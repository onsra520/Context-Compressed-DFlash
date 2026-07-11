import { demoPresets } from '../mocks/mock-data.js';

const clamp = (value, min, max) => Math.max(min, Math.min(max, value));
const round = (value, digits = 0) => Number(value.toFixed(digits));

function hashText(text) {
    let hash = 2166136261;
    for (let index = 0; index < text.length; index += 1) {
        hash ^= text.charCodeAt(index);
        hash = Math.imul(hash, 16777619);
    }
    return hash >>> 0;
}

function analyzePrompt(prompt) {
    const trimmed = prompt.trim();
    const words = trimmed ? trimmed.split(/\s+/).length : 0;
    const characters = trimmed.length;
    const estimatedTokens = Math.max(8, Math.ceil(characters / 4.2 + words * 0.18));
    const workload = estimatedTokens < 180 ? 'Short context' : estimatedTokens < 750 ? 'Medium context' : 'Long context';
    return { words, characters, estimatedTokens, workload };
}

function prefillLatency(tokens) {
    return 22 + 0.3 * tokens + 0.02 * Math.pow(tokens, 1.45);
}

function buildOutputPreview(prompt) {
    const clean = prompt.replace(/\s+/g, ' ').trim();
    const excerpt = clean.length > 104 ? `${clean.slice(0, 104)}…` : clean;
    return `Generated answer preview for: “${excerpt || 'empty prompt'}”`;
}

function computeSimulation(prompt) {
    const analysis = analyzePrompt(prompt);
    const seed = hashText(prompt);
    const inputTokens = analysis.estimatedTokens;
    const outputTokens = clamp(Math.round(48 + Math.sqrt(inputTokens) * 1.55 + (seed % 17)), 52, 180);
    const preview = buildOutputPreview(prompt);

    const baselineTps = 22 + (seed % 5);
    const baselinePrefill = prefillLatency(inputTokens);
    const baselineGeneration = (outputTokens / baselineTps) * 1000;
    const baselineE2E = baselinePrefill + baselineGeneration;

    const dflashTps = 41 + (seed % 8);
    const dflashTau = 6.2 + ((seed >> 3) % 19) / 10;
    const dflashPrefill = baselinePrefill * 1.02;
    const dflashGeneration = (outputTokens / dflashTps) * 1000;
    const dflashE2E = dflashPrefill + dflashGeneration + 35;

    const keepRate = 0.5 + (((seed >> 5) % 7) - 3) / 100;
    const compressedTokens = Math.max(24, Math.round(inputTokens * keepRate));
    const compressionOverhead = 105 + inputTokens * 0.12 + ((seed >> 7) % 18);
    const ccTps = dflashTps * 0.98;
    const ccTau = Math.max(4.8, dflashTau - 0.2);
    const ccPrefill = prefillLatency(compressedTokens) * 1.02;
    const ccGeneration = (outputTokens / ccTps) * 1000;
    const ccE2E = compressionOverhead + ccPrefill + ccGeneration + 35;

    return {
        analysis,
        baseline: {
            label: 'Baseline-AR',
            inputTokens,
            effectiveTokens: inputTokens,
            compressionRatio: null,
            compressionOverhead: 0,
            prefill: baselinePrefill,
            generation: baselineGeneration,
            e2e: baselineE2E,
            throughput: baselineTps,
            tau: null,
            outputTokens,
            preview
        },
        dflash: {
            label: 'D-Flash',
            inputTokens,
            effectiveTokens: inputTokens,
            compressionRatio: null,
            compressionOverhead: 0,
            prefill: dflashPrefill,
            generation: dflashGeneration,
            e2e: dflashE2E,
            throughput: dflashTps,
            tau: dflashTau,
            outputTokens,
            preview
        },
        cc: {
            label: 'CC-DFlash',
            inputTokens,
            effectiveTokens: compressedTokens,
            compressionRatio: inputTokens / compressedTokens,
            compressionOverhead,
            prefill: ccPrefill,
            generation: ccGeneration,
            e2e: ccE2E,
            throughput: ccTps,
            tau: ccTau,
            outputTokens,
            preview
        }
    };
}

function metricClass(label) {
    const normalized = label.toLowerCase();
    if (normalized.includes('e2e') || normalized.includes('end-to-end')) return 'm-speed';
    if (normalized.includes('throughput')) return 'm-tps';
    if (normalized.includes('prefill')) return 'm-lat';
    if (normalized.includes('generation')) return 'm-cyan';
    if (normalized.includes('compression')) return 'm-compress';
    if (normalized.includes('tau') || normalized.includes('τ')) return 'm-accept';
    return 'm-token';
}

function formatMs(value) {
    if (value >= 1000) return `${round(value / 1000, 2)} s`;
    return `${Math.round(value)} ms`;
}

function metricsFor(row, baselineE2E) {
    return [
        ['Input tokens', row.inputTokens.toLocaleString('en-US')],
        ['Effective prefill', row.effectiveTokens.toLocaleString('en-US')],
        ['Compression ratio', row.compressionRatio ? `${round(row.compressionRatio, 2)}×` : '—'],
        ['Compression overhead', row.compressionOverhead ? formatMs(row.compressionOverhead) : '0 ms'],
        ['Prefill latency', formatMs(row.prefill)],
        ['Generation latency', formatMs(row.generation)],
        ['End-to-end', formatMs(row.e2e)],
        ['Generation throughput', `${round(row.throughput, 1)} tok/s`],
        ['Acceptance τ', row.tau ? round(row.tau, 1) : '—'],
        ['E2E vs Baseline', `${round(baselineE2E / row.e2e, 2)}×`]
    ];
}

function renderMetrics(elementId, row, baselineE2E) {
    const metrics = metricsFor(row, baselineE2E);
    document.getElementById(elementId).innerHTML = metrics.map(([label, value]) => (
        `<div class="metric ${metricClass(label)}"><span>${label}</span><b>${value}</b></div>`
    )).join('');
}

function setStatus(id, text) {
    const element = document.getElementById(id);
    element.textContent = text;
    element.className = `status ${text === 'RUNNING' ? 'running' : text === 'DONE' ? 'done' : ''}`;
}

function setSteps(index) {
    [...document.getElementById('compareSteps').children].forEach((step, stepIndex) => {
        step.className = `step ${stepIndex < index ? 'done' : stepIndex === index ? 'active' : ''}`;
    });
}

function progress(fillId, duration, signal) {
    return new Promise((resolve) => {
        const fill = document.getElementById(fillId);
        const wrap = fill.parentElement;
        const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        const actualDuration = reduceMotion ? 80 : duration;
        wrap.style.display = 'block';
        fill.style.width = '0%';
        const startedAt = performance.now();
        let frame = 0;

        const finish = () => {
            cancelAnimationFrame(frame);
            fill.style.width = '100%';
            window.setTimeout(() => {
                wrap.style.display = 'none';
                resolve();
            }, reduceMotion ? 0 : 130);
        };

        const tick = (time) => {
            if (signal.aborted) {
                wrap.style.display = 'none';
                resolve();
                return;
            }
            const ratio = Math.min((time - startedAt) / actualDuration, 1);
            fill.style.width = `${ratio * 100}%`;
            if (ratio >= 1) {
                finish();
                return;
            }
            frame = requestAnimationFrame(tick);
        };

        signal.addEventListener('abort', () => {
            cancelAnimationFrame(frame);
            wrap.style.display = 'none';
            resolve();
        }, { once: true });
        frame = requestAnimationFrame(tick);
    });
}

function summaryMarkup(simulation) {
    const { baseline, dflash, cc, analysis } = simulation;
    const fastest = [baseline, dflash, cc].sort((a, b) => a.e2e - b.e2e)[0];
    const reduction = round((1 - cc.effectiveTokens / cc.inputTokens) * 100, 1);
    const ccVsDflash = cc.e2e <= dflash.e2e;
    const interpretation = ccVsDflash
        ? `Với ${analysis.workload.toLowerCase()}, prefill saving đã bù được compression overhead trong mô phỏng. CC-DFlash có E2E thấp hơn D-Flash.`
        : `Với ${analysis.workload.toLowerCase()}, compression overhead lớn hơn phần prefill saving. D-Flash giữ E2E thấp hơn CC-DFlash.`;

    return `
        <div class="summary-grid">
            <div><span>Workload</span><b>${analysis.workload}</b></div>
            <div><span>Fastest E2E</span><b>${fastest.label}</b></div>
            <div><span>CC input reduction</span><b>${reduction}%</b></div>
            <div><span>DFlash generation gain</span><b>${round(baseline.generation / dflash.generation, 2)}×</b></div>
        </div>
        <p>${interpretation}</p>
        <p class="summary-caveat">Simulation values illustrate architecture behavior only. Scientific results are reported in the frozen evidence section.</p>
    `;
}

export function initBenchmarkShowdown() {
    const preset = document.getElementById('demoPreset');
    const prompt = document.getElementById('comparePrompt');
    const inputStats = document.getElementById('inputStats');
    const start = document.getElementById('compareStart');
    const reset = document.getElementById('compareReset');
    const summary = document.getElementById('comparisonSummary');
    const summaryBody = document.getElementById('comparisonSummaryBody');
    let controller = new AbortController();

    function updateStats() {
        const analysis = analyzePrompt(prompt.value);
        inputStats.innerHTML = `
            <span>Words: ${analysis.words}</span>
            <span>Estimated tokens: ${analysis.estimatedTokens.toLocaleString('en-US')}</span>
            <span>Workload: ${analysis.workload}</span>
        `;
    }

    function applyPreset(key) {
        prompt.value = demoPresets[key].prompt;
        updateStats();
    }

    function cancelRun() {
        controller.abort();
        controller = new AbortController();
        start.disabled = false;
    }

    function resetComparison() {
        cancelRun();
        setSteps(-1);
        ['baselineMetrics', 'dflashMetrics', 'ccMetrics'].forEach((id) => {
            document.getElementById(id).innerHTML = '';
        });
        document.getElementById('baselineResponse').textContent = 'Waiting for comparison...';
        document.getElementById('dflashResponse').textContent = 'Waiting for comparison...';
        document.getElementById('ccResponse').textContent = 'Waiting for comparison...';
        setStatus('baselineStatus', 'IDLE');
        setStatus('dflashStatus', 'IDLE');
        setStatus('ccStatus', 'IDLE');
        summary.style.display = 'none';
        applyPreset(preset.value);
    }

    async function runComparison() {
        cancelRun();
        const localController = controller;
        const value = prompt.value.trim();
        if (!value) {
            prompt.focus();
            return;
        }

        start.disabled = true;
        summary.style.display = 'none';
        const simulation = computeSimulation(value);
        setSteps(0);
        await progress('baselineFill', 350, localController.signal);
        if (localController.signal.aborted) return;

        setSteps(1);
        setStatus('baselineStatus', 'RUNNING');
        await progress('baselineFill', 800, localController.signal);
        if (localController.signal.aborted) return;
        document.getElementById('baselineResponse').textContent = simulation.baseline.preview;
        renderMetrics('baselineMetrics', simulation.baseline, simulation.baseline.e2e);
        setStatus('baselineStatus', 'DONE');

        setSteps(2);
        setStatus('dflashStatus', 'RUNNING');
        await progress('dflashFill', 750, localController.signal);
        if (localController.signal.aborted) return;
        document.getElementById('dflashResponse').textContent = simulation.dflash.preview;
        renderMetrics('dflashMetrics', simulation.dflash, simulation.baseline.e2e);
        setStatus('dflashStatus', 'DONE');

        setSteps(3);
        setStatus('ccStatus', 'RUNNING');
        await progress('ccFill', 920, localController.signal);
        if (localController.signal.aborted) return;
        document.getElementById('ccResponse').textContent = simulation.cc.preview;
        renderMetrics('ccMetrics', simulation.cc, simulation.baseline.e2e);
        setStatus('ccStatus', 'DONE');

        setSteps(4);
        summaryBody.innerHTML = summaryMarkup(simulation);
        summary.style.display = 'block';
        start.disabled = false;
    }

    preset.addEventListener('change', () => applyPreset(preset.value));
    prompt.addEventListener('input', () => {
        if (prompt.value !== demoPresets[preset.value]?.prompt) preset.value = 'custom';
        updateStats();
    });
    start.addEventListener('click', runComparison);
    reset.addEventListener('click', resetComparison);

    applyPreset('gsm8k');
    resetComparison();
}
