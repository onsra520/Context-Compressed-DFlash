import { architectureSteps } from '../mocks/mock-data.js';

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
    const packet = document.getElementById('packet');
    const stepTitle = document.getElementById('stepTitle');
    const stepDesc = document.getElementById('stepDesc');
    const stepIndicator = document.getElementById('stepIndicator');
    const traceMetric = document.getElementById('prompt-trace-metric');
    const traceInput = document.getElementById('prompt-trace-input');
    const traceOperation = document.getElementById('prompt-trace-operation');
    const traceOutput = document.getElementById('prompt-trace-output');
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

    function applyTransform() {
        graphScene.style.transform = `translate(${translateX}px, ${translateY}px) scale(${scale})`;
        if (zoomLevel) zoomLevel.textContent = `${Math.round(scale * 100)}%`;
    }

    function fitGraph() {
        const viewportRect = graphViewport.getBoundingClientRect();
        const sceneWidth = 2200;
        const sceneHeight = 1000;
        const safeLeft = viewportRect.width > 900 ? 345 : 0;
        const availableWidth = viewportRect.width - safeLeft;
        const fitScale = Math.min(availableWidth / sceneWidth, viewportRect.height / sceneHeight);
        scale = Math.min(1.8, Math.max(0.3, fitScale));
        translateX = safeLeft + (availableWidth - sceneWidth * scale) / 2;
        translateY = (viewportRect.height - sceneHeight * scale) / 2;
        applyTransform();
    }

    function updatePacket(nodeId, text, immediate = false) {
        const node = document.getElementById(nodeId);
        const x = node.offsetLeft + node.offsetWidth / 2;
        const y = node.offsetTop + node.offsetHeight / 2;
        packet.textContent = text;
        packet.classList.add('visible');
        if (immediate || reduceMotion) packet.style.transition = 'none';
        packet.style.left = `${x}px`;
        packet.style.top = `${y}px`;
        if (immediate || reduceMotion) {
            requestAnimationFrame(() => {
                packet.style.transition = '';
            });
        }
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
        
        const activeEdges = step.activeEdge ? [step.activeEdge] : [];
        activeEdges.forEach(edgeId => {
            document.getElementById(edgeId)?.classList.add('is-active');
        });

        if (stepTitle) stepTitle.textContent = step.title;
        if (stepDesc) stepDesc.textContent = step.description;
        
        if (stepIndicator) {
            const stepNumStr = index.toString().padStart(2, '0');
            stepIndicator.textContent = `STEP ${stepNumStr} / ${architectureSteps.length - 1}`;
        }

        if (step.trace) {
            if (traceMetric) traceMetric.textContent = step.trace.metric;
            if (traceInput) traceInput.innerHTML = step.trace.input.replace(/\n/g, '<br>');
            if (traceOperation) traceOperation.textContent = step.trace.operation;
            if (traceOutput) traceOutput.innerHTML = step.trace.output.replace(/\n/g, '<br>');
        }

        const accentVar = step.accent ? `var(--${step.accent})` : 'var(--cyan)';
        if (traceMetric) traceMetric.style.background = accentVar;
        if (stepIndicator) stepIndicator.style.background = accentVar;
        if (traceInput) traceInput.style.borderLeftColor = accentVar;
        if (traceOutput) traceOutput.style.borderLeftColor = accentVar;
        if (traceOperation) {
            traceOperation.style.color = accentVar;
        }

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
        packet.classList.remove('visible');
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
