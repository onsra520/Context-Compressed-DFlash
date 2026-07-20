import { finalBenchmarkN20 } from '../data/final-benchmark-n20.js';

const datasetData = (dataset) => finalBenchmarkN20.datasets[dataset];
const formatTokens = (value) => value.toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
});

function renderThroughputChart(dataset) {
    const container = document.getElementById('chart-throughput');
    const note = document.getElementById('note-throughput');
    if (!container || !note) return;

    const data = datasetData(dataset).throughput;
    const maxValue = Math.max(...data.map((row) => row.value)) * 1.1;
    container.innerHTML = `
        <div class="plot-frame">
            <div class="bar-chart bar-chart--vertical">
                ${data.map((row) => {
                    const highlightClass = row.name === 'DFlash-R1'
                        ? 'highlight-cyan'
                        : row.name === 'CC-DFlash-R2'
                            ? 'highlight-magenta'
                            : '';
                    return `
                        <div class="bar-col">
                            <div class="bar-val">${row.value.toFixed(2)}</div>
                            <div class="bar-track">
                                <div class="bar-fill ${highlightClass}" style="height: ${(row.value / maxValue) * 100}%"></div>
                            </div>
                            <div class="bar-label">${row.name.replace('-R', '<br>-R')}</div>
                        </div>
                    `;
                }).join('')}
            </div>
        </div>
    `;
    note.textContent = finalBenchmarkN20.throughputNote;
}

function renderReductionChart(dataset) {
    const container = document.getElementById('chart-reduction');
    const note = document.getElementById('note-reduction');
    if (!container || !note) return;

    const data = datasetData(dataset).reduction;
    const reduced = data.reduced ?? data.original - data.effective;
    const reductionRate = data.reductionRate ?? 1 - data.effective / data.original;
    container.innerHTML = `
        <div class="plot-frame">
            <div class="token-flow token-flow--simple">
                <div class="tf-stage">
                    <div class="tf-label">${data.originalLabel}</div>
                    <div class="tf-value">${formatTokens(data.original)}</div>
                    <div class="tf-unit">TOKENS / SAMPLE</div>
                </div>
                <div class="tf-arrow"><div class="tf-arrow-icon">→</div></div>
                <div class="tf-stage bg-cyan">
                    <div class="tf-label">${data.effectiveLabel}</div>
                    ${data.effectiveSublabel ? `<div class="tf-sub">${data.effectiveSublabel}</div>` : ''}
                    <div class="tf-value">${formatTokens(data.effective)}</div>
                    <div class="tf-unit">TOKENS / SAMPLE</div>
                </div>
            </div>
            <div class="tf-overall token-reduction-summary">
                <strong>${formatTokens(data.original)} → ${formatTokens(data.effective)} TOKENS</strong>
                <span>−${formatTokens(reduced)} TOKENS · −${(reductionRate * 100).toFixed(2)}%</span>
            </div>
        </div>
    `;
    note.textContent = data.note;
}

function renderQualityChart(dataset) {
    const container = document.getElementById('chart-quality');
    const note = document.getElementById('note-quality');
    if (!container || !note) return;

    const data = datasetData(dataset).quality;
    container.innerHTML = `
        <div class="plot-frame quality-plot-frame">
            <div class="panel">
                <h4>${dataset.toUpperCase()} — ${data.metric}</h4>
                <div class="quality-bars">
                    ${data.values.map((row) => `
                        <div class="q-row">
                            <span class="q-label">${row.name}</span>
                            <div class="q-track">
                                <div class="q-fill" style="width: ${(row.value / data.scaleMaximum) * 100}%"></div>
                            </div>
                            <span class="q-val">${row.display}</span>
                        </div>
                    `).join('')}
                </div>
            </div>
        </div>
    `;
    note.textContent = data.note;
}

function renderLatencyChart(dataset) {
    const container = document.getElementById('chart-latency');
    const note = document.getElementById('note-latency');
    if (!container || !note) return;

    const data = datasetData(dataset).latency;
    const maxValue = Math.max(data.dflash.total, data.ccdflash.total) * 1.05;
    container.innerHTML = `
        <div class="plot-frame">
            <div class="latency-legend">
                <span class="leg-item"><span class="leg-box leg-comp"></span> Compression</span>
                <span class="leg-item"><span class="leg-box leg-gen"></span> Generation</span>
            </div>
            <div class="stacked-bars">
                <div class="st-row">
                    <span class="st-label">DFlash-R1</span>
                    <div class="st-track">
                        <div class="st-seg st-gen" style="width: ${(data.dflash.generation / maxValue) * 100}%"></div>
                    </div>
                    <span class="st-val">${data.dflash.total.toFixed(2)} ms</span>
                </div>
                <div class="st-row">
                    <span class="st-label">CC-DFlash-R2</span>
                    <div class="st-track">
                        <div class="st-seg st-comp" title="Compression ${data.ccdflash.compression.toFixed(2)} ms" style="width: ${(data.ccdflash.compression / maxValue) * 100}%"></div>
                        <div class="st-seg st-gen" title="Generation ${data.ccdflash.generation.toFixed(2)} ms" style="width: ${(data.ccdflash.generation / maxValue) * 100}%"></div>
                    </div>
                    <span class="st-val">${data.ccdflash.total.toFixed(2)} ms</span>
                </div>
            </div>
            <div class="latency-delta-wrap">
                <div class="latency-delta">+${data.deltaMs.toFixed(2)} ms · +${(data.deltaRate * 100).toFixed(2)}% slower</div>
            </div>
        </div>
    `;
    note.textContent = finalBenchmarkN20.latencyNote;
}

function renderBenchmarkIdentity() {
    const heading = document.getElementById('evidence-heading');
    const sampleSize = document.getElementById('evidence-sample-size');
    const conclusions = document.getElementById('evidence-conclusion-list');
    if (heading) heading.textContent = finalBenchmarkN20.label;
    if (sampleSize) sampleSize.textContent = finalBenchmarkN20.sampleSize;
    if (conclusions) {
        conclusions.innerHTML = finalBenchmarkN20.conclusions.map((conclusion, index) => `
            <li>
                <span class="icon ${index === 2 || index === 4 ? 'warn' : ''}">${index === 2 || index === 4 ? '⚠' : '✓'}</span>
                ${conclusion}
            </li>
        `).join('');
    }
}

function syncToggleState(dataset) {
    document.querySelectorAll('.card-toggles .tgl-btn').forEach((button) => {
        if (!(button instanceof HTMLButtonElement)) return;
        button.classList.toggle('active', button.dataset.ds === dataset);
    });
}

function renderAllPanels(dataset) {
    renderThroughputChart(dataset);
    renderReductionChart(dataset);
    renderQualityChart(dataset);
    renderLatencyChart(dataset);
    syncToggleState(dataset);
}

function bindToggles() {
    document.querySelectorAll('.card-toggles .tgl-btn').forEach((button) => {
        if (!(button instanceof HTMLButtonElement)) return;
        button.addEventListener('click', () => renderAllPanels(button.dataset.ds));
    });
}

export function initEvidenceCharts() {
    renderBenchmarkIdentity();
    renderAllPanels('gsm8k');
    bindToggles();
}
