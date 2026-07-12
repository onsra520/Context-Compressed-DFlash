const fs = require('fs');

let html = fs.readFileSync('index.html', 'utf-8');

const htmlOld = `                <span class="puri-sticker puri-sticker--orange puri-s1">BASELINE AR</span>
                <span class="puri-sticker puri-sticker--cyan puri-s2">D-FLASH</span>
                <span class="puri-sticker puri-sticker--lime puri-s3">CC-DFLASH</span>
                <span class="puri-doodle puri-doodle--black puri-d1">same prompt!</span>
                <span class="puri-sparkle puri-sparkle--purple puri-x1">♡</span>
            </div>

            <header class="section-header">
                <div class="section-no">02</div>
                <div>
                    <h2 class="section-title">So sánh ba kiến trúc</h2>
                    <p class="section-sub">
                        Nhập một prompt bất kỳ. Frontend sẽ mô phỏng cùng prompt qua Baseline-AR, D-Flash và
                        CC-DFlash bằng công thức mock xác định theo độ dài input.
                    </p>
                    <div class="stickers-row">
                        <span class="sticker s-orange">Same target</span>
                        <span class="sticker s-yellow">Same prompt</span>
                        <span class="sticker s-cyan">Separated metrics</span>
                        <span class="sticker s-green">Deterministic mock</span>
                    </div>
                </div>
            </header>`;

const htmlNew = `                <span class="puri-sticker puri-sticker--orange puri-s1">BASELINE AR</span>
                <span class="puri-sticker puri-sticker--cyan puri-s2">D-FLASH</span>
                <span class="puri-sticker puri-sticker--lime puri-s3">CC-DFLASH</span>
                
                <span class="puri-sticker puri-sticker--orange puri-s4">Same target</span>
                <span class="puri-sticker puri-sticker--hot puri-s5">Same prompt</span>
                <span class="puri-sticker puri-sticker--cyan puri-s6">Separated metrics</span>
                <span class="puri-sticker puri-sticker--lime puri-s7">Deterministic mock</span>

                <span class="puri-doodle puri-doodle--black puri-d1">same prompt!</span>
                <span class="puri-sparkle puri-sparkle--purple puri-x1">♡</span>
            </div>

            <header class="section-header">
                <div class="section-no">02</div>
                <div>
                    <h2 class="section-title">So sánh ba kiến trúc</h2>
                    <p class="section-sub">
                        Nhập một prompt bất kỳ. Frontend sẽ mô phỏng cùng prompt qua Baseline-AR, D-Flash và
                        CC-DFlash bằng công thức mock xác định theo độ dài input.
                    </p>
                </div>
            </header>`;

html = html.replace(htmlOld, htmlNew);
fs.writeFileSync('index.html', html);


let css = fs.readFileSync('styles/purikura.css', 'utf-8');
const cssOld = /#comparison \.puri-word--a \{[\s\S]*?\.section#comparison \.puri-x1 \{\s*left: 7vw;\s*bottom: 180px\s*\}/;

const cssNew = `#comparison .puri-word--a {
    right: 3vw;
    top: 60px
}

.section#comparison .puri-word--b {
    left: 45vw;
    bottom: 25px
}

.section#comparison .puri-s1 {
    right: 6vw;
    top: 155px
}

.section#comparison .puri-s2 {
    right: 20vw;
    top: 135px
}

.section#comparison .puri-s3 {
    left: 4vw;
    bottom: 60px
}

.section#comparison .puri-s4 {
    left: 3vw;
    top: 180px
}

.section#comparison .puri-s5 {
    right: 35vw;
    top: 165px
}

.section#comparison .puri-s6 {
    left: 28vw;
    bottom: 45px
}

.section#comparison .puri-s7 {
    right: 18vw;
    bottom: 75px
}

.section#comparison .puri-d1 {
    left: 48vw;
    top: 110px
}

.section#comparison .puri-x1 {
    left: 8vw;
    bottom: 120px
}`;

if (css.match(cssOld)) {
    css = css.replace(cssOld, cssNew);
} else {
    console.error("Could not find the old CSS block!");
}

fs.writeFileSync('styles/purikura.css', css);
console.log('Update complete.');
