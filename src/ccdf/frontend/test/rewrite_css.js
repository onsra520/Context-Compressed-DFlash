const fs = require('fs');
let css = fs.readFileSync('styles/architecture-graph.css', 'utf8');

// We will add specific dimensions to each node and update group sizes.
const newOverrides = `
#nInput { width: 420px; min-height: 260px; left: 40px; top: 605px; }
#nSplit { width: 460px; min-height: 400px; left: 540px; top: 535px; }
#nCompress { width: 500px; min-height: 540px; left: 1080px; top: 360px; }
#nProtect { width: 420px; min-height: 230px; left: 1080px; top: 980px; }
#nMerge { width: 460px; min-height: 320px; left: 1660px; top: 575px; }
#nPrefill { left: 2200px; top: 645px; }

#nFinal  { left: 1060px; top: 100px; }
#nBuffer { left: 1440px; top: 100px; }
#nVerify { left: 1820px; top: 100px; }
#nDraft  { left: 2200px; top: 100px; }

#groupCompression {
    left: 496px;
    top: 316px;
    width: 1128px;
    height: 938px;
}

#groupDFlash {
    left: 1396px;
    top: 20px;
    width: 1148px;
    height: 306px;
}
`;

// Replace old positioning rules
css = css.replace(/\/\* INPUT ROW[^]+#nDraft[^}]+\}/, newOverrides);

// Also remove width: 375px from .node since we define per-node widths, or leave it as default.
// Let's set default back to 300px just in case, but specific nodes have overrides.
css = css.replace(/width: 375px;/, 'width: 300px;');

fs.writeFileSync('styles/architecture-graph.css', css);
console.log("Success CSS");
