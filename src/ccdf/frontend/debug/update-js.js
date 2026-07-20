const fs = require('fs');
let js = fs.readFileSync('scripts/architecture-graph.js', 'utf-8');

const newEdges = `    const activeEdgesByStep = {
        0: [],
        1: ['original-to-context-compression'],
        2: ['segmenter-to-llmlingua'],
        3: ['segmenter-to-protected-question'],
        4: ['context-compression-to-prompt-compression'],
        5: ['prompt-compression-to-target-prefill', 'target-prefill-to-dflash-container'],
        6: ['output-buffer-to-draft-loop'],
        7: ['draft-to-verify'],
        8: ['verify-to-output-buffer', 'output-buffer-to-draft-loop'],
        9: ['dflash-container-to-final-output']
    };`;

js = js.replace(/const activeEdgesByStep = {[\s\S]*?};/, newEdges);

fs.writeFileSync('scripts/architecture-graph.js', js);
console.log('architecture-graph.js updated successfully.');
