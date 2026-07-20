const fs = require('fs');
let html = fs.readFileSync('index.html', 'utf8');

// Remove the NÉN indicator
html = html.replace(/<div class="prompt-sub-card-indicator">↓ NÉN<\/div>\s*/g, '');

// Paths to update in index.html (the edges)
const paths = [
    { old: /d="M \d+ \d+ H \d+"/g, newPattern: 'd="M X Y H Z"' } // We'll just replace the whole edge-group block since it's easier.
];

// Instead of regex replacing all paths which is risky, let's just replace each path explicitly by class and id or order.
const edgePaths = [
    // 1. original-to-context-compression
    'd="M 460 735 H 496"',
    // 2. context-compression-to-prompt-compression
    'd="M 1624 735 H 1660"',
    // 3. prompt-compression-to-target-prefill
    'd="M 2120 735 H 2200"',
    // 4. target-prefill-to-dflash-container
    'd="M 2350 645 V 326"',
    // 5. dflash-container-to-final-output
    'd="M 1396 190 H 1360"',
    // 6. segmenter-to-llmlingua
    'd="M 1000 735 H 1040 V 630 H 1080"',
    // 7. segmenter-to-protected-question
    'd="M 1000 735 H 1040 V 1095 H 1080"',
    // 8. draft-to-verify
    'd="M 2200 190 H 2120"',
    // 9. verify-to-output-buffer
    'd="M 1820 190 H 1740"',
    // 10. output-buffer-to-draft-loop
    'd="M 1590 100 V 50 H 2350 V 100"'
];

// We will replace the entire block of edges.
const edgeBlockRegex = /<!-- EDGES -->[\s\S]*?<!-- CONTAINERS -->/;
const newEdgeBlock = `<!-- EDGES -->
                                        <div class="edge-group" id="original-to-context-compression">
                                            <path class="edge-outline" d="M 460 735 H 496"></path>
                                            <path class="edge-base" d="M 460 735 H 496"></path>
                                            <path class="edge-active" d="M 460 735 H 496" marker-end="url(#arrow-orange)"></path>
                                        </div>

                                        <div class="edge-group" id="context-compression-to-prompt-compression">
                                            <path class="edge-outline" d="M 1624 735 H 1660"></path>
                                            <path class="edge-base" d="M 1624 735 H 1660"></path>
                                            <path class="edge-active" d="M 1624 735 H 1660" marker-end="url(#arrow-orange)"></path>
                                        </div>

                                        <div class="edge-group" id="prompt-compression-to-target-prefill">
                                            <path class="edge-outline" d="M 2120 735 H 2200"></path>
                                            <path class="edge-base" d="M 2120 735 H 2200"></path>
                                            <path class="edge-active" d="M 2120 735 H 2200" marker-end="url(#arrow-orange)"></path>
                                        </div>

                                        <div class="edge-group" id="target-prefill-to-dflash-container">
                                            <path class="edge-outline" d="M 2350 645 V 326"></path>
                                            <path class="edge-base" d="M 2350 645 V 326"></path>
                                            <path class="edge-active" d="M 2350 645 V 326" marker-end="url(#arrow-orange)"></path>
                                        </div>

                                        <div class="edge-group" id="dflash-container-to-final-output">
                                            <path class="edge-outline" d="M 1396 190 H 1360"></path>
                                            <path class="edge-base" d="M 1396 190 H 1360"></path>
                                            <path class="edge-active" d="M 1396 190 H 1360" marker-end="url(#arrow-orange)"></path>
                                        </div>

                                        <div class="edge-group" id="segmenter-to-llmlingua">
                                            <path class="edge-outline" d="M 1000 735 H 1040 V 630 H 1080"></path>
                                            <path class="edge-base" d="M 1000 735 H 1040 V 630 H 1080"></path>
                                            <path class="edge-active" d="M 1000 735 H 1040 V 630 H 1080" marker-end="url(#arrow-orange)"></path>
                                        </div>

                                        <div class="edge-group" id="segmenter-to-protected-question">
                                            <path class="edge-outline" d="M 1000 735 H 1040 V 1095 H 1080"></path>
                                            <path class="edge-base" d="M 1000 735 H 1040 V 1095 H 1080"></path>
                                            <path class="edge-active" d="M 1000 735 H 1040 V 1095 H 1080" marker-end="url(#arrow-orange)"></path>
                                        </div>

                                        <div class="edge-group" id="draft-to-verify">
                                            <path class="edge-outline" d="M 2200 190 H 2120"></path>
                                            <path class="edge-base" d="M 2200 190 H 2120"></path>
                                            <path class="edge-active loop-edge" d="M 2200 190 H 2120" marker-end="url(#arrow-orange)"></path>
                                        </div>

                                        <div class="edge-group" id="verify-to-output-buffer">
                                            <path class="edge-outline" d="M 1820 190 H 1740"></path>
                                            <path class="edge-base" d="M 1820 190 H 1740"></path>
                                            <path class="edge-active loop-edge" d="M 1820 190 H 1740" marker-end="url(#arrow-orange)"></path>
                                        </div>

                                        <div class="edge-group" id="output-buffer-to-draft-loop">
                                            <path class="edge-outline" d="M 1590 100 V 50 H 2350 V 100"></path>
                                            <path class="edge-base" d="M 1590 100 V 50 H 2350 V 100"></path>
                                            <path class="edge-active loop-edge" d="M 1590 100 V 50 H 2350 V 100" marker-end="url(#arrow-orange)"></path>
                                        </div>

                                        <!-- CONTAINERS -->`;

html = html.replace(edgeBlockRegex, newEdgeBlock);
fs.writeFileSync('index.html', html);
console.log("Success HTML");
