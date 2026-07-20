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
                                            <span class="insp-metric" id="prompt-trace-metric">184 TOKENS</span>
                                        </div>
                                        <div class="insp-flow">
                                            <div class="insp-label">VÀO</div>
                                            <div class="insp-box insp-box--input" id="prompt-trace-input">Bữa tối cho 8 người, gồm yêu cầu ăn uống, ngân sách và thời gian.</div>
                                            
                                            <div class="insp-operation-wrap">
                                                <span class="insp-arrow">↓</span>
                                                <span class="insp-operation" id="prompt-trace-operation">NHẬN PROMPT</span>
                                            </div>
                                            
                                            <div class="insp-label">RA</div>
                                            <div class="insp-box insp-box--output" id="prompt-trace-output">184 tokens · context + question + output rules</div>
                                        </div>
                                    </div>
                                </aside>`;

const asideRegex = /<aside class="graph-inspector".*?>[\s\S]*?<\/aside>/;
html = html.replace(asideRegex, newAside.trim());

fs.writeFileSync('index.html', html);
console.log('Updated index.html to use prompt-trace hooks.');
