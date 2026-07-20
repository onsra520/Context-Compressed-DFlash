/** Live arbitrary-prompt comparison driven only by backend SSE events. */

const CONDITIONS = ['baseline-ar', 'd-flash', 'cc-dflash'];
const IDS = {
    'baseline-ar': { status: 'baselineStatus', output: 'baselineResponse', metrics: 'baselineMetrics', progress: 'baselineProgress' },
    'd-flash': { status: 'dflashStatus', output: 'dflashResponse', metrics: 'dflashMetrics', progress: 'dflashProgress' },
    'cc-dflash': { status: 'ccStatus', output: 'ccResponse', metrics: 'ccMetrics', progress: 'ccProgress' },
};

const round = (value, digits = 1) => Number(value).toFixed(digits);
const formatMs = value => value == null ? '—' : value >= 1000 ? `${round(value / 1000, 2)} s` : `${round(value, 1)} ms`;
const formatRate = value => value == null ? '—' : `${round(value * 100, 1)}%`;

function setStatus(conditionId, status) {
    const element = document.getElementById(IDS[conditionId].status);
    element.textContent = status.toUpperCase();
    element.className = `status ${status}`;
}

function setStep(index) {
    const steps = [...document.getElementById('compareSteps').children];
    steps.forEach((step, position) => {
        step.className = `step ${position < index ? 'done' : position === index ? 'active' : ''}`;
    });
}

function metric(label, value, cssClass = 'm-token') {
    return `<div class="metric ${cssClass}"><span>${label}</span><b>${value}</b></div>`;
}

function renderConditionMetrics(conditionId, values) {
    const rows = [
        metric('Input tokens', values.input_tokens ?? '—'),
        metric('Output tokens', values.output_tokens ?? '—'),
        metric('TTFT', formatMs(values.ttft_ms), 'm-lat'),
        metric('Decode tok/s', values.decode_tok_s == null ? '—' : `${round(values.decode_tok_s)} tok/s`, 'm-tps'),
        metric('Pipeline E2E', formatMs(values.pipeline_e2e_ms), 'm-speed'),
        metric('Stop reason', values.stop_reason || '—'),
    ];
    if (conditionId !== 'baseline-ar') {
        rows.push(
            metric('Draft proposed', values.proposed_draft_tokens ?? '—', 'm-accept'),
            metric('Draft accepted', values.accepted_draft_tokens ?? '—', 'm-accept'),
            metric('Draft rejected', values.rejected_draft_tokens ?? '—', 'm-accept'),
            metric('Acceptance rate', formatRate(values.acceptance_rate), 'm-accept'),
            metric('Verify loops', values.verify_loops ?? '—', 'm-accept'),
            metric('Mean accepted / loop', values.mean_accepted_tokens_per_loop == null ? '—' : round(values.mean_accepted_tokens_per_loop, 2), 'm-accept'),
        );
    }
    if (conditionId === 'cc-dflash') {
        rows.push(
            metric('Original → compressed', `${values.original_input_tokens ?? '—'} → ${values.compressed_input_tokens ?? '—'}`, 'm-compress'),
            metric('Compression reduction', formatRate(values.reduction_rate), 'm-compress'),
            metric('Compression latency', formatMs(values.compression_latency_ms), 'm-compress'),
            metric('Compression device', values.compression_device || '—', 'm-compress'),
            metric('Compression status', values.compression_status || '—', 'm-compress'),
            metric('E2E split', `${formatMs(values.compression_latency_ms)} + ${formatMs(values.generation_component_ms)}`, 'm-compress'),
        );
    }
    document.getElementById(IDS[conditionId].metrics).innerHTML = rows.join('');
}

function renderLiveSummary(results) {
    const baseline = results['baseline-ar'];
    const dflash = results['d-flash'];
    const cc = results['cc-dflash'];
    const summary = document.getElementById('comparisonSummary');
    const body = document.getElementById('comparisonSummaryBody');
    summary.style.display = 'block';
    body.innerHTML = `
        <div class="summary-grid live-summary-grid">
            <div><span>Input Tokens</span><b>${cc ? `${cc.original_input_tokens} → ${cc.compressed_input_tokens}` : baseline?.input_tokens ?? '—'}</b></div>
            <div><span>TTFT · AR / DF / CC</span><b>${[baseline, dflash, cc].map(v => v ? formatMs(v.ttft_ms) : '—').join(' · ')}</b></div>
            <div><span>Decode Tok/s · AR / DF / CC</span><b>${[baseline, dflash, cc].map(v => v ? round(v.decode_tok_s) : '—').join(' · ')}</b></div>
            <div><span>Pipeline E2E · AR / DF / CC</span><b>${[baseline, dflash, cc].map(v => v ? formatMs(v.pipeline_e2e_ms) : '—').join(' · ')}</b></div>
            <div><span>Compression Reduction</span><b>${cc ? formatRate(cc.reduction_rate) : '—'}</b></div>
            <div><span>D-Flash Acceptance Rate · DF / CC</span><b>${[dflash, cc].map(v => v ? formatRate(v.acceptance_rate) : '—').join(' · ')}</b></div>
        </div>
        <p class="summary-caveat">Arbitrary-prompt telemetry from this run only: performance, acceptance, and compression.</p>
    `;
}

function parseEvent(event) {
    return JSON.parse(event.data).data;
}

export async function initBenchmarkShowdown() {
    const sampleSelect = document.getElementById('demoPreset');
    const prompt = document.getElementById('comparePrompt');
    const device = document.getElementById('compressionDevice');
    const maxTokens = document.getElementById('maxNewTokens');
    const start = document.getElementById('compareStart');
    const reset = document.getElementById('compareReset');
    const stats = document.getElementById('inputStats');
    let samples = {};
    let source = null;
    let activeRunId = null;
    let results = {};
    let comparisonAvailable = false;

    function updateLocalStats() {
        const value = prompt.value.trim();
        stats.innerHTML = `<span>Words: ${value ? value.split(/\s+/).length : 0}</span><span>Characters: ${value.length}</span><span>Tokens: measured by the live runtime</span>`;
    }

    function clearRunDisplay() {
        results = {};
        setStep(-1);
        CONDITIONS.forEach(conditionId => {
            setStatus(conditionId, 'idle');
            document.getElementById(IDS[conditionId].output).textContent = 'Waiting for committed tokens...';
            document.getElementById(IDS[conditionId].metrics).innerHTML = '';
            document.getElementById(IDS[conditionId].progress).style.display = 'none';
        });
        document.getElementById('comparisonSummary').style.display = 'none';
    }

    async function cancelActiveRun() {
        if (source) {
            source.close();
            source = null;
        }
        if (activeRunId) {
            await fetch(`/api/demo/runs/${activeRunId}/cancel`, { method: 'POST' }).catch(() => {});
            activeRunId = null;
        }
    }

    async function loadCapabilitiesAndSamples() {
        const [capabilities, samplePayload] = await Promise.all([
            fetch('/api/demo/capabilities').then(response => response.json()),
            fetch('/api/demo/prompt-samples').then(response => response.json()),
        ]);
        comparisonAvailable = Boolean(capabilities.cuda_available);
        start.disabled = !comparisonAvailable;
        start.title = comparisonAvailable ? '' : 'CUDA is required by the configured target and draft models.';
        device.value = capabilities.default_compression_device;
        sampleSelect.innerHTML = '';
        samplePayload.samples.forEach(sample => {
            samples[sample.id] = sample;
            const option = document.createElement('option');
            option.value = sample.id;
            option.textContent = sample.label;
            sampleSelect.appendChild(option);
        });
        const custom = document.createElement('option');
        custom.value = 'custom';
        custom.textContent = 'Prompt tùy chỉnh';
        sampleSelect.appendChild(custom);
        const first = samplePayload.samples[0];
        if (first) {
            sampleSelect.value = first.id;
            prompt.value = first.prompt;
        }
        updateLocalStats();
    }

    function attachEventSource(runId) {
        source = new EventSource(`/api/demo/runs/${runId}/events`);
        source.addEventListener('run.started', () => setStep(0));
        source.addEventListener('input.analyzed', () => setStep(1));
        source.addEventListener('condition.queued', event => setStatus(parseEvent(event).condition_id, 'queued'));
        source.addEventListener('condition.started', event => {
            const conditionId = parseEvent(event).condition_id;
            setStep(conditionId === 'baseline-ar' ? 1 : conditionId === 'd-flash' ? 2 : 4);
            setStatus(conditionId, 'running');
            document.getElementById(IDS[conditionId].output).textContent = '';
            document.getElementById(IDS[conditionId].progress).style.display = 'block';
        });
        source.addEventListener('condition.token_delta', event => {
            const data = parseEvent(event);
            document.getElementById(IDS[data.condition_id].output).textContent += data.text_delta;
        });
        source.addEventListener('condition.metrics', event => {
            const data = parseEvent(event);
            results[data.condition_id] = data;
            renderConditionMetrics(data.condition_id, data);
            renderLiveSummary(results);
        });
        source.addEventListener('condition.completed', event => {
            const data = parseEvent(event);
            const output = document.getElementById(IDS[data.condition_id].output);
            if (!output.textContent) output.textContent = data.text;
            setStatus(data.condition_id, 'completed');
            document.getElementById(IDS[data.condition_id].progress).style.display = 'none';
        });
        source.addEventListener('compression.started', () => setStep(3));
        source.addEventListener('comparison.completed', () => {
            setStep(5);
            renderLiveSummary(results);
        });
        source.addEventListener('run.completed', () => {
            source.close();
            source = null;
            activeRunId = null;
            start.disabled = !comparisonAvailable;
        });
        source.addEventListener('run.failed', event => {
            const data = parseEvent(event);
            CONDITIONS.forEach(conditionId => {
                if (document.getElementById(IDS[conditionId].status).textContent === 'RUNNING') setStatus(conditionId, 'failed');
            });
            const summary = document.getElementById('comparisonSummary');
            summary.style.display = 'block';
            document.getElementById('comparisonSummaryBody').textContent = `Run failed at ${data.stage}: ${data.error}`;
            source.close();
            source = null;
            activeRunId = null;
            start.disabled = !comparisonAvailable;
        });
        source.addEventListener('run.cancelled', () => {
            CONDITIONS.forEach(conditionId => {
                if (document.getElementById(IDS[conditionId].status).textContent === 'RUNNING') setStatus(conditionId, 'cancelled');
            });
            source.close();
            source = null;
            activeRunId = null;
            start.disabled = !comparisonAvailable;
        });
    }

    async function runComparison() {
        await cancelActiveRun();
        if (!prompt.value.trim()) {
            prompt.focus();
            return;
        }
        clearRunDisplay();
        start.disabled = true;
        const response = await fetch('/api/demo/runs', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                prompt: prompt.value,
                compression_device: device.value,
                max_new_tokens: Number(maxTokens.value),
            }),
        });
        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: response.statusText }));
            start.disabled = !comparisonAvailable;
            window.alert(error.detail || response.statusText);
            return;
        }
        const created = await response.json();
        activeRunId = created.run_id;
        attachEventSource(activeRunId);
    }

    sampleSelect.addEventListener('change', () => {
        if (samples[sampleSelect.value]) prompt.value = samples[sampleSelect.value].prompt;
        updateLocalStats();
    });
    prompt.addEventListener('input', () => {
        if (!samples[sampleSelect.value] || prompt.value !== samples[sampleSelect.value].prompt) sampleSelect.value = 'custom';
        updateLocalStats();
    });
    start.addEventListener('click', () => runComparison().catch(error => window.alert(error.message)));
    reset.addEventListener('click', () => cancelActiveRun().finally(clearRunDisplay));
    clearRunDisplay();
    await loadCapabilitiesAndSamples();
}
