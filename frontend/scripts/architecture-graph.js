import { architectureSteps, demoData } from '../mocks/mock-data.js';

const wait = (ms, signal) => new Promise((resolve) => {
    const timer = window.setTimeout(resolve, ms);
    signal?.addEventListener('abort', () => {
        window.clearTimeout(timer);
        resolve();
    }, { once: true });
});

function tokensMarkup(items, kind = '') {
    return items.map((item) => `<span class="tok ${kind}">${item}</span>`).join('');
}

export function initArchitectureGraph() {
    const graphViewport = document.getElementById('graphViewport');
    const graphScene = document.getElementById('graphScene');
    const stepTitle = document.getElementById('stepTitle');
    const stepDesc = document.getElementById('stepDesc');
    const stepIndicator = document.getElementById('stepIndicator');
    const liveDataFields = document.getElementById('live-data-fields');
    const logBox = document.getElementById('logBox');
    const zoomLevel = document.getElementById('zoomLevel');

    const runBtn = document.getElementById('runBtn');
    const autoBtn = document.getElementById('autoBtn');
    const zoomOutBtn = document.getElementById('zoomOutBtn');
    const zoomInBtn = document.getElementById('zoomInBtn');
    const zoomFitBtn = document.getElementById('zoomFitBtn');

    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    let currentStep = -1;
    let autoPlaying = false;
    let controller = new AbortController();
    let scale = 1;
    let translateX = 0;
    let translateY = 0;
    let dragStart = null;

    const nodes = [...graphScene.querySelectorAll('.node')];
    const edges = [...graphScene.querySelectorAll('.edge')];

    // Populate node contents dynamically from demoData
    const promptNode = document.getElementById('nInput-content');
    if (promptNode) promptNode.textContent = demoData.originalPrompt;

    const splitContextNode = document.getElementById('nSplit-context');
    if (splitContextNode) splitContextNode.textContent = demoData.context;

    const splitProtectedNode = document.getElementById('nSplit-protected');
    if (splitProtectedNode) splitProtectedNode.textContent = demoData.protectedQuestion;

    const compressInputNode = document.getElementById('nCompress-input');
    if (compressInputNode) compressInputNode.textContent = demoData.context;

    const compressOutputNode = document.getElementById('nCompress-output');
    if (compressOutputNode) compressOutputNode.textContent = demoData.compressedContext;

    const protectNode = document.getElementById('nProtect-content');
    if (protectNode) protectNode.textContent = demoData.protectedQuestion;

    const mergeNode = document.getElementById('nMerge-content');
    if (mergeNode) mergeNode.textContent = demoData.finalCompressedPrompt;

    const svgEdges = graphScene.querySelector('svg.edges');

    function applyTransform() {
        graphScene.style.transform = `translate(${translateX}px, ${translateY}px) scale(${scale})`;
        if (zoomLevel) zoomLevel.textContent = `${Math.round(scale * 100)}%`;

    }

    function fitGraph() {
        const viewportRect = graphViewport.getBoundingClientRect();
        const sceneWidth = 2200;
        const sceneHeight = 1700;
        const safeLeft = viewportRect.width > 900 ? 345 : 0;
        const availableWidth = viewportRect.width - safeLeft;
        const fitScale = Math.min(availableWidth / sceneWidth, viewportRect.height / sceneHeight);
        scale = Math.min(1.8, Math.max(0.3, fitScale));
        translateX = safeLeft + (availableWidth - sceneWidth * scale) / 2;
        translateY = (viewportRect.height - sceneHeight * scale) / 2;
        applyTransform();
    }

    function updatePacket(nodeId, text, immediate = false) {
        // Obsolete function, removed
    }

    
    function clearHighlights() {
        nodes.forEach((node) => node.classList.remove('active', 'completed'));
        edges.forEach((edge) => edge.classList.remove('is-active'));
    }

    function addLog(text) {
        const line = document.createElement('div');
        line.textContent = `› ${text}`;
        logBox.prepend(line);
        while (logBox.children.length > 7) logBox.removeChild(logBox.lastElementChild);
    }

    function renderStep(index, { log = true } = {}) {
        if (index < 0 || index >= architectureSteps.length) return;
        currentStep = index;
        const step = architectureSteps[index];

        clearHighlights();
        architectureSteps.slice(0, index).forEach((previous) => {
            document.getElementById(previous.node)?.classList.add('completed');
        });

        document.getElementById(step.node)?.classList.add('active');
        
        const activeEdges = step.activeEdge 
            ? (Array.isArray(step.activeEdge) ? step.activeEdge : [step.activeEdge]) 
            : [];
        activeEdges.forEach(edgeId => {
            document.getElementById(edgeId)?.classList.add('is-active');
        });

        if (stepTitle) stepTitle.textContent = step.title;
        if (stepDesc) stepDesc.textContent = step.description;
        
        if (stepIndicator) {
            const stepNumStr = index.toString().padStart(2, '0');
            stepIndicator.textContent = `STEP ${stepNumStr} / ${architectureSteps.length - 1}`;
        }

        if (liveDataFields) {
            liveDataFields.innerHTML = '';
            if (step.trace) {
                let data = step.trace;
                if (!data["TRẠNG THÁI"] && data.operation) {
                    data = {
                        "TRẠNG THÁI": data.operation,
                        "METRIC": data.metric,
                        "INPUT": data.input,
                        "OUTPUT": data.output
                    };
                }
                Object.entries(data).forEach(([key, value]) => {
                    if (value) {
                        const row = document.createElement('div');
                        row.style.display = 'flex';
                        row.style.flexDirection = 'column';
                        row.style.gap = '2px';
                        
                        const label = document.createElement('span');
                        label.textContent = key;
                        label.style.fontSize = '11px';
                        label.style.fontWeight = '900';
                        label.style.textTransform = 'uppercase';
                        
                        const val = document.createElement('div');
                        val.textContent = value;
                        val.style.background = '#fff';
                        val.style.border = '2px solid #111';
                        val.style.borderLeft = '6px solid var(--cyan)';
                        val.style.padding = '6px 10px';
                        val.style.fontSize = '13px';
                        val.style.fontWeight = '700';
                        
                        const accentVar = step.accent ? `var(--${step.accent})` : 'var(--cyan)';
                        val.style.borderLeftColor = accentVar;
                        
                        row.appendChild(label);
                        row.appendChild(val);
                        liveDataFields.appendChild(row);
                    }
                });
            }
        }
        
        // D-Flash Nodes Update Logic
        const prefillPrefix = document.getElementById('nPrefill-prefix');
        const prefillState = document.getElementById('nPrefill-state');
        const draftSlots = document.getElementById('nDraft-slots');
        const verifySlots = document.getElementById('nVerify-slots');
        const bufferContent = document.getElementById('nBuffer-content');
        
        function renderSlots(container, items) {
            container.innerHTML = items.map(item => {
                if (!item || !item.t) return '<div class="draft-slot empty">&nbsp;</div>';
                let classes = ['draft-slot', item.s].join(' ').trim();
                let html = `<div class="${classes}">${item.t}</div>`;
                if (item.s === 'rejected' && item.c) {
                    html += `<div class="draft-slot corrected">${item.c}</div>`;
                }
                return html;
            }).join('');
        }

        const dflashData = {
            cycle1: {
                prefix: "[Trống - Bắt đầu sinh]",
                state: "Target cache ready",
                draft: [
                    {t: "lyric", s: ""}, {t: "tiếp", s: ""}, {t: "theo", s: ""}, {t: "là", s: ""},
                    {t: "đây", s: ""}, {t: "là", s: ""}, {t: "bài", s: ""}, {t: "này", s: ""}
                ],
                verify: [
                    {t: "lyric", s: "accepted"}, {t: "tiếp", s: "accepted"}, {t: "theo", s: "accepted"}, {t: "là", s: "accepted"},
                    {t: "đây", s: "rejected", c: "Bàn"}, {t: "là", s: "discarded"}, {t: "bài", s: "discarded"}, {t: "này", s: "discarded"}
                ],
                buffer: "lyric tiếp theo là Bàn"
            },
            cycle2: {
                prefix: "lyric tiếp theo là Bàn",
                state: "Updated cache with Cycle 1",
                draft: [
                    {t: "chân", s: ""}, {t: "ai", s: ""}, {t: "chờ", s: ""}, {t: "ai", s: ""},
                    {t: "nghe", s: ""}, {t: "tiếng", s: ""}, {t: "khóc", s: ""}, {t: "trong", s: ""}
                ],
                verify: [
                    {t: "chân", s: "accepted"}, {t: "ai", s: "accepted"}, {t: "chờ", s: "rejected", c: "đợi"}, {t: "ai", s: "discarded"},
                    {t: "nghe", s: "discarded"}, {t: "tiếng", s: "discarded"}, {t: "khóc", s: "discarded"}, {t: "trong", s: "discarded"}
                ],
                buffer: "lyric tiếp theo là Bàn chân ai đợi"
            },
            cycle3: {
                prefix: "lyric tiếp theo là Bàn chân ai đợi",
                state: "Updated cache with Cycle 2",
                draft: [
                    {t: "ai", s: ""}, {t: "nghe", s: ""}, {t: "tiếng", s: ""}, {t: "khóc", s: ""},
                    {t: "trong", s: ""}, {t: "đêm", s: ""}, {t: "dài", s: ""}, {t: "", s: ""}
                ],
                verify: [
                    {t: "ai", s: "accepted"}, {t: "nghe", s: "accepted"}, {t: "tiếng", s: "accepted"}, {t: "khóc", s: "accepted"},
                    {t: "trong", s: "accepted"}, {t: "đêm", s: "accepted"}, {t: "dài", s: "accepted"}, {t: "", s: "empty"}
                ],
                buffer: "lyric tiếp theo là Bàn chân ai đợi ai nghe tiếng khóc trong đêm dài"
            }
        };

        function padSlots(items) {
            const padded = [...items];
            while (padded.length < 40) padded.push({t: "", s: "empty"});
            return padded;
        }

        if (prefillPrefix && draftSlots && verifySlots && bufferContent) {
            const draftLabel = document.getElementById('nDraft-loop-label');
            const verifyLabel = document.getElementById('nVerify-loop-label');
            const finalContent = document.getElementById('nFinal-content');

            if (index < 6) {
                if (draftLabel) draftLabel.textContent = `DRAFT BLOCK — WAITING`;
                if (verifyLabel) verifyLabel.textContent = `VERIFY — WAITING`;
                prefillPrefix.textContent = "[Chờ dữ liệu...]";
                if (prefillState) prefillState.textContent = "[Chờ khởi tạo]";
                
                const emptySlots = padSlots([]);
                renderSlots(draftSlots, emptySlots);
                renderSlots(verifySlots, emptySlots);
                bufferContent.textContent = "[Trống]";
                if (finalContent) finalContent.textContent = "[Đang chờ...]";
            } else {
                let activeCycle = dflashData.cycle1;
                if (step.id.includes('cycle-2')) activeCycle = dflashData.cycle2;
                if (step.id.includes('cycle-3') || step.id === 'buffer-complete' || step.id === 'final-output') activeCycle = dflashData.cycle3;
                
                const cycleNum = step.id.includes('cycle-2') ? 2 : (step.id.includes('cycle-3') || step.id === 'buffer-complete' || step.id === 'final-output' ? 3 : 1);
                
                if (draftLabel) draftLabel.textContent = `DRAFT BLOCK — LOOP ${cycleNum}`;
                if (verifyLabel) verifyLabel.textContent = `VERIFY — LOOP ${cycleNum}`;

                prefillPrefix.textContent = activeCycle.prefix;
                if (prefillState) prefillState.textContent = activeCycle.state;
                
                renderSlots(draftSlots, padSlots(activeCycle.draft));
                
                if (step.id.includes('prefill') || step.id === `draft-cycle-${cycleNum}`) {
                    renderSlots(verifySlots, padSlots(activeCycle.draft.map(d => ({t: d.t, s: 'empty'}))));
                } else {
                    renderSlots(verifySlots, padSlots(activeCycle.verify));
                }
                
                if (step.id === `loop-cycle-${cycleNum}` || step.id === 'buffer-complete' || step.id === 'final-output') {
                    bufferContent.textContent = activeCycle.buffer;
                } else if (cycleNum > 1) {
                    bufferContent.textContent = dflashData[`cycle${cycleNum-1}`].buffer;
                } else {
                    bufferContent.textContent = "[Trống]";
                }
                
                if (finalContent) {
                    if (step.id === 'final-output') {
                        finalContent.textContent = activeCycle.buffer;
                    } else {
                        finalContent.textContent = "[Đang sinh...]";
                    }
                }
            }
        }

        const accentVar = step.accent ? `var(--${step.accent})` : 'var(--cyan)';
        if (stepIndicator) stepIndicator.style.background = accentVar;

        if (prevBtn) prevBtn.disabled = index === 0;
        if (nextBtn) nextBtn.disabled = index === architectureSteps.length - 1;
    }

    function cancelPlayback() {
        controller.abort();
        controller = new AbortController();
        autoPlaying = false;
        if (autoBtn) {
            autoBtn.classList.remove('is-playing');
            autoBtn.textContent = 'Auto Play';
        }
        if (runBtn) runBtn.disabled = false;
    }

    function resetGraph() {
        cancelPlayback();
        currentStep = 0;
        clearHighlights();
        renderStep(0, { log: false });
        fitGraph();
    }

    async function playAll() {
        cancelPlayback();
        const localController = controller;
        runBtn.disabled = true;
        for (let index = 0; index < architectureSteps.length; index += 1) {
            if (localController.signal.aborted) break;
            renderStep(index);
            await wait(reduceMotion ? 120 : 820, localController.signal);
        }
        if (!localController.signal.aborted) runBtn.disabled = false;
    }

    async function autoPlay() {
        if (autoPlaying) {
            cancelPlayback();
            return;
        }
        cancelPlayback();
        autoPlaying = true;
        autoBtn.classList.add('is-playing');
        autoBtn.textContent = 'Pause';
        const localController = controller;
        let index = currentStep < 0 || currentStep >= architectureSteps.length - 1 ? 0 : currentStep + 1;

        while (autoPlaying && !localController.signal.aborted) {
            renderStep(index);
            await wait(reduceMotion ? 220 : 1050, localController.signal);
            index = (index + 1) % architectureSteps.length;
        }
    }

    if (runBtn) runBtn.addEventListener('click', playAll);
    if (autoBtn) autoBtn.addEventListener('click', autoPlay);
    if (resetBtn) resetBtn.addEventListener('click', resetGraph);
    if (nextBtn) nextBtn.addEventListener('click', () => {
        cancelPlayback();
        renderStep(Math.min(currentStep + 1, architectureSteps.length - 1));
    });
    if (prevBtn) prevBtn.addEventListener('click', () => {
        cancelPlayback();
        renderStep(Math.max(currentStep - 1, 0));
    });

    if (zoomInBtn) zoomInBtn.addEventListener('click', () => {
        scale = Math.min(1.8, scale + 0.1);
        applyTransform();
    });
    if (zoomOutBtn) zoomOutBtn.addEventListener('click', () => {
        scale = Math.max(0.55, scale - 0.1);
        applyTransform();
    });
    if (zoomFitBtn) zoomFitBtn.addEventListener('click', fitGraph);

    graphViewport.addEventListener('pointerdown', (event) => {
        if (event.target.closest('button')) return;
        event.preventDefault();
        graphViewport.focus();
        dragStart = {
            x: event.clientX,
            y: event.clientY,
            translateX,
            translateY
        };
        graphViewport.setPointerCapture(event.pointerId);
        graphViewport.classList.add('is-dragging');
    });

    graphViewport.addEventListener('pointermove', (event) => {
        if (!dragStart) return;
        translateX = dragStart.translateX + event.clientX - dragStart.x;
        translateY = dragStart.translateY + event.clientY - dragStart.y;
        requestAnimationFrame(applyTransform);
    });

    const stopDrag = (event) => {
        if (!dragStart) return;
        dragStart = null;
        graphViewport.classList.remove('is-dragging');
        if (graphViewport.hasPointerCapture(event.pointerId)) {
            graphViewport.releasePointerCapture(event.pointerId);
        }
    };
    graphViewport.addEventListener('pointerup', stopDrag);
    graphViewport.addEventListener('pointercancel', stopDrag);

    graphViewport.addEventListener('wheel', (event) => {
        if (!event.ctrlKey) return;
        if (document.activeElement !== graphViewport && !graphViewport.contains(document.activeElement)) return;
        
        event.preventDefault();
        
        const rect = graphViewport.getBoundingClientRect();
        const pointerX = event.clientX - rect.left;
        const pointerY = event.clientY - rect.top;

        const sceneX = (pointerX - translateX) / scale;
        const sceneY = (pointerY - translateY) / scale;

        const delta = event.deltaY > 0 ? -0.1 : 0.1;
        const newScale = Math.min(1.8, Math.max(0.55, scale + delta));

        translateX = pointerX - sceneX * newScale;
        translateY = pointerY - sceneY * newScale;
        scale = newScale;

        applyTransform();
    }, { passive: false });

    graphViewport.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') {
            graphViewport.blur();
            return;
        }
        if (event.key === 'ArrowRight') {
            event.preventDefault();
            cancelPlayback();
            renderStep(Math.min(currentStep + 1, architectureSteps.length - 1));
        }
        if (event.key === 'ArrowLeft') {
            event.preventDefault();
            cancelPlayback();
            renderStep(Math.max(currentStep - 1, 0));
        }
    });

    window.addEventListener('resize', fitGraph);
    resetGraph();
    fitGraph();
}
