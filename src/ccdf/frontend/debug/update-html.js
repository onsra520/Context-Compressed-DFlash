const fs = require('fs');

let html = fs.readFileSync('index.html', 'utf-8');

// 1. Add containers
const containers = `
                                        <!-- CONTAINERS -->
                                        <div class="stage-group" id="groupCompression"></div>
                                        <div class="stage-group-label" id="groupCompressionLabel">CONTEXT COMPRESSION</div>
                                        
                                        <div class="stage-group" id="groupDFlash"></div>
                                        <div class="stage-group-label" id="groupDFlashLabel">D-FLASH GENERATION LOOP</div>
`;

if (!html.includes('groupCompression')) {
    html = html.replace('<div class="graph-scene" id="graphScene">', '<div class="graph-scene" id="graphScene">\n' + containers);
}

// 2. Replace SVG edges
const newSvg = `
                                        <svg class="edges" viewBox="0 0 2200 1000" aria-hidden="true">
                                            <defs>
                                                <!-- Markers for each color -->
                                                <marker id="arrow-gray" viewBox="0 0 18 16" refX="17" refY="8" markerWidth="18" markerHeight="16" markerUnits="userSpaceOnUse" orient="auto" overflow="visible"><path d="M 1 1 L 17 8 L 1 15 Z" fill="#6f7478" stroke="#111" stroke-width="1.5px" stroke-linejoin="miter"></path></marker>
                                                <marker id="arrow-yellow" viewBox="0 0 18 16" refX="17" refY="8" markerWidth="18" markerHeight="16" markerUnits="userSpaceOnUse" orient="auto" overflow="visible"><path d="M 1 1 L 17 8 L 1 15 Z" fill="var(--yellow)" stroke="#111" stroke-width="1.5px" stroke-linejoin="miter"></path></marker>
                                                <marker id="arrow-hot" viewBox="0 0 18 16" refX="17" refY="8" markerWidth="18" markerHeight="16" markerUnits="userSpaceOnUse" orient="auto" overflow="visible"><path d="M 1 1 L 17 8 L 1 15 Z" fill="var(--hot)" stroke="#111" stroke-width="1.5px" stroke-linejoin="miter"></path></marker>
                                                <marker id="arrow-green" viewBox="0 0 18 16" refX="17" refY="8" markerWidth="18" markerHeight="16" markerUnits="userSpaceOnUse" orient="auto" overflow="visible"><path d="M 1 1 L 17 8 L 1 15 Z" fill="var(--green)" stroke="#111" stroke-width="1.5px" stroke-linejoin="miter"></path></marker>
                                                <marker id="arrow-orange" viewBox="0 0 18 16" refX="17" refY="8" markerWidth="18" markerHeight="16" markerUnits="userSpaceOnUse" orient="auto" overflow="visible"><path d="M 1 1 L 17 8 L 1 15 Z" fill="var(--orange)" stroke="#111" stroke-width="1.5px" stroke-linejoin="miter"></path></marker>
                                                <marker id="arrow-cyan" viewBox="0 0 18 16" refX="17" refY="8" markerWidth="18" markerHeight="16" markerUnits="userSpaceOnUse" orient="auto" overflow="visible"><path d="M 1 1 L 17 8 L 1 15 Z" fill="var(--cyan)" stroke="#111" stroke-width="1.5px" stroke-linejoin="miter"></path></marker>
                                                <marker id="arrow-purple" viewBox="0 0 18 16" refX="17" refY="8" markerWidth="18" markerHeight="16" markerUnits="userSpaceOnUse" orient="auto" overflow="visible"><path d="M 1 1 L 17 8 L 1 15 Z" fill="var(--purple)" stroke="#111" stroke-width="1.5px" stroke-linejoin="miter"></path></marker>
                                                <marker id="arrow-blue" viewBox="0 0 18 16" refX="17" refY="8" markerWidth="18" markerHeight="16" markerUnits="userSpaceOnUse" orient="auto" overflow="visible"><path d="M 1 1 L 17 8 L 1 15 Z" fill="var(--blue)" stroke="#111" stroke-width="1.5px" stroke-linejoin="miter"></path></marker>
                                            </defs>

                                            <!-- EXTERNAL EDGES -->
                                            <g class="architecture-edge edge" id="original-to-context-compression" data-edge-id="original-to-context-compression" style="--edge-active-color: var(--yellow);">
                                                <path class="edge-outline" d="M 340 680 H 436"></path>
                                                <path class="edge-base" d="M 340 680 H 436"></path>
                                                <path class="edge-active" d="M 340 680 H 436" marker-end="url(#arrow-yellow)"></path>
                                            </g>

                                            <g class="architecture-edge edge" id="context-compression-to-prompt-compression" data-edge-id="context-compression-to-prompt-compression" style="--edge-active-color: var(--hot);">
                                                <path class="edge-outline" d="M 1264 680 H 1360"></path>
                                                <path class="edge-base" d="M 1264 680 H 1360"></path>
                                                <path class="edge-active" d="M 1264 680 H 1360" marker-end="url(#arrow-hot)"></path>
                                            </g>

                                            <g class="architecture-edge edge" id="prompt-compression-to-target-prefill" data-edge-id="prompt-compression-to-target-prefill" style="--edge-active-color: var(--purple);">
                                                <path class="edge-outline" d="M 1660 680 H 1800"></path>
                                                <path class="edge-base" d="M 1660 680 H 1800"></path>
                                                <path class="edge-active" d="M 1660 680 H 1800" marker-end="url(#arrow-purple)"></path>
                                            </g>

                                            <g class="architecture-edge edge" id="target-prefill-to-dflash-container" data-edge-id="target-prefill-to-dflash-container" style="--edge-active-color: var(--cyan);">
                                                <path class="edge-outline" d="M 1950 590 V 326"></path>
                                                <path class="edge-base" d="M 1950 590 V 326"></path>
                                                <path class="edge-active" d="M 1950 590 V 326" marker-end="url(#arrow-cyan)"></path>
                                            </g>

                                            <g class="architecture-edge edge" id="dflash-container-to-final-output" data-edge-id="dflash-container-to-final-output" style="--edge-active-color: var(--blue);">
                                                <path class="edge-outline" d="M 876 190 H 780"></path>
                                                <path class="edge-base" d="M 876 190 H 780"></path>
                                                <path class="edge-active" d="M 876 190 H 780" marker-end="url(#arrow-blue)"></path>
                                            </g>

                                            <!-- INTERNAL EDGES (Context Compression) -->
                                            <g class="architecture-edge edge edge-internal" id="segmenter-to-llmlingua" data-edge-id="segmenter-to-llmlingua" style="--edge-active-color: var(--hot);">
                                                <path class="edge-outline" d="M 780 680 H 830 V 520 H 920"></path>
                                                <path class="edge-base" d="M 780 680 H 830 V 520 H 920"></path>
                                                <path class="edge-active" d="M 780 680 H 830 V 520 H 920" marker-end="url(#arrow-hot)"></path>
                                            </g>

                                            <g class="architecture-edge edge edge-internal" id="segmenter-to-protected-question" data-edge-id="segmenter-to-protected-question" style="--edge-active-color: var(--green);">
                                                <path class="edge-outline" d="M 780 680 H 830 V 840 H 920"></path>
                                                <path class="edge-base" d="M 780 680 H 830 V 840 H 920"></path>
                                                <path class="edge-active" d="M 780 680 H 830 V 840 H 920" marker-end="url(#arrow-green)"></path>
                                            </g>

                                            <!-- INTERNAL EDGES (D-Flash Generation Loop) -->
                                            <g class="architecture-edge edge edge-internal" id="draft-to-verify" data-edge-id="draft-to-verify" style="--edge-active-color: var(--cyan);">
                                                <path class="edge-outline" d="M 1800 190 H 1660"></path>
                                                <path class="edge-base" d="M 1800 190 H 1660"></path>
                                                <path class="edge-active" d="M 1800 190 H 1660" marker-end="url(#arrow-cyan)"></path>
                                            </g>

                                            <g class="architecture-edge edge edge-internal" id="verify-to-output-buffer" data-edge-id="verify-to-output-buffer" style="--edge-active-color: var(--purple);">
                                                <path class="edge-outline" d="M 1360 190 H 1220"></path>
                                                <path class="edge-base" d="M 1360 190 H 1220"></path>
                                                <path class="edge-active" d="M 1360 190 H 1220" marker-end="url(#arrow-purple)"></path>
                                            </g>

                                            <g class="architecture-edge edge edge-internal" id="output-buffer-to-draft-loop" data-edge-id="output-buffer-to-draft-loop" style="--edge-active-color: var(--orange);">
                                                <path class="edge-outline" d="M 1070 100 V 50 H 1950 V 104"></path>
                                                <path class="edge-base" d="M 1070 100 V 50 H 1950 V 104"></path>
                                                <path class="edge-active loop-edge" d="M 1070 100 V 50 H 1950 V 104" marker-end="url(#arrow-orange)"></path>
                                            </g>
                                        </svg>`;

const svgStart = html.indexOf('<svg class="edges"');
const svgEnd = html.indexOf('</svg>', svgStart) + 6;
html = html.substring(0, svgStart) + newSvg + html.substring(svgEnd);

// 3. Rename Final Prompt to PROMPT COMPRESSION
html = html.replace('<h4>Final Prompt</h4>', '<h4>Prompt Compression</h4>');
// Keep description as 'Compressed context + protected question.' which is already there, but let's check
if (html.includes('<p>Compressed context + protected question.</p>')) {
    // it's already there
}

fs.writeFileSync('index.html', html);
console.log('index.html updated successfully.');
