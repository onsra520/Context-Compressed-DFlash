const fs = require('fs');

let js = fs.readFileSync('scripts/architecture-graph.js', 'utf-8');

// Update selectors
const selectorsOld = `    const stepTitle = document.getElementById('stepTitle');
    const stepDesc = document.getElementById('stepDesc');
    const stepIndicator = document.getElementById('stepIndicator');
    const traceMetric = document.getElementById('traceMetric');
    const contextBox = document.getElementById('contextBox');
    const processBox = document.getElementById('processBox');
    const payloadBox = document.getElementById('payloadBox');`;

const selectorsNew = `    const stepTitle = document.getElementById('stepTitle');
    const stepDesc = document.getElementById('stepDesc');
    const stepIndicator = document.getElementById('stepIndicator');
    const traceMetric = document.getElementById('prompt-trace-metric');
    const traceInput = document.getElementById('prompt-trace-input');
    const traceOperation = document.getElementById('prompt-trace-operation');
    const traceOutput = document.getElementById('prompt-trace-output');`;
// Since the old file doesn't have traceMetric (it wasn't successfully updated), I'll just use a broader replace block
const selStart = `    const stepTitle = document.getElementById('stepTitle');`;
const selEnd = `    const logBox = document.getElementById('logBox');`;
const selRegex = new RegExp(selStart.replace(/[.*+?^\${}()|[\\]\\\\]/g, '\\\\$&') + '[\\\\s\\\\S]*?' + selEnd.replace(/[.*+?^\${}()|[\\]\\\\]/g, '\\\\$&'));

const selNew = `    const stepTitle = document.getElementById('stepTitle');
    const stepDesc = document.getElementById('stepDesc');
    const stepIndicator = document.getElementById('stepIndicator');
    const traceMetric = document.getElementById('prompt-trace-metric');
    const traceInput = document.getElementById('prompt-trace-input');
    const traceOperation = document.getElementById('prompt-trace-operation');
    const traceOutput = document.getElementById('prompt-trace-output');
    
    const zoomLevel = document.getElementById('zoomLevel');
    const logBox = document.getElementById('logBox');`;

js = js.replace(selRegex, selNew);

// Fallback selector replace if it failed to match (it still uses querySelector)
const fallbackSel = /const stepTitle = document\.querySelector\('\.insp-node-title'\) \|\| document\.getElementById\('stepTitle'\);[\s\S]*?const progressText = document\.querySelector\('\.insp-progress-text'\);/;
if (js.match(fallbackSel)) {
    js = js.replace(fallbackSel, selNew);
}

// Update renderStep
const renderStart = `if (stepTitle) stepTitle.textContent = step.title;`;
const renderEnd = `if (payloadBox) payloadBox.textContent = step.output || '—';`;
const renderRegex = new RegExp(renderStart.replace(/[.*+?^\${}()|[\\]\\\\]/g, '\\\\$&') + '[\\\\s\\\\S]*?' + renderEnd.replace(/[.*+?^\${}()|[\\]\\\\]/g, '\\\\$&'));

const renderNew = `if (stepTitle) stepTitle.textContent = step.title;
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
        }`;

js = js.replace(renderRegex, renderNew);

// Remove the old if (stepIndicator) block
const stepIndRegex = /if \(stepIndicator\) \{\s*const stepNumStr = \(index \+ 1\)\.toString\(\)\.padStart\(2, '0'\);\s*stepIndicator\.textContent = `STEP \$\{stepNumStr\} \/ \$\{architectureSteps\.length\}`;\s*\}/g;
js = js.replace(stepIndRegex, '');

// Update resetGraph
const resetStart = `    function resetGraph() {`;
const resetEnd = `fitGraph();\n    }`;
const resetRegex = new RegExp(resetStart.replace(/[.*+?^\${}()|[\\]\\\\]/g, '\\\\$&') + '[\\\\s\\\\S]*?' + resetEnd.replace(/[.*+?^\${}()|[\\]\\\\]/g, '\\\\$&'));

const resetNew = `    function resetGraph() {
        cancelPlayback();
        currentStep = 0;
        clearHighlights();
        packet.classList.remove('visible');
        renderStep(0, { log: false });
        fitGraph();
    }`;
js = js.replace(resetRegex, resetNew);

// In initGraph, change renderStep(-1) to renderStep(0)
js = js.replace("renderStep(-1, { log: false });", "renderStep(0, { log: false });");

// Update Prev check
js = js.replace("if (index < 0 || index >= architectureSteps.length) return;", "if (index < 0 || index >= architectureSteps.length) return;"); // just sanity
js = js.replace("if (index < 0) {", "if (index < 0) {"); // Old init check? Let's just remove any if(index<0) inside renderStep
const oldInitStart = `if (index < 0) {`;
const oldInitEnd = `if (stepIndicator) stepIndicator.textContent = \`STEP 00 / \${architectureSteps.length}\`;\n        }`;
const oldInitRegex = new RegExp(oldInitStart.replace(/[.*+?^\${}()|[\\]\\\\]/g, '\\\\$&') + '[\\\\s\\\\S]*?' + oldInitEnd.replace(/[.*+?^\${}()|[\\]\\\\]/g, '\\\\$&'));
js = js.replace(oldInitRegex, '');

fs.writeFileSync('scripts/architecture-graph.js', js);
console.log('Updated architecture-graph.js comprehensively.');
