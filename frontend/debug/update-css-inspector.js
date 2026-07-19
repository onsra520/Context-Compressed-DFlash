const fs = require('fs');

let css = fs.readFileSync('styles/architecture-graph.css', 'utf-8');

const newCSS = `/* ═══════════════════════════════════════════════════════════════
   GRAPH INSPECTOR UI
   ═══════════════════════════════════════════════════════════════ */
.graph-inspector {
    position: absolute;
    top: 16px;
    left: 16px;
    width: 320px;
    display: flex;
    flex-direction: column;
    gap: 12px;
    z-index: 100;
    pointer-events: auto;
}

.insp-card {
    background: var(--paper, #fffff8);
    border: 3px solid #111;
    box-shadow: 5px 5px 0 #111;
    padding: 14px 16px;
    display: flex;
    flex-direction: column;
}

.insp-card--describe {
    height: 140px;
}

.insp-card--live {
    height: 260px;
}

/* NODE DESCRIBE CARD */
.insp-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 4px;
}

.insp-title, .insp-live-title {
    font-size: 13px;
    font-weight: 900;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin: 0;
}

.insp-step, .insp-metric {
    font-size: 11px;
    font-weight: 900;
    background: var(--cyan);
    border: 2px solid #111;
    padding: 2px 6px;
    white-space: nowrap;
}

.insp-node-title {
    font-size: 22px;
    font-weight: 900;
    line-height: 1;
    margin: 6px 0 8px 0;
    text-transform: uppercase;
    color: var(--black);
}

.insp-desc {
    font-size: 13px;
    font-weight: 700;
    line-height: 1.4;
    margin: 0;
    display: -webkit-box;
    -webkit-line-clamp: 3;
    -webkit-box-orient: vertical;
    overflow: hidden;
}

/* LIVE DATA CARD */
.insp-flow {
    display: flex;
    flex-direction: column;
    gap: 4px;
}

.insp-label {
    font-size: 11px;
    font-weight: 900;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 2px;
}

.insp-box {
    background: #fff;
    border: 2px solid #111;
    padding: 6px 10px;
    font-size: 13px;
    font-weight: 700;
    line-height: 1.35;
    border-left-width: 6px;
    
    /* Display preview constraints */
    display: -webkit-box;
    -webkit-line-clamp: 3;
    -webkit-box-orient: vertical;
    overflow: hidden;
    min-height: 52px;
}

.insp-box--input { border-left-color: var(--yellow); }
.insp-box--output { border-left-color: var(--lime); }

.insp-operation-wrap {
    display: flex;
    align-items: center;
    justify-content: flex-start;
    gap: 8px;
    margin: 4px 0;
}

.insp-arrow {
    font-size: 14px;
    font-weight: 900;
}

.insp-operation {
    font-size: 11px;
    font-weight: 900;
    background: #111;
    color: var(--paper);
    padding: 3px 8px;
    border-radius: 2px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

/* Responsive */
@media (max-width: 900px) {
    .graph-inspector {
        position: relative;
        top: 0;
        left: 0;
        width: 100%;
        margin-bottom: 20px;
    }
}
@media (max-height: 800px) {
    .insp-card { padding: 12px; }
    .insp-card--describe { height: 130px; }
    .insp-card--live { height: 240px; }
    .insp-desc { -webkit-line-clamp: 2; }
}
`;

const cssRegex = /\/\* ═══════════════════════════════════════════════════════════════\s*GRAPH INSPECTOR UI\s*═══════════════════════════════════════════════════════════════ \*\/[\s\S]*?(?=\/\* ═══════════════════════════════════════════════════════════════|$)/;
css = css.replace(cssRegex, newCSS);

fs.writeFileSync('styles/architecture-graph.css', css);
console.log('Updated architecture-graph.css');
