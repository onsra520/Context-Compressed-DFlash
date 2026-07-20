const fs = require('fs');
let js = fs.readFileSync('scripts/architecture-graph.js', 'utf-8');

// 1. Update query selectors
const selectorsOld = `    const stepTitle = document.querySelector('.insp-node-title') || document.getElementById('stepTitle');
    const stepDesc = document.querySelector('.insp-desc') || document.getElementById('stepDesc');
    const cycleChip = document.querySelector('.insp-badge--stage') || document.getElementById('cycleChip');
    const cycleLabel = document.querySelector('.insp-badge--state') || document.getElementById('cycleLabel');
    const containerBadge = document.getElementById('containerCycleBadge');
    const contextBox = document.querySelector('.insp-box--input') || document.getElementById('contextBox');
    const processBox = document.querySelector('.insp-box--process');
    const eventBox = document.querySelector('.insp-box--event');
    const payloadBox = document.querySelector('.insp-box--output') || document.getElementById('payloadBox');
    const resultBox = document.getElementById('resultBox');
    const logBox = document.getElementById('logBox');
    const bar = document.querySelector('.insp-bar') || document.getElementById('bar');
    const zoomLevel = document.getElementById('zoomLevel');
    const stepIndicator = document.querySelector('.insp-step');
    const progressText = document.querySelector('.insp-progress-text');`;

const selectorsNew = `    const stepTitle = document.getElementById('stepTitle');
    const stepDesc = document.getElementById('stepDesc');
    const stepIndicator = document.getElementById('stepIndicator');
    const traceMetric = document.getElementById('traceMetric');
    const contextBox = document.getElementById('contextBox');
    const processBox = document.getElementById('processBox');
    const payloadBox = document.getElementById('payloadBox');
    const containerBadge = document.getElementById('containerCycleBadge');
    
    const zoomLevel = document.getElementById('zoomLevel');
    const logBox = document.getElementById('logBox');`;
js = js.replace(selectorsOld, selectorsNew);

// 2. Update renderStep DOM assignments
const renderStart = `if (stepTitle) stepTitle.textContent = step.title;`;
const renderEnd = `if (bar) bar.style.width = \`\${((index + 1) / architectureSteps.length) * 100}%\`;`;
const renderRegex = new RegExp(renderStart.replace(/[.*+?^\${}()|[\\]\\\\]/g, '\\\\$&') + '[\\\\s\\\\S]*?' + renderEnd.replace(/[.*+?^\${}()|[\\]\\\\]/g, '\\\\$&'));

const renderNew = `if (stepTitle) stepTitle.textContent = step.title;
        if (stepDesc) stepDesc.textContent = step.description;
        
        if (stepIndicator) {
            const stepNumStr = (index).toString().padStart(2, '0');
            stepIndicator.textContent = \`STEP \${stepNumStr} / \${architectureSteps.length - 1}\`;
        }

        if (traceMetric) traceMetric.textContent = step.metric || '';
        if (contextBox) contextBox.innerHTML = (step.inputPreview || '').replace(/\\n/g, '<br>');
        if (processBox) processBox.textContent = step.operation || '';
        if (payloadBox) payloadBox.innerHTML = (step.outputPreview || '').replace(/\\n/g, '<br>');

        if (containerBadge) {
            if (step.cycleBadge) {
                containerBadge.style.display = 'block';
                containerBadge.textContent = 'CYCLE: ' + step.cycleBadge.replace('CYCLE ', '');
            } else {
                containerBadge.style.display = 'none';
            }
        }
        
        const accentVar = step.accent ? \`var(--\${step.accent})\` : 'var(--cyan)';
        if (traceMetric) traceMetric.style.background = accentVar;
        if (stepIndicator) stepIndicator.style.background = accentVar;
        if (contextBox) contextBox.style.borderLeftColor = accentVar;
        if (payloadBox) payloadBox.style.borderLeftColor = accentVar;
        if (processBox) processBox.style.color = accentVar;`;

js = js.replace(renderRegex, renderNew);

// Wait, step numbering is 0 to 15 or 1 to 16? The user said: "STEP 00 / 16". So (index + 1).
js = js.replace("const stepNumStr = (index).toString().padStart(2, '0');", "const stepNumStr = (index).toString().padStart(2, '0');"); // Wait, Step 00? If index is 0, it will be "STEP 00". User said: "STEP 00 / 16" for step 0. So index.toString() is exactly 00!
js = js.replace("\${architectureSteps.length - 1}", "\${architectureSteps.length}"); // "00 / 16" means length is 16.

// 3. Remove index < 0 fallback in renderStep entirely or change it to fallback to renderStep(0)? 
// Actually, I should just modify where renderStep(-1) is called and replace the inner if(index < 0) block.
const initStart = `if (index < 0) {`;
const initEnd = `if (stepIndicator) stepIndicator.textContent = \`STEP 00 / \${architectureSteps.length}\`;
        }`;
const initRegex = new RegExp(initStart.replace(/[.*+?^\${}()|[\\]\\\\]/g, '\\\\$&') + '[\\\\s\\\\S]*?' + initEnd.replace(/[.*+?^\${}()|[\\]\\\\]/g, '\\\\$&'));

// We can just remove the if (index < 0) block because we will never call renderStep(-1). We will call renderStep(0).
js = js.replace(initRegex, '');

// Also replace `if (index < 0 || index >= architectureSteps.length) return;` 
// with `if (index < 0 || index >= architectureSteps.length) return;` (keep it, but index will be 0)

// 4. Update initGraph to call renderStep(0) instead of renderStep(-1)
js = js.replace("renderStep(-1, { log: false });", "renderStep(0, { log: false });");

// 5. Update fitGraph to reserve left space
const fitOld = `    function fitGraph() {
        const viewportRect = graphViewport.getBoundingClientRect();
        const sceneWidth = 2200;
        const sceneHeight = 1000;
        const fitScale = Math.min(viewportRect.width / sceneWidth, viewportRect.height / sceneHeight);
        scale = Math.min(1.8, Math.max(0.3, fitScale));
        translateX = (viewportRect.width - sceneWidth * scale) / 2;
        translateY = (viewportRect.height - sceneHeight * scale) / 2;
        applyTransform();
    }`;

const fitNew = `    function fitGraph() {
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

// 6. Update Reset button
js = js.replace("renderStep(-1);", "renderStep(0);");

fs.writeFileSync('scripts/architecture-graph.js', js);
console.log('Updated architecture-graph.js');
