const fs = require('fs');

let html = fs.readFileSync('index.html', 'utf-8');

// The badge HTML
const badgeHTML = `
                                        <div id="containerCycleBadge" style="position: absolute; left: 1840px; top: 38px; background: #111; color: var(--cyan); border: 2px solid #fffff8; padding: 4px 10px; font-family: var(--mono); font-weight: 900; font-size: 12px; z-index: 5; pointer-events: none; border-radius: 2px;">CYCLE: IDLE</div>
`;

if (!html.includes('containerCycleBadge')) {
    html = html.replace('<div class="stage-group" id="groupDFlash"></div>', '<div class="stage-group" id="groupDFlash"></div>' + badgeHTML);
}

fs.writeFileSync('index.html', html);
console.log('index.html updated successfully with cycle badge.');
