const fs = require('fs');
let css = fs.readFileSync('styles/architecture-graph.css', 'utf8');

const newOverrides = `
#nInput { width: 390px; left: 120px; top: 610px; }
#nSplit { width: 420px; left: 595px; top: 545px; }
#nCompress { width: 440px; left: 1095px; top: 380px; }
#nProtect { width: 400px; left: 1095px; top: 860px; }
#nMerge { width: 420px; left: 1615px; top: 585px; }
#nPrefill { left: 2115px; top: 645px; }

#nFinal  { left: 795px; top: 100px; }
#nBuffer { left: 1235px; top: 100px; }
#nVerify { left: 1675px; top: 100px; }
#nDraft  { left: 2115px; top: 100px; }

#groupCompression {
    left: 551px;
    top: 336px;
    width: 1028px;
    height: 798px;
}

#groupDFlash {
    left: 1191px;
    top: 20px;
    width: 1268px;
    height: 306px;
}
`;

css = css.replace(/#nInput \{ width: 420px;[^]+#groupDFlash \{[^}]+\}/, newOverrides.trim());

fs.writeFileSync('styles/architecture-graph.css', css);
console.log("Success CSS");
