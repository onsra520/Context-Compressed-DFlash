const fs = require('fs');
let js = fs.readFileSync('scripts/architecture-graph.js', 'utf8');

// Replace population logic
const popRegex = /\/\/ Populate node contents dynamically[\s\S]*?if \(mergeNode\) mergeNode\.innerHTML = demoData\.finalCompressedPrompt\.replace\(\/\\n\/g, '<br>'\);/;
const popReplacement = `// Populate node contents dynamically from demoData
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
    if (mergeNode) mergeNode.textContent = demoData.finalCompressedPrompt;`;

js = js.replace(popRegex, popReplacement);

// Replace fitGraph logic
const fitRegex = /function fitGraph\(\) \{[\s\S]*?applyTransform\(\);\n    \}/;
const fitReplacement = `function fitGraph() {
        const viewportRect = graphViewport.getBoundingClientRect();
        const sceneWidth = 2600;
        const sceneHeight = 1200;
        const safeLeft = viewportRect.width > 900 ? 345 : 0;
        const availableWidth = viewportRect.width - safeLeft;
        
        let fitScale = Math.min(availableWidth / sceneWidth, viewportRect.height / sceneHeight);
        scale = Math.min(1.8, Math.max(0.75, fitScale));
        
        if (scale > fitScale) {
            translateX = safeLeft + 40;
            translateY = Math.max(0, (viewportRect.height - sceneHeight * scale) / 2 + 100);
        } else {
            translateX = safeLeft + (availableWidth - sceneWidth * scale) / 2;
            translateY = (viewportRect.height - sceneHeight * scale) / 2;
        }
        applyTransform();
    }`;

js = js.replace(fitRegex, fitReplacement);

// Replace current node card rendering
// We need to keep the badge icon if we want.
// Wait, the user said: "NODE HIỆN TẠI... Bổ sung badge đồng bộ với node graph... [badge] TITLE... Mô tả tiếng Việt"
// Let's check how the current step card is updated.
const cardRegex = /if \(stepTitle\) stepTitle\.textContent = step\.title;\n\s*if \(stepDesc\) stepDesc\.textContent = step\.description;\n\s*if \(stepIndicator\) stepIndicator\.textContent = `STEP \$\{stepNumStr\} \/ \$\{architectureSteps\.length - 1\}`;/;
const cardReplacement = `if (stepTitle) {
            const svgIcon = document.querySelector(\`#\${step.node} .icon\`)?.innerHTML || '';
            stepTitle.innerHTML = \`<div style="display: flex; align-items: center; gap: 8px;">
                <div style="width: 24px; height: 24px; display: grid; place-items: center; border: 2px solid #111; box-shadow: 2px 2px 0 #111; background: #fff; border-radius: 2px;">\${svgIcon}</div>
                <span>\${step.title}</span>
            </div>\`;
        }
        if (stepDesc) stepDesc.textContent = step.description;
        if (stepIndicator) stepIndicator.textContent = \`STEP \${stepNumStr} / \${architectureSteps.length - 1}\`;`;

js = js.replace(cardRegex, cardReplacement);

fs.writeFileSync('scripts/architecture-graph.js', js);
console.log("Success JS");
