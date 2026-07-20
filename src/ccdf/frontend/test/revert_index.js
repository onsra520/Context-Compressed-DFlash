const fs = require('fs');
let html = fs.readFileSync('index.html', 'utf8');

const edgeBlockRegex = /<!-- EDGES -->[\s\S]*?<!-- CONTAINERS -->/;
const newEdgeBlock = `<!-- EDGES -->
                                        <div class="edge-group" id="original-to-context-compression">
                                            <path class="edge-outline" d="M 510 735 H 551"></path>
                                            <path class="edge-base" d="M 510 735 H 551"></path>
                                            <path class="edge-active" d="M 510 735 H 551" marker-end="url(#arrow-orange)"></path>
                                        </div>

                                        <div class="edge-group" id="context-compression-to-prompt-compression">
                                            <path class="edge-outline" d="M 1579 735 H 1615"></path>
                                            <path class="edge-base" d="M 1579 735 H 1615"></path>
                                            <path class="edge-active" d="M 1579 735 H 1615" marker-end="url(#arrow-orange)"></path>
                                        </div>

                                        <div class="edge-group" id="prompt-compression-to-target-prefill">
                                            <path class="edge-outline" d="M 2035 735 H 2115"></path>
                                            <path class="edge-base" d="M 2035 735 H 2115"></path>
                                            <path class="edge-active" d="M 2035 735 H 2115" marker-end="url(#arrow-orange)"></path>
                                        </div>

                                        <div class="edge-group" id="target-prefill-to-dflash-container">
                                            <path class="edge-outline" d="M 2265 645 V 326"></path>
                                            <path class="edge-base" d="M 2265 645 V 326"></path>
                                            <path class="edge-active" d="M 2265 645 V 326" marker-end="url(#arrow-orange)"></path>
                                        </div>

                                        <div class="edge-group" id="dflash-container-to-final-output">
                                            <path class="edge-outline" d="M 1191 190 H 1095"></path>
                                            <path class="edge-base" d="M 1191 190 H 1095"></path>
                                            <path class="edge-active" d="M 1191 190 H 1095" marker-end="url(#arrow-orange)"></path>
                                        </div>

                                        <div class="edge-group" id="segmenter-to-llmlingua">
                                            <path class="edge-outline" d="M 1015 735 H 1055 V 580 H 1095"></path>
                                            <path class="edge-base" d="M 1015 735 H 1055 V 580 H 1095"></path>
                                            <path class="edge-active" d="M 1015 735 H 1055 V 580 H 1095" marker-end="url(#arrow-orange)"></path>
                                        </div>

                                        <div class="edge-group" id="segmenter-to-protected-question">
                                            <path class="edge-outline" d="M 1015 735 H 1055 V 975 H 1095"></path>
                                            <path class="edge-base" d="M 1015 735 H 1055 V 975 H 1095"></path>
                                            <path class="edge-active" d="M 1015 735 H 1055 V 975 H 1095" marker-end="url(#arrow-orange)"></path>
                                        </div>

                                        <div class="edge-group" id="draft-to-verify">
                                            <path class="edge-outline" d="M 2115 190 H 1975"></path>
                                            <path class="edge-base" d="M 2115 190 H 1975"></path>
                                            <path class="edge-active loop-edge" d="M 2115 190 H 1975" marker-end="url(#arrow-orange)"></path>
                                        </div>

                                        <div class="edge-group" id="verify-to-output-buffer">
                                            <path class="edge-outline" d="M 1675 190 H 1535"></path>
                                            <path class="edge-base" d="M 1675 190 H 1535"></path>
                                            <path class="edge-active loop-edge" d="M 1675 190 H 1535" marker-end="url(#arrow-orange)"></path>
                                        </div>

                                        <div class="edge-group" id="output-buffer-to-draft-loop">
                                            <path class="edge-outline" d="M 1385 100 V 50 H 2265 V 100"></path>
                                            <path class="edge-base" d="M 1385 100 V 50 H 2265 V 100"></path>
                                            <path class="edge-active loop-edge" d="M 1385 100 V 50 H 2265 V 100" marker-end="url(#arrow-orange)"></path>
                                        </div>

                                        <!-- CONTAINERS -->`;

html = html.replace(edgeBlockRegex, newEdgeBlock);
fs.writeFileSync('index.html', html);
console.log("Success HTML");
