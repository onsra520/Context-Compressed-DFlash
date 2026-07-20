/**
 * benchmark-showdown.js
 *
 * Connects the comparison UI to the real FastAPI backend.
 * No mock/random/fallback production data.
 * SSE events must be emitted by the server as proper SSE frames:
 *   event: condition.started
 *   data: {"condition_id":"baseline-ar"}
 */

import { demoPresets } from '../mocks/mock-data.js';

const round = (value, digits = 0) => Number(value.toFixed(digits));

function formatMs(value) {
    if (value == null) return '—';
    if (value >= 1000) return `${round(value / 1000, 2)} s`;
    return `${Math.round(value)} ms`;
}

function analyzePromptLocally(prompt) {
    const trimmed = prompt.trim();
    const words = trimmed ? trimmed.split(/\s+/).length : 0;
    const characters = trimmed.length;
    const estimatedTokens = Math.max(8, Math.ceil(characters / 4.2 + words * 0.18));
    return { words, characters, estimatedTokens };
}

function metricClass(label) {
    const n = label.toLowerCase();
    if (n.includes('warm end-to-end') || n.includes('e2e vs')) return 'm-speed';
    if (n.includes('throughput')) return 'm-tps';
    if (n.includes('prefill')) return 'm-lat';
    if (n.includes('generation latency')) return 'm-cyan';
    if (n.includes('compression')) return 'm-compress';
    if (n.includes('tau') || n.includes('acceptance')) return 'm-accept';
    return 'm-token';
}

function metricsFor(row, baselineE2E) {
    const cmpLabel = row.condition_id === 'baseline-ar'
        ? '(reference)'
        : baselineE2E && row.warm_request_e2e_ms != null
            ? `${round((baselineE2E - row.warm_request_e2e_ms) / baselineE2E * 100, 1)}% ${baselineE2E > row.warm_request_e2e_ms ? 'faster' : 'slower'} than Baseline`
            : '—';

    const compressionRatioLabel = !row.compression_applied && !row.compression_bypassed
        ? 'not applied'
        : row.compression_bypassed
            ? `bypassed (${row.compression_bypass_reason || 'unknown'})`
            : row.compression_ratio != null
                ? `${round(row.compression_ratio, 2)}×`
                : '—';

    return [
        ['Input tokens', row.input_tokens_precompression != null ? row.input_tokens_precompression.toLocaleString('en-US') : '—'],
        ['Effective prefill', row.input_tokens_final != null ? row.input_tokens_final.toLocaleString('en-US') : '—'],
        ['Compression ratio', compressionRatioLabel],
        ['Compression overhead', row.compression_total_ms != null ? formatMs(row.compression_total_ms) : '0 ms'],
        ['Prefill latency', formatMs(row.target_prefill_ms)],
        ['Generation latency', formatMs(row.decode_total_ms)],
        ['Warm end-to-end', formatMs(row.warm_request_e2e_ms)],
        ['Generation throughput', row.generation_tok_s != null ? `${round(row.generation_tok_s, 1)} tok/s` : '—'],
        ['Acceptance τ', row.effective_tau != null ? round(row.effective_tau, 2) : '—'],
        ['Warm E2E vs Baseline', cmpLabel],
    ];
}

function renderMetrics(elementId, row, baselineE2E) {
    const metrics = metricsFor(row, baselineE2E);
    document.getElementById(elementId).innerHTML = metrics.map(([label, value]) =>
        `<div class="metric ${metricClass(label)}"><span>${label}</span><b>${value}</b></div>`
    ).join('');
}

function setStatus(id, text) {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = text;
    el.className = `status ${
        text === 'RUNNING' ? 'running' : text === 'DONE' ? 'done' : text === 'FAILED' ? 'failed' : ''
    }`;
}

function setSteps(index) {
    const steps = document.getElementById('compareSteps');
    if (!steps) return;
    [...steps.children].forEach((step, i) => {
        step.className = `step ${i < index ? 'done' : i === index ? 'active' : ''}`;
    });
}

function showConditionError(conditionId, errorMsg) {
    // Show error in the relevant card's response area.
    const cardMap = {
        'baseline-ar': { resp: 'baselineResponse', status: 'baselineStatus', progress: 'baselineProgress' },
        'dflash-r1': { resp: 'dflashResponse', status: 'dflashStatus', progress: 'dflashProgress' },
        'cc-dflash-r2': { resp: 'ccResponse', status: 'ccStatus', progress: 'ccProgress' },
        'cc-dflash-r2-gpu': { resp: 'ccResponse', status: 'ccStatus', progress: 'ccProgress' },
    };
    // Show in all running cards if we don't know which one failed
    for (const [, ids] of Object.entries(cardMap)) {
        const statusEl = document.getElementById(ids.status);
        if (statusEl && statusEl.textContent === 'RUNNING') {
            setStatus(ids.status, 'FAILED');
            const respEl = document.getElementById(ids.resp);
            if (respEl) respEl.textContent = `Error: ${errorMsg}`;
            const progEl = document.getElementById(ids.progress);
            if (progEl) progEl.style.display = 'none';
        }
    }
}

function summaryMarkup(results) {
    const baseline = results['baseline-ar'];
    const dflash = results['dflash-r1'];
    const cc = results['cc-dflash-r2-gpu'] || results['cc-dflash-r2'];

    if (!baseline || !dflash || !cc) {
        return '<p>Incomplete results — one or more conditions did not complete.</p>';
    }

    const arr = [baseline, dflash, cc];
    const fastest = arr.reduce((a, b) =>
        (a.warm_request_e2e_ms ?? Infinity) < (b.warm_request_e2e_ms ?? Infinity) ? a : b
    );

    const isContextless = cc.compression_bypassed && cc.compression_bypass_reason === 'empty_context';
    const isBypass = cc.compression_bypassed;
    const workload = isContextless
        ? 'question-only (compressor not loaded)'
        : isBypass
            ? `compression bypass (${cc.compression_bypass_reason || 'short context'})`
            : 'compressed context';

    const gainDflashGen = (baseline.decode_total_ms && dflash.decode_total_ms)
        ? baseline.decode_total_ms / dflash.decode_total_ms
        : null;

    const ccReduction = cc.prompt_reduction_pct != null
        ? `${round(cc.prompt_reduction_pct, 1)}%`
        : 'n/a';

    const ccE2E = cc.warm_request_e2e_ms;
    const dflashE2E = dflash.warm_request_e2e_ms;

    let interpretation;
    if (isContextless) {
        interpretation = 'Workload is question-only. CC-DFlash gracefully bypasses compression; compressor was not loaded.';
    } else if (isBypass) {
        interpretation = 'Context was too short to compress. Passthrough was used.';
    } else if (ccE2E != null && dflashE2E != null && ccE2E < dflashE2E) {
        interpretation = 'Compression savings offset overhead. CC-DFlash is faster end-to-end than D-Flash.';
    } else {
        interpretation = 'Compression overhead exceeds savings. D-Flash is faster end-to-end than CC-DFlash for this workload.';
    }

    return `
        <div class="summary-grid">
            <div><span>Workload</span><b>${workload}</b></div>
            <div><span>Fastest warm E2E</span><b>${fastest.display_name}</b></div>
            <div><span>CC prompt reduction</span><b>${ccReduction}</b></div>
            <div><span>DFlash gen speedup</span><b>${gainDflashGen != null ? round(gainDflashGen, 2) + '×' : 'n/a'}</b></div>
        </div>
        <p>${interpretation}</p>
        <p class="summary-caveat">Results generated from real model execution using a generic demo policy. Not a canonical benchmark run.</p>
    `;
}

export async function initBenchmarkShowdown() {
    const preset = document.getElementById('demoPreset');
    const promptEl = document.getElementById('comparePrompt');
    const inputStats = document.getElementById('inputStats');
    const deviceSelect = document.getElementById('compressionDevice');
    const startBtn = document.getElementById('compareStart');
    const resetBtn = document.getElementById('compareReset');
    const summary = document.getElementById('comparisonSummary');
    const summaryBody = document.getElementById('comparisonSummaryBody');

    let eventSource = null;
    let baselineE2E = null;
    let results = {};
    let comparisonAvailable = true;

    // Probe capabilities and disable CUDA if unavailable.
    try {
        const caps = await fetch('/api/capabilities').then(r => r.json());
        if (!caps.cuda_available) {
            deviceSelect.value = 'cpu';
            const cudaOpt = deviceSelect.querySelector('option[value="cuda"]');
            if (cudaOpt) cudaOpt.disabled = true;
        }
        if (!caps.comparison_available) {
            comparisonAvailable = false;
            startBtn.disabled = true;
            startBtn.title = caps.comparison_unavailable_reason || 'Comparison runtime is unavailable.';
            if (summaryBody) {
                summaryBody.innerHTML = `<p class="error-msg">${caps.comparison_unavailable_reason || 'Comparison runtime is unavailable.'}</p>`;
            }
            if (summary) summary.style.display = 'block';
        }
    } catch (e) {
        console.warn('Could not fetch /api/capabilities:', e);
    }

    function updateStats() {
        const analysis = analyzePromptLocally(promptEl.value);
        inputStats.innerHTML = `
            <span>Words: ${analysis.words}</span>
            <span>Est. tokens: ${analysis.estimatedTokens.toLocaleString('en-US')}</span>
        `;
    }

    function applyPreset(key) {
        const p = demoPresets[key];
        if (p) promptEl.value = p.prompt;
        updateStats();
    }

    function cancelRun() {
        if (eventSource) {
            eventSource.close();
            eventSource = null;
        }
        startBtn.disabled = !comparisonAvailable;
    }

    function resetComparison() {
        cancelRun();
        setSteps(-1);
        results = {};
        baselineE2E = null;
        ['baselineMetrics', 'dflashMetrics', 'ccMetrics'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.innerHTML = '';
        });
        ['baselineResponse', 'dflashResponse', 'ccResponse'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.textContent = 'Waiting for comparison...';
        });
        ['baselineStatus', 'dflashStatus', 'ccStatus'].forEach(id => setStatus(id, 'IDLE'));
        ['baselineProgress', 'dflashProgress', 'ccProgress'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.style.display = 'none';
        });
        if (summary) summary.style.display = 'none';
        applyPreset(preset.value || 'gsm8k');
    }

    async function runComparison() {
        cancelRun();
        const value = promptEl.value.trim();
        if (!value) { promptEl.focus(); return; }

        startBtn.disabled = true;
        if (summary) summary.style.display = 'none';
        setSteps(0);

        try {
            const resp = await fetch('/api/compare', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ input: value, compression_device: deviceSelect.value }),
            });

            if (resp.status === 409) {
                alert('Server is busy with another comparison. Please wait and retry.');
                startBtn.disabled = !comparisonAvailable;
                return;
            }
            if (!resp.ok) {
                const err = await resp.json().catch(() => ({ detail: resp.statusText }));
                alert('Error starting job: ' + (err.detail || resp.statusText));
                startBtn.disabled = !comparisonAvailable;
                return;
            }

            const { job_id } = await resp.json();
            results = {};
            baselineE2E = null;

            eventSource = new EventSource('/api/compare/' + job_id + '/events');

            eventSource.addEventListener('input.parsed', () => {
                setSteps(1);
            });

            eventSource.addEventListener('condition.started', e => {
                // data is JSON: {"condition_id": "baseline-ar"}
                let conditionId;
                try {
                    conditionId = JSON.parse(e.data).condition_id;
                } catch {
                    conditionId = e.data; // fallback for plain string
                }
                if (conditionId === 'baseline-ar') {
                    setSteps(1);
                    setStatus('baselineStatus', 'RUNNING');
                    const el = document.getElementById('baselineProgress');
                    if (el) el.style.display = 'block';
                } else if (conditionId === 'dflash-r1') {
                    setSteps(2);
                    setStatus('dflashStatus', 'RUNNING');
                    const el = document.getElementById('dflashProgress');
                    if (el) el.style.display = 'block';
                } else {
                    setSteps(3);
                    setStatus('ccStatus', 'RUNNING');
                    const el = document.getElementById('ccProgress');
                    if (el) el.style.display = 'block';
                }
            });

            eventSource.addEventListener('condition.completed', e => {
                let data;
                try { data = JSON.parse(e.data); } catch { return; }
                results[data.condition_id] = data;

                let statusId, metricsId, respId, progressId;
                if (data.condition_id === 'baseline-ar') {
                    statusId = 'baselineStatus'; metricsId = 'baselineMetrics';
                    respId = 'baselineResponse'; progressId = 'baselineProgress';
                    baselineE2E = data.warm_request_e2e_ms;
                } else if (data.condition_id === 'dflash-r1') {
                    statusId = 'dflashStatus'; metricsId = 'dflashMetrics';
                    respId = 'dflashResponse'; progressId = 'dflashProgress';
                } else {
                    statusId = 'ccStatus'; metricsId = 'ccMetrics';
                    respId = 'ccResponse'; progressId = 'ccProgress';
                }

                setStatus(statusId, 'DONE');
                const progEl = document.getElementById(progressId);
                if (progEl) progEl.style.display = 'none';
                const respEl = document.getElementById(respId);
                if (respEl) respEl.textContent = data.generated_text;
                renderMetrics(metricsId, data, baselineE2E);
            });

            eventSource.addEventListener('comparison.completed', e => {
                setSteps(4);
                let allResults;
                try { allResults = JSON.parse(e.data); } catch { allResults = results; }
                if (summaryBody) summaryBody.innerHTML = summaryMarkup(allResults);
                if (summary) summary.style.display = 'block';
            });

            eventSource.addEventListener('job.completed', () => {
                eventSource.close();
                eventSource = null;
                startBtn.disabled = !comparisonAvailable;
            });

            eventSource.addEventListener('condition.failed', e => {
                let data;
                try { data = JSON.parse(e.data); } catch { data = { error: e.data }; }
                showConditionError(null, data.error || 'Unknown error');
            });

            eventSource.addEventListener('job.failed', e => {
                let data;
                try { data = JSON.parse(e.data); } catch { data = { error: e.data }; }
                if (summaryBody) {
                    summaryBody.innerHTML = `<p class="error-msg">Job failed: ${data.error || 'Unknown error'}</p>`;
                }
                if (summary) summary.style.display = 'block';
                if (eventSource) { eventSource.close(); eventSource = null; }
                startBtn.disabled = !comparisonAvailable;
            });

            eventSource.onerror = () => {
                // Connection lost after job completed is normal; don't alert.
                if (startBtn.disabled) {
                    startBtn.disabled = !comparisonAvailable;
                }
            };

        } catch (err) {
            console.error('runComparison error:', err);
            alert('Network error: ' + err.message);
            startBtn.disabled = !comparisonAvailable;
        }
    }

    preset.addEventListener('change', () => applyPreset(preset.value));
    promptEl.addEventListener('input', () => {
        if (promptEl.value !== (demoPresets[preset.value] || {}).prompt) {
            preset.value = 'custom';
        }
        updateStats();
    });
    startBtn.addEventListener('click', runComparison);
    resetBtn.addEventListener('click', resetComparison);

    resetComparison();
}
