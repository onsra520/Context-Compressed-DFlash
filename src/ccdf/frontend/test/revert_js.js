const fs = require('fs');
let js = fs.readFileSync('scripts/architecture-graph.js', 'utf8');

const fitRegex = /function fitGraph\(\) \{[\s\S]*?applyTransform\(\);\n    \}/;
const fitReplacement = `function fitGraph() {
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

js = js.replace(fitRegex, fitReplacement);
fs.writeFileSync('scripts/architecture-graph.js', js);
console.log("Success JS");
