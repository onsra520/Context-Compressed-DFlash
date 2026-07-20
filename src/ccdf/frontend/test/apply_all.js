const fs = require('fs');

// ============================================================
// 1. CSS
// ============================================================
let css = fs.readFileSync('styles/architecture-graph.css', 'utf8');

// Update scene and SVG canvas size
css = css.replace(/width: 3700px;\s*\n\s*height: 1050px;\s*\n\s*transform-origin: 0 0;/, 
  'width: 2200px;\n    height: 1700px;\n    transform-origin: 0 0;');

css = css.replace(/\.edges \{[^}]+\}/, `.edges {
    position: absolute;
    inset: 0;
    width: 2200px;
    height: 1700px;
    overflow: visible;
    pointer-events: none;
    z-index: 5;
}`);

// Replace node positions block
const nodePosRegex = /#nInput[^]+?#groupDFlashLabel\s*\{[^}]+\}/s;
const newNodePos = `#nInput    { width: 390px; left:  40px; top: 350px; }
#nSplit    { width: 420px; left: 530px; top: 360px; }
#nCompress { width: 440px; left:1000px; top: 190px; }
#nProtect  { width: 400px; left:1000px; top: 630px; }
#nMerge    { width: 420px; left:1590px; top: 350px; }
#nPrefill  { width: 300px; left: 440px; top:1000px; }
#nDraft    { width: 300px; left: 900px; top:1000px; }
#nVerify   { width: 300px; left: 900px; top:1260px; }
#nBuffer   { width: 300px; left: 440px; top:1260px; }
#nFinal    { width: 300px; left:  40px; top:1100px; }

#groupCompression {
    left: 480px;
    top: 150px;
    width: 1060px;
    height: 750px;
}

#groupDFlash {
    left: 400px;
    top: 920px;
    width: 1660px;
    height: 560px;
}

#groupDFlashLabel {
    left: 650px;
    top: 936px;
    background: var(--cyan);
}`;
css = css.replace(nodePosRegex, newNodePos);

// Restore stage-group base styles (add before #nInput block)
const stageGroupCSS = `/* ═══════════════════════════════════════════════════════════════
   CLUSTER CONTAINERS
   ═══════════════════════════════════════════════════════════════ */
.stage-group {
    position: absolute;
    border: 4px dashed var(--black);
    background: rgba(0, 0, 0, 0.03);
    z-index: 2;
    box-shadow: 6px 6px 0 rgba(0,0,0,0.12);
}

.stage-group-label {
    position: absolute;
    font-family: var(--display);
    font-size: 12px;
    font-weight: 900;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    padding: 4px 10px;
    border: 3px solid var(--black);
    box-shadow: 3px 3px 0 var(--black);
    z-index: 20;
}

#groupCompressionLabel {
    left: 496px;
    top: 150px;
    background: var(--hot);
    color: #fff;
}

`;

// Insert before the first #nInput rule
css = css.replace('#nInput    { width:', stageGroupCSS + '#nInput    { width:');

// Remove stale groupCompressionLabel at bottom if exists
css = css.replace(/\n#groupCompressionLabel \{ left: 20px; top: 10px; \}\n?/, '');

fs.writeFileSync('styles/architecture-graph.css', css);
console.log('CSS done');

// ============================================================
// 2. HTML – edges and SVG viewBox
// ============================================================
let html = fs.readFileSync('index.html', 'utf8');

// Update viewBox
html = html.replace(/viewBox="[^"]*"/, 'viewBox="0 0 2200 1700"');

// Replace entire edge section
const newEdges = `<!-- EXTERNAL EDGES -->
                                            <g class="architecture-edge edge" id="original-to-context-compression" data-edge-id="original-to-context-compression" style="--edge-active-color: var(--yellow);">
                                                <path class="edge-outline" d="M 430 500 H 480"></path>
                                                <path class="edge-base" d="M 430 500 H 480"></path>
                                                <path class="edge-active" d="M 430 500 H 480" marker-end="url(#arrow-yellow)"></path>
                                            </g>

                                            <g class="architecture-edge edge" id="context-compression-to-prompt-compression" data-edge-id="context-compression-to-prompt-compression" style="--edge-active-color: var(--hot);">
                                                <path class="edge-outline" d="M 1540 525 H 1590"></path>
                                                <path class="edge-base" d="M 1540 525 H 1590"></path>
                                                <path class="edge-active" d="M 1540 525 H 1590" marker-end="url(#arrow-hot)"></path>
                                            </g>

                                            <g class="architecture-edge edge" id="prompt-compression-to-dflash" data-edge-id="prompt-compression-to-dflash" style="--edge-active-color: var(--purple);">
                                                <path class="edge-outline" d="M 2010 500 V 1200"></path>
                                                <path class="edge-base" d="M 2010 500 V 1200"></path>
                                                <path class="edge-active" d="M 2010 500 V 1200" marker-end="url(#arrow-purple)"></path>
                                            </g>

                                            <g class="architecture-edge edge" id="dflash-to-final-output" data-edge-id="dflash-to-final-output" style="--edge-active-color: var(--blue);">
                                                <path class="edge-outline" d="M 400 1200 H 340"></path>
                                                <path class="edge-base" d="M 400 1200 H 340"></path>
                                                <path class="edge-active" d="M 400 1200 H 340" marker-end="url(#arrow-blue)"></path>
                                            </g>

                                            <!-- INTERNAL EDGES (Context Compression) -->
                                            <g class="architecture-edge edge edge-internal" id="segmenter-to-llmlingua" data-edge-id="segmenter-to-llmlingua" style="--edge-active-color: var(--hot);">
                                                <path class="edge-outline" d="M 950 460 H 975 V 340 H 1000"></path>
                                                <path class="edge-base" d="M 950 460 H 975 V 340 H 1000"></path>
                                                <path class="edge-active" d="M 950 460 H 975 V 340 H 1000" marker-end="url(#arrow-hot)"></path>
                                            </g>

                                            <g class="architecture-edge edge edge-internal" id="segmenter-to-protected-question" data-edge-id="segmenter-to-protected-question" style="--edge-active-color: var(--green);">
                                                <path class="edge-outline" d="M 950 560 H 975 V 780 H 1000"></path>
                                                <path class="edge-base" d="M 950 560 H 975 V 780 H 1000"></path>
                                                <path class="edge-active" d="M 950 560 H 975 V 780 H 1000" marker-end="url(#arrow-green)"></path>
                                            </g>

                                            <!-- INTERNAL EDGES (D-Flash Generation Loop) -->
                                            <g class="architecture-edge edge edge-internal" id="prefill-to-draft" data-edge-id="prefill-to-draft" style="--edge-active-color: var(--orange);">
                                                <path class="edge-outline" d="M 740 1100 H 900"></path>
                                                <path class="edge-base" d="M 740 1100 H 900"></path>
                                                <path class="edge-active" d="M 740 1100 H 900" marker-end="url(#arrow-orange)"></path>
                                            </g>

                                            <g class="architecture-edge edge edge-internal" id="draft-to-verify" data-edge-id="draft-to-verify" style="--edge-active-color: var(--cyan);">
                                                <path class="edge-outline" d="M 1050 1200 V 1260"></path>
                                                <path class="edge-base" d="M 1050 1200 V 1260"></path>
                                                <path class="edge-active" d="M 1050 1200 V 1260" marker-end="url(#arrow-cyan)"></path>
                                            </g>

                                            <g class="architecture-edge edge edge-internal" id="verify-to-output-buffer" data-edge-id="verify-to-output-buffer" style="--edge-active-color: var(--purple);">
                                                <path class="edge-outline" d="M 900 1360 H 740"></path>
                                                <path class="edge-base" d="M 900 1360 H 740"></path>
                                                <path class="edge-active" d="M 900 1360 H 740" marker-end="url(#arrow-purple)"></path>
                                            </g>

                                            <g class="architecture-edge edge edge-internal" id="output-buffer-to-prefill" data-edge-id="output-buffer-to-prefill" style="--edge-active-color: var(--orange);">
                                                <path class="edge-outline" d="M 590 1260 V 1200"></path>
                                                <path class="edge-base" d="M 590 1260 V 1200"></path>
                                                <path class="edge-active loop-edge" d="M 590 1260 V 1200" marker-end="url(#arrow-orange)"></path>
                                            </g>`;

html = html.replace(
  /<!-- EXTERNAL EDGES -->[\s\S]*?<\/svg>/,
  newEdges + '\n                                        </svg>'
);

fs.writeFileSync('index.html', html);
console.log('HTML done');

// ============================================================
// 3. JS – sceneWidth/Height
// ============================================================
let js = fs.readFileSync('scripts/architecture-graph.js', 'utf8');
js = js.replace(
  /const sceneWidth = \d+;\s*\n\s*const sceneHeight = \d+;/,
  'const sceneWidth = 2200;\n        const sceneHeight = 1700;'
);
fs.writeFileSync('scripts/architecture-graph.js', js);
console.log('JS done');
