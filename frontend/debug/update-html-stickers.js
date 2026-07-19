const fs = require('fs');

let html = fs.readFileSync('index.html', 'utf-8');

// Evidence Section updates
const evidenceOld = `<span class="puri-sparkle puri-sparkle--cyan puri-x1">✧</span>
            </div>

            <header class="section-header">
                <div class="section-no">04</div>
                <div>
                    <h2 class="section-title">Kết quả tổng hợp</h2>
                    <p class="section-sub">
                        GSM8K cung cấp bằng chứng chất lượng numeric ngắn hạn. QMSum cung cấp chẩn đoán long-context
                        về input reduction, latency và lexical overlap — không phải semantic correctness.
                    </p>
                </div>
            </header>

            <div class="evidence-grid">
                <article class="evidence-card evidence-card--gsm">
                    <div class="evidence-head">
                        <span class="sticker s-hot">GSM8K · n=30</span>
                        <h3>Numeric answer match</h3>
                    </div>`;

const evidenceNew = `<span class="puri-sticker puri-sticker--hot puri-s4">GSM8K · n=30</span>
                <span class="puri-sticker puri-sticker--cyan puri-s5">QMSum · n=30</span>
                <span class="puri-sticker puri-sticker--lime puri-s6">Final interpretation</span>
                <span class="puri-sparkle puri-sparkle--cyan puri-x1">✧</span>
            </div>

            <header class="section-header">
                <div class="section-no">04</div>
                <div>
                    <h2 class="section-title">Kết quả tổng hợp</h2>
                    <p class="section-sub">
                        GSM8K cung cấp bằng chứng chất lượng numeric ngắn hạn. QMSum cung cấp chẩn đoán long-context
                        về input reduction, latency và lexical overlap — không phải semantic correctness.
                    </p>
                </div>
            </header>

            <div class="evidence-grid">
                <article class="evidence-card evidence-card--gsm">
                    <div class="evidence-head">
                        <h3>Numeric answer match</h3>
                    </div>`;

html = html.replace(evidenceOld, evidenceNew);

const qmsumOld = `<div class="evidence-head">
                        <span class="sticker s-cyan">QMSum · n=30</span>
                        <h3>Normalized lexical overlap</h3>
                    </div>`;
const qmsumNew = `<div class="evidence-head">
                        <h3>Normalized lexical overlap</h3>
                    </div>`;
html = html.replace(qmsumOld, qmsumNew);

const takeawayOld = `<div class="evidence-head">
                        <span class="sticker s-green">Final interpretation</span>
                        <h3>Workload-dependent benefit</h3>
                    </div>`;
const takeawayNew = `<div class="evidence-head">
                        <h3>Workload-dependent benefit</h3>
                    </div>`;
html = html.replace(takeawayOld, takeawayNew);


// Conclusion Section updates
const conclusionOld = `<span class="puri-sparkle puri-sparkle--yellow puri-x1">★</span>
            </div>

            <header class="section-header">
                <div class="section-no">05</div>
                <div>
                    <h2 class="section-title">Kết luận</h2>
                    <p class="section-sub">Một pipeline tích hợp hoàn chỉnh, với giới hạn claim được xác định rõ.</p>
                </div>
            </header>

            <div class="conclusion-board">
                <div class="conclusion-main">
                    <p>
                        <strong>CC-DFlash chứng minh được một pipeline tích hợp khả thi:</strong>
                        nén context trước DFlash, giảm input token và duy trì chất lượng numeric gần các baseline
                        trong thiết lập GSM8K đã đánh giá.
                    </p>
                    <p>
                        Kết quả cũng cho thấy lợi ích generation không tự động chuyển thành lợi ích end-to-end,
                        vì chi phí compression vẫn là yếu tố quyết định và phụ thuộc độ dài workload.
                    </p>
                </div>

                <div class="claim-boundaries">
                    <h3>Final claim boundary</h3>
                    <div class="boundary-grid">
                        <span>No universal speedup claim</span>
                        <span>No QMSum semantic-correctness claim</span>
                        <span>No deployment-readiness claim</span>
                        <span>No confirmed 8 GB deployment claim</span>
                    </div>
                </div>`;

const conclusionNew = `<span class="puri-sticker puri-sticker--orange puri-s4">No universal speedup claim</span>
                <span class="puri-sticker puri-sticker--cyan puri-s5">No QMSum semantic-correctness claim</span>
                <span class="puri-sticker puri-sticker--hot puri-s6">No deployment-readiness claim</span>
                <span class="puri-sticker puri-sticker--lime puri-s7">No confirmed 8 GB deployment claim</span>
                <span class="puri-sparkle puri-sparkle--yellow puri-x1">★</span>
            </div>

            <header class="section-header">
                <div class="section-no">05</div>
                <div>
                    <h2 class="section-title">Kết luận</h2>
                    <p class="section-sub">Một pipeline tích hợp hoàn chỉnh, với giới hạn claim được xác định rõ.</p>
                </div>
            </header>

            <div class="conclusion-board">
                <div class="conclusion-main">
                    <p>
                        <strong>CC-DFlash chứng minh được một pipeline tích hợp khả thi:</strong>
                        nén context trước DFlash, giảm input token và duy trì chất lượng numeric gần các baseline
                        trong thiết lập GSM8K đã đánh giá.
                    </p>
                    <p>
                        Kết quả cũng cho thấy lợi ích generation không tự động chuyển thành lợi ích end-to-end,
                        vì chi phí compression vẫn là yếu tố quyết định và phụ thuộc độ dài workload.
                    </p>
                </div>

                <div class="claim-boundaries">
                    <h3>Final claim boundary</h3>
                    <div class="boundary-grid">
                    </div>
                </div>`;

html = html.replace(conclusionOld, conclusionNew);

fs.writeFileSync('index.html', html);
console.log('HTML updated successfully');
