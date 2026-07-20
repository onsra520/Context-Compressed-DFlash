const fs = require('fs');

const html = fs.readFileSync('index.html', 'utf8');

const regex = /<article class="node node-yellow" id="nInput">[\s\S]*?<\/article>\s*<article class="node node-cyan" id="nSplit">[\s\S]*?<\/article>\s*<article class="node node-hot" id="nCompress">[\s\S]*?<\/article>\s*<article class="node node-green" id="nProtect">[\s\S]*?<\/article>\s*<article class="node node-purple" id="nMerge">[\s\S]*?<\/article>/;

const replacement = `<article class="node node-yellow" id="nInput">
    <div class="n-top">
        <div class="icon">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14"/><path d="m12 5 7 7-7 7"/><path d="M3 19V5"/></svg>
        </div>
        <h4>ORIGINAL PROMPT</h4>
    </div>
    <div class="prompt-sub-card">
        <div class="prompt-sub-card-label">PROMPT ĐẦU VÀO</div>
        <div class="prompt-sub-card-content" id="nInput-content"></div>
    </div>
</article>

<article class="node node-cyan" id="nSplit">
    <div class="n-top">
        <div class="icon">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="18" r="3"/><circle cx="6" cy="6" r="3"/><circle cx="18" cy="6" r="3"/><path d="M18 9v2c0 .6-.4 1-1 1H7c-.6 0-1-.4-1-1V9"/><path d="M12 12v3"/></svg>
        </div>
        <h4>PROMPT SEGMENTER</h4>
    </div>
    <div class="prompt-sub-card">
        <div class="prompt-sub-card-label">CONTEXT</div>
        <div class="prompt-sub-card-content" id="nSplit-context"></div>
    </div>
    <div class="prompt-sub-card">
        <div class="prompt-sub-card-label">PROTECTED</div>
        <div class="prompt-sub-card-content" id="nSplit-protected"></div>
    </div>
</article>

<article class="node node-hot" id="nCompress">
    <div class="n-top">
        <div class="icon">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M8 3v3a2 2 0 0 1-2 2H3"/><path d="M21 8h-3a2 2 0 0 1-2-2V3"/><path d="M3 16h3a2 2 0 0 1 2 2v3"/><path d="M16 21v-3a2 2 0 0 1 2-2h3"/></svg>
        </div>
        <div>
            <h4>COMPRESSOR</h4>
            <span class="tech-label" style="font-size: 10px; font-weight: 900; background: #fff; color: #111; border: 2px solid #111; padding: 2px 4px; display: inline-block; margin-top: 4px;">LLMLINGUA-2</span>
        </div>
    </div>
    <div class="prompt-sub-card" style="margin-top: 0;">
        <div class="prompt-sub-card-label">INPUT</div>
        <div class="prompt-sub-card-content" id="nCompress-input"></div>
    </div>
    <div class="prompt-sub-card-indicator">↓ NÉN</div>
    <div class="prompt-sub-card" style="margin-top: 0;">
        <div class="prompt-sub-card-label">OUTPUT</div>
        <div class="prompt-sub-card-content" id="nCompress-output"></div>
    </div>
</article>

<article class="node node-green" id="nProtect">
    <div class="n-top">
        <div class="icon">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2-1 4-3 7-3s5 2 7 3a1 1 0 0 1 1 1v7Z"/><path d="m9 12 2 2 4-4"/></svg>
        </div>
        <h4>PROTECTED QUESTION</h4>
    </div>
    <div class="prompt-sub-card">
        <div class="prompt-sub-card-label">GIỮ NGUYÊN</div>
        <div class="prompt-sub-card-content" id="nProtect-content"></div>
    </div>
</article>

<article class="node node-purple" id="nMerge">
    <div class="n-top">
        <div class="icon">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m18 15-6-6-6 6"/><path d="M12 21V9"/><path d="M6 3v6"/><path d="M18 3v6"/></svg>
        </div>
        <h4>PROMPT COMPRESSION</h4>
    </div>
    <div style="display: flex; gap: 4px; margin-bottom: 8px;">
        <span class="status-chip" style="font-size: 10px; font-weight: 900; background: #fff; color: #111; border: 2px solid #111; padding: 2px 4px;">CONTEXT + PROTECTED</span>
    </div>
    <div class="prompt-sub-card" style="margin-top: 0;">
        <div class="prompt-sub-card-label">PROMPT SAU KHI GHÉP</div>
        <div class="prompt-sub-card-content" id="nMerge-content"></div>
    </div>
</article>`;

const newHtml = html.replace(regex, replacement);

if (newHtml === html) {
    console.error("No changes made!");
    process.exit(1);
}
fs.writeFileSync('index.html', newHtml);
console.log("Success");
