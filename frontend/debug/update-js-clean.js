const fs = require('fs');
let js = fs.readFileSync('scripts/architecture-graph.js', 'utf-8');

// 1. Selectors
const selOld = /const stepTitle[\s\S]*?const zoomLevel = document\.getElementById\('zoomLevel'\);/;
const selNew = `const stepTitle = document.getElementById('stepTitle');
    const stepDesc = document.getElementById('stepDesc');
    const stepIndicator = document.getElementById('stepIndicator');
    const traceMetric = document.getElementById('prompt-trace-metric');
    const traceInput = document.getElementById('prompt-trace-input');
    const traceOperation = document.getElementById('prompt-trace-operation');
    const traceOutput = document.getElementById('prompt-trace-output');
    const logBox = document.getElementById('logBox');
    const zoomLevel = document.getElementById('zoomLevel');`;
js = js.replace(selOld, selNew);

// 2. fitGraph
const fitOld = /function fitGraph\(\) \{[\s\S]*?applyTransform\(\);\n    \}/;
const fitNew = `function fitGraph() {
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
    }`;
js = js.replace(fitOld, fitNew);

// 3. Remove activeEdgesByStep and update renderStep
const edgesRegex = /const activeEdgesByStep = \{[\s\S]*?\};\n/;
js = js.replace(edgesRegex, '');

const renderOld = /function renderStep\(index, \{ log = true \} = \{\}\) \{[\s\S]*?\}\n\n    function cancelPlayback/;
const renderNew = `function renderStep(index, { log = true } = {}) {
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
            stepIndicator.textContent = \`STEP \${stepNumStr} / \${architectureSteps.length - 1}\`;
        }

        if (step.trace) {
            if (traceMetric) traceMetric.textContent = step.trace.metric;
            if (traceInput) traceInput.innerHTML = step.trace.input.replace(/\\n/g, '<br>');
            if (traceOperation) traceOperation.textContent = step.trace.operation;
            if (traceOutput) traceOutput.innerHTML = step.trace.output.replace(/\\n/g, '<br>');
        }

        const accentVar = step.accent ? \`var(--\${step.accent})\` : 'var(--cyan)';
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

    function cancelPlayback`;
js = js.replace(renderOld, renderNew);

// 4. resetGraph
const resetOld = /function resetGraph\(\) \{[\s\S]*?fitGraph\(\);\n    \}/;
const resetNew2 = `function resetGraph() {
        cancelPlayback();
        currentStep = 0;
        clearHighlights();
        packet.classList.remove('visible');
        renderStep(0, { log: false });
        fitGraph();
    }`;
js = js.replace(resetOld, resetNew2);

// 5. initial renderStep call in initGraph
// Actually, earlier in initGraph there might be `resetGraph();` or something. Let's see later lines.
// There is `resetGraph();` and then returning controls. Wait, the old file has it.

fs.writeFileSync('scripts/architecture-graph.js', js);
console.log('Successfully rebuilt architecture-graph.js from scratch.');
