import { mockResults } from '../mocks/mock-results.js';

function renderThroughputChart(dataset) {
    const container = document.getElementById('chart-throughput');
    if (!container) return;
    
    const data = mockResults.throughput[dataset];
    const maxVal = Math.max(...data.map(d => d.value)) * 1.1; // Add 10% padding
    
    container.innerHTML = `
        <div class="plot-frame">
            <div class="bar-chart bar-chart--vertical">
                ${data.map(d => {
                    let highlightClass = '';
                    if (d.name.includes("DFlash-R1")) highlightClass = 'highlight-cyan';
                    if (d.name.includes("CC-DFlash-R2")) highlightClass = 'highlight-magenta';
                    return `
                    <div class="bar-col">
                        <div class="bar-val">${d.value.toFixed(1)}</div>
                        <div class="bar-track">
                            <div class="bar-fill ${highlightClass}" style="height: ${(d.value / maxVal) * 100}%"></div>
                        </div>
                        <div class="bar-label">${d.name.replace('-R', '\n-R')}</div>
                    </div>
                    `;
                }).join('')}
            </div>
        </div>
    `;
}

function renderReductionChart(dataset) {
    const container = document.getElementById('chart-reduction');
    const note = document.getElementById('note-reduction');
    if (!container || !note) return;
    
    if (dataset === 'gsm8k') {
        const d = mockResults.tokenReduction.gsm8k;
        const cleanupPct = Math.abs(d.promptCleanupPct);
        const lingPct = Math.abs(d.llmlinguaReductionPct);
        const overallPct = Math.abs((d.afterSafeguard - d.oldPrompt) / d.oldPrompt * 100).toFixed(1);
        
        container.innerHTML = `
            <div class="plot-frame">
                <div class="token-flow">
                    <div class="tf-stage">
                        <div class="tf-label">ORIGINAL</div>
                        <div class="tf-value">${d.oldPrompt}</div>
                        <div class="tf-unit">TOKENS</div>
                        <div class="tf-sub">Old prompt</div>
                    </div>
                    <div class="tf-arrow">
                        <div class="tf-arrow-icon">→</div>
                        <div class="tf-chip">-${cleanupPct}%<span>Prompt cleanup</span></div>
                    </div>
                    <div class="tf-stage bg-cyan">
                        <div class="tf-label">PROMPT V5</div>
                        <div class="tf-value">${d.v5Prompt}</div>
                        <div class="tf-unit">TOKENS</div>
                        <div class="tf-sub">Shared instruction</div>
                    </div>
                    <div class="tf-arrow">
                        <div class="tf-arrow-icon">→</div>
                        <div class="tf-chip bg-yellow">-${lingPct}%<span>LLMLingua</span></div>
                    </div>
                    <div class="tf-stage bg-yellow">
                        <div class="tf-label">SAFEGUARDED</div>
                        <div class="tf-value">${d.afterSafeguard}</div>
                        <div class="tf-unit">TOKENS</div>
                        <div class="tf-sub">Compressed input</div>
                    </div>
                </div>
                <div class="tf-overall">
                    OVERALL: ${d.oldPrompt} → ${d.afterSafeguard} TOKENS &middot; -${overallPct}%
                </div>
            </div>
        `;
        note.innerHTML = "SHORT PROMPT: PHẦN GIẢM CHÍNH ĐẾN TỪ PROMPT CLEANUP.";
    } else {
        const d = mockResults.tokenReduction.qmsum;
        const selPct = Math.abs(d.selectionReductionPct).toFixed(1);
        const lingPct = Math.abs(d.llmlinguaReductionPct).toFixed(1);
        const overallPct = Math.abs(d.overallReductionPct).toFixed(1);
        
        container.innerHTML = `
            <div class="plot-frame">
                <div class="token-flow">
                    <div class="tf-stage">
                        <div class="tf-label">FULL</div>
                        <div class="tf-value">${d.fullTranscript.toLocaleString()}</div>
                        <div class="tf-unit">TOKENS</div>
                        <div class="tf-sub">Full transcript</div>
                    </div>
                    <div class="tf-arrow">
                        <div class="tf-arrow-icon">→</div>
                        <div class="tf-chip">-${selPct}%<span>Context selection</span></div>
                    </div>
                    <div class="tf-stage bg-cyan">
                        <div class="tf-label">SELECTED</div>
                        <div class="tf-value">${d.selectedContext.toLocaleString()}</div>
                        <div class="tf-unit">TOKENS</div>
                        <div class="tf-sub">Query-aware context</div>
                    </div>
                    <div class="tf-arrow">
                        <div class="tf-arrow-icon">→</div>
                        <div class="tf-chip bg-yellow">-${lingPct}%<span>LLMLingua</span></div>
                    </div>
                    <div class="tf-stage bg-magenta">
                        <div class="tf-label">COMPRESSED</div>
                        <div class="tf-value">${d.compressedContext.toLocaleString()}</div>
                        <div class="tf-unit">TOKENS</div>
                        <div class="tf-sub">Target input</div>
                    </div>
                </div>
                <div class="tf-overall bg-purple">
                    OVERALL: ${d.fullTranscript.toLocaleString()} → ${d.compressedContext.toLocaleString()} TOKENS &middot; -${overallPct}%
                </div>
            </div>
        `;
        note.innerHTML = "LONG CONTEXT: PHẦN GIẢM CHÍNH ĐẾN TỪ QUERY-AWARE SELECTION.";
    }
}

function renderQualityChart(dataset) {
    const container = document.getElementById('chart-quality');
    const note = document.getElementById('note-quality');
    if (!container || !note) return;
    
    if (dataset === 'gsm8k') {
        const data = mockResults.quality.gsm8k;
        container.innerHTML = `
            <div class="plot-frame" style="padding: 0;">
                <div class="panel">
                    <h4>GSM8K — Numeric Exact Match</h4>
                    <div class="quality-bars">
                        ${data.map(d => `
                            <div class="q-row">
                                <span class="q-label">${d.name}</span>
                                <div class="q-track">
                                    <div class="q-seg filled" style="width: ${(d.value / d.total) * 100}%"></div>
                                    <div class="q-seg" style="width: ${((d.total - d.value) / d.total) * 100}%"></div>
                                </div>
                                <span class="q-val">${d.value}/${d.total}</span>
                            </div>
                        `).join('')}
                    </div>
                </div>
            </div>
        `;
        note.innerHTML = "Compression giữ quality ngang target baseline trong thiết lập mock.";
    } else {
        const data = mockResults.quality.qmsum;
        const minVal = 0.170;
        const maxVal = 0.185;
        container.innerHTML = `
            <div class="plot-frame" style="padding: 0;">
                <div class="panel">
                    <h4>QMSum — Lexical Overlap Proxy</h4>
                    <div class="quality-bars">
                        ${data.map(d => `
                            <div class="q-row">
                                <span class="q-label">${d.name}</span>
                                <div class="q-track"><div class="q-fill" style="width: ${((d.value - minVal) / (maxVal - minVal)) * 100}%"></div></div>
                                <span class="q-val">${d.value.toFixed(3)}</span>
                            </div>
                        `).join('')}
                    </div>
                </div>
            </div>
        `;
        note.innerHTML = "Lexical diagnostic proxy — không đại diện cho semantic correctness.";
    }
}

function renderLatencyChart(dataset) {
    const container = document.getElementById('chart-latency');
    const note = container?.nextElementSibling;
    if (!container) return;
    
    const d = mockResults.latency[dataset];
    
    if (dataset === 'gsm8k') {
        const maxVal = Math.max(d.dflash.total, d.ccdflash.total) * 1.1;
        
        container.innerHTML = `
            <div class="plot-frame">
                <div class="latency-legend">
                    <span class="leg-item"><span class="leg-box leg-comp"></span> Compression</span>
                    <span class="leg-item"><span class="leg-box leg-prefill"></span> Prefill</span>
                    <span class="leg-item"><span class="leg-box leg-gen"></span> Generation</span>
                </div>
                <div class="stacked-bars">
                    <div class="st-row">
                        <span class="st-label">DFlash-R1</span>
                        <div class="st-track">
                            <div class="st-seg st-prefill" style="width: ${(d.dflash.prefill / maxVal) * 100}%"></div>
                            <div class="st-seg st-gen" style="width: ${(d.dflash.generation / maxVal) * 100}%"></div>
                        </div>
                        <span class="st-val">${d.dflash.total} ms</span>
                    </div>
                    <div class="st-row">
                        <span class="st-label">CC-DFlash-R2</span>
                        <div class="st-track">
                            <div class="st-seg st-comp" style="width: ${(d.ccdflash.compression / maxVal) * 100}%"></div>
                            <div class="st-seg st-prefill" style="width: ${(d.ccdflash.prefill / maxVal) * 100}%"></div>
                            <div class="st-seg st-gen" style="width: ${(d.ccdflash.generation / maxVal) * 100}%"></div>
                        </div>
                        <span class="st-val">${d.ccdflash.total} ms</span>
                    </div>
                </div>
                <div class="latency-delta-wrap"><div class="latency-delta">+${d.deltaMs} ms (+${d.deltaPct}%) slower</div></div>
            </div>
        `;
    } else {
        const maxVal = Math.max(d.dflash.total, d.ccdflash.total) * 1.1;
        
        container.innerHTML = `
            <div class="plot-frame">
                <div class="latency-legend">
                    <span class="leg-item"><span class="leg-box leg-comp"></span> Compression</span>
                    <span class="leg-item"><span class="leg-box leg-gen"></span> Generation Pipeline</span>
                </div>
                <div class="stacked-bars">
                    <div class="st-row">
                        <span class="st-label">DFlash-R1</span>
                        <div class="st-track">
                            <div class="st-seg st-gen" style="width: ${(d.dflash.generationPipeline / maxVal) * 100}%"></div>
                        </div>
                        <span class="st-val">${d.dflash.total} ms</span>
                    </div>
                    <div class="st-row">
                        <span class="st-label">CC-DFlash-R2</span>
                        <div class="st-track">
                            <div class="st-seg st-comp" style="width: ${(d.ccdflash.compression / maxVal) * 100}%"></div>
                            <div class="st-seg st-gen" style="width: ${(d.ccdflash.generationPipeline / maxVal) * 100}%"></div>
                        </div>
                        <span class="st-val">${d.ccdflash.total} ms</span>
                    </div>
                </div>
                <div class="latency-delta-wrap"><div class="latency-delta">+${d.deltaMs} ms (+${d.deltaPct}%) slower</div></div>
            </div>
        `;
    }
    
    if (note && note.classList.contains('evidence-note')) {
        note.innerHTML = "Decode can improve while end-to-end still loses to compression overhead.";
    }
}

function renderKPIStrip() {
    const container = document.getElementById('kpi-strip');
    if (!container) return;
    
    const d = mockResults.kpi;
    container.innerHTML = `
        <div class="kpi-card">
            <div class="kpi-val">${d.vram}</div>
            <div class="kpi-label">Peak Reserved VRAM</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-val">${d.acceptanceLength} <span class="kpi-badge">diagnostic</span></div>
            <div class="kpi-label">Mean Acceptance Length τ</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-val">${d.compressionFallback}</div>
            <div class="kpi-label">Compression Fallback</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-val">${d.parserFailures}</div>
            <div class="kpi-label">Parser Failures</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-val">${d.emptyOutputs}</div>
            <div class="kpi-label">Empty Outputs</div>
        </div>
    `;
}

function bindToggles() {
    document.querySelectorAll('.card-toggles').forEach(toggles => {
        const btns = toggles.querySelectorAll('.tgl-btn');
        btns.forEach(btn => {
            btn.addEventListener('click', (e) => {
                btns.forEach(b => b.classList.remove('active'));
                e.target.classList.add('active');
                
                const ds = e.target.dataset.ds;
                const card = e.target.closest('.evidence-card');
                
                if (card.id === 'card-throughput') renderThroughputChart(ds);
                if (card.id === 'card-reduction') renderReductionChart(ds);
                if (card.id === 'card-quality') renderQualityChart(ds);
                if (card.id === 'card-latency') renderLatencyChart(ds);
            });
        });
    });
}

export function initEvidenceCharts() {
    renderThroughputChart('gsm8k');
    renderReductionChart('gsm8k');
    renderQualityChart('gsm8k'); // Default to GSM8K
    renderLatencyChart('qmsum'); // QMSum default for latency
    renderKPIStrip();
    bindToggles();
}

