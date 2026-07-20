const fs = require('fs');
let html = fs.readFileSync('index.html', 'utf8');
let css = fs.readFileSync('styles/architecture-graph.css', 'utf8');
let js = fs.readFileSync('scripts/architecture-graph.js', 'utf8');

// ============================================================
// 1. CSS: Update node positions, widths, cluster bounds
// ============================================================
const newNodeCSS = `
#nInput    { width: 390px; left:  40px; top: 480px; }
#nSplit    { width: 420px; left: 530px; top: 455px; }
#nCompress { width: 440px; left:1000px; top: 280px; }
#nProtect  { width: 400px; left:1000px; top: 710px; }
#nMerge    { width: 420px; left:1590px; top: 465px; }
#nPrefill  { width: 300px; left:2100px; top: 480px; }
#nDraft    { width: 300px; left:2560px; top: 480px; }
#nVerify   { width: 300px; left:2560px; top: 170px; }
#nBuffer   { width: 300px; left:2100px; top: 170px; }
#nFinal    { width: 300px; left:3410px; top: 410px; }

#groupCompression {
    left: 480px;
    top: 250px;
    width: 1060px;
    height: 750px;
}

#groupDFlash {
    left: 2060px;
    top: 100px;
    width: 1340px;
    height: 820px;
}
`;

// Replace old node/cluster positioning block
css = css.replace(/#nInput[^]+?#groupDFlash\s*\{[^}]+\}/s, newNodeCSS.trim());

// Also fix groupDFlashLabel - remove dangerous rotation
css = css.replace(
  /#groupDFlashLabel\s*\{[^}]+\}/s,
  `#groupDFlashLabel {
    left: 680px;
    top: 120px;
    background: var(--cyan);
}`
);

// Fix groupCompressionLabel position
const compLabelMatch = css.match(/#groupCompressionLabel\s*\{[^}]+\}/s);
if (!compLabelMatch) {
  // Add it
  css += `\n#groupCompressionLabel { left: 20px; top: 10px; }\n`;
}

fs.writeFileSync('styles/architecture-graph.css', css);
console.log('CSS updated');

// ============================================================
// 2. HTML: Update SVG viewBox and all edges
// ============================================================

// Update viewBox
html = html.replace(
  /viewBox="[^"]*"/,
  'viewBox="0 0 3700 1050"'
);

// Replace the entire edge section
const edgeBlock = `<!-- EXTERNAL EDGES -->
                                            <g class="architecture-edge edge" id="original-to-context-compression" data-edge-id="original-to-context-compression" style="--edge-active-color: var(--yellow);">
                                                <path class="edge-outline" d="M 430 590 H 480"></path>
                                                <path class="edge-base" d="M 430 590 H 480"></path>
                                                <path class="edge-active" d="M 430 590 H 480" marker-end="url(#arrow-yellow)"></path>
                                            </g>

                                            <g class="architecture-edge edge" id="context-compression-to-prompt-compression" data-edge-id="context-compression-to-prompt-compression" style="--edge-active-color: var(--hot);">
                                                <path class="edge-outline" d="M 1540 625 H 1590"></path>
                                                <path class="edge-base" d="M 1540 625 H 1590"></path>
                                                <path class="edge-active" d="M 1540 625 H 1590" marker-end="url(#arrow-hot)"></path>
                                            </g>

                                            <g class="architecture-edge edge" id="prompt-compression-to-dflash" data-edge-id="prompt-compression-to-dflash" style="--edge-active-color: var(--purple);">
                                                <path class="edge-outline" d="M 2010 590 H 2060"></path>
                                                <path class="edge-base" d="M 2010 590 H 2060"></path>
                                                <path class="edge-active" d="M 2010 590 H 2060" marker-end="url(#arrow-purple)"></path>
                                            </g>

                                            <g class="architecture-edge edge" id="dflash-to-final-output" data-edge-id="dflash-to-final-output" style="--edge-active-color: var(--blue);">
                                                <path class="edge-outline" d="M 3400 510 H 3410"></path>
                                                <path class="edge-base" d="M 3400 510 H 3410"></path>
                                                <path class="edge-active" d="M 3400 510 H 3410" marker-end="url(#arrow-blue)"></path>
                                            </g>

                                            <!-- INTERNAL EDGES (Context Compression) -->
                                            <g class="architecture-edge edge edge-internal" id="segmenter-to-llmlingua" data-edge-id="segmenter-to-llmlingua" style="--edge-active-color: var(--hot);">
                                                <path class="edge-outline" d="M 950 545 H 975 V 430 H 1000"></path>
                                                <path class="edge-base" d="M 950 545 H 975 V 430 H 1000"></path>
                                                <path class="edge-active" d="M 950 545 H 975 V 430 H 1000" marker-end="url(#arrow-hot)"></path>
                                            </g>

                                            <g class="architecture-edge edge edge-internal" id="segmenter-to-protected-question" data-edge-id="segmenter-to-protected-question" style="--edge-active-color: var(--green);">
                                                <path class="edge-outline" d="M 950 645 H 975 V 810 H 1000"></path>
                                                <path class="edge-base" d="M 950 645 H 975 V 810 H 1000"></path>
                                                <path class="edge-active" d="M 950 645 H 975 V 810 H 1000" marker-end="url(#arrow-green)"></path>
                                            </g>

                                            <!-- INTERNAL EDGES (D-Flash Generation Loop) -->
                                            <g class="architecture-edge edge edge-internal" id="prefill-to-draft" data-edge-id="prefill-to-draft" style="--edge-active-color: var(--orange);">
                                                <path class="edge-outline" d="M 2400 580 H 2560"></path>
                                                <path class="edge-base" d="M 2400 580 H 2560"></path>
                                                <path class="edge-active" d="M 2400 580 H 2560" marker-end="url(#arrow-orange)"></path>
                                            </g>

                                            <g class="architecture-edge edge edge-internal" id="draft-to-verify" data-edge-id="draft-to-verify" style="--edge-active-color: var(--cyan);">
                                                <path class="edge-outline" d="M 2710 480 V 370"></path>
                                                <path class="edge-base" d="M 2710 480 V 370"></path>
                                                <path class="edge-active" d="M 2710 480 V 370" marker-end="url(#arrow-cyan)"></path>
                                            </g>

                                            <g class="architecture-edge edge edge-internal" id="verify-to-output-buffer" data-edge-id="verify-to-output-buffer" style="--edge-active-color: var(--purple);">
                                                <path class="edge-outline" d="M 2560 270 H 2400"></path>
                                                <path class="edge-base" d="M 2560 270 H 2400"></path>
                                                <path class="edge-active" d="M 2560 270 H 2400" marker-end="url(#arrow-purple)"></path>
                                            </g>

                                            <g class="architecture-edge edge edge-internal" id="output-buffer-to-prefill" data-edge-id="output-buffer-to-prefill" style="--edge-active-color: var(--orange);">
                                                <path class="edge-outline" d="M 2250 370 V 480"></path>
                                                <path class="edge-base" d="M 2250 370 V 480"></path>
                                                <path class="edge-active loop-edge" d="M 2250 370 V 480" marker-end="url(#arrow-orange)"></path>
                                            </g>

                                            <g class="architecture-edge edge edge-internal" id="dflash-cluster-to-final" data-edge-id="dflash-cluster-to-final" style="--edge-active-color: var(--blue);">
                                                <path class="edge-outline" d="M 2400 270 H 3410 V 510"></path>
                                                <path class="edge-base" d="M 2400 270 H 3410 V 510"></path>
                                                <path class="edge-active" d="M 2400 270 H 3410 V 510" marker-end="url(#arrow-blue)"></path>
                                            </g>`;

// Replace the old edge section (from <!-- EXTERNAL EDGES --> or <!-- INTERNAL EDGES --> to </svg>)
html = html.replace(
  /<!-- EXTERNAL EDGES -->[\s\S]*?<\/svg>/,
  edgeBlock + '\n                                        </svg>'
);

fs.writeFileSync('index.html', html);
console.log('HTML updated');

// ============================================================
// 3. JS: Update sceneWidth/sceneHeight for fitGraph
// ============================================================
js = js.replace(
  /const sceneWidth = \d+;\s*\n\s*const sceneHeight = \d+;/,
  'const sceneWidth = 3700;\n        const sceneHeight = 1050;'
);

// Update edge IDs in activeEdge references in mock data steps if needed
// Actually that's in mock-data.js not here.

fs.writeFileSync('scripts/architecture-graph.js', js);
console.log('JS updated');

// ============================================================
// 4. mock-data.js: Update edge IDs to match new names
// ============================================================
let mock = fs.readFileSync('mocks/mock-data.js', 'utf8');

// Update edge id references to match new names
mock = mock.replace(/"prompt-compression-to-target-prefill"/g, '"prompt-compression-to-dflash"');
mock = mock.replace(/"target-prefill-to-dflash-container"/g, '"prompt-compression-to-dflash"');
mock = mock.replace(/"dflash-container-to-final-output"/g, '"dflash-to-final-output"');
mock = mock.replace(/"output-buffer-to-draft-loop"/g, '"output-buffer-to-prefill"');
// Keep segmenter-to-llmlingua and segmenter-to-protected-question as is

fs.writeFileSync('mocks/mock-data.js', mock);
console.log('Mock updated');
