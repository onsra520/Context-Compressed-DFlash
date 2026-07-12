const fs = require('fs');

let html = fs.readFileSync('index.html', 'utf-8');

const newAside = `                                <aside class="graph-inspector" aria-label="Dynamic Walkthrough Inspector">
                                    <div class="insp-card insp-card--describe">
                                        <div class="insp-header">
                                            <span class="insp-title">NODE HIỆN TẠI</span>
                                            <span class="insp-step" id="stepIndicator">STEP 00 / 16</span>
                                        </div>
                                        <h3 class="insp-node-title" id="stepTitle">ORIGINAL PROMPT</h3>
                                        <p class="insp-desc" id="stepDesc">Nhận yêu cầu ban đầu gồm context, câu hỏi và các ràng buộc cần được giữ nguyên.</p>
                                    </div>

                                    <div class="insp-card insp-card--live">
                                        <div class="insp-header">
                                            <span class="insp-live-title">PROMPT TRACE</span>
                                            <span class="insp-metric" id="traceMetric">184 TOKENS</span>
                                        </div>
                                        <div class="insp-flow">
                                            <div class="insp-label" id="inspInputLabel">VÀO</div>
                                            <div class="insp-box insp-box--input" id="contextBox">Yêu cầu bữa tối cho 8 người,<br>kèm ngân sách, thời gian và dị ứng.</div>
                                            
                                            <div class="insp-operation-wrap">
                                                <span class="insp-arrow">↓</span>
                                                <span class="insp-operation" id="processBox">NHẬN PROMPT</span>
                                            </div>
                                            
                                            <div class="insp-label" id="inspOutputLabel">RA</div>
                                            <div class="insp-box insp-box--output" id="payloadBox">184 tokens<br>Context + question + output rules</div>
                                        </div>
                                    </div>
                                </aside>`;

const asideRegex = /<aside class="graph-inspector".*?>[\s\S]*?<\/aside>/;
html = html.replace(asideRegex, newAside.trim());

fs.writeFileSync('index.html', html);
console.log('Updated index.html aside content.');
