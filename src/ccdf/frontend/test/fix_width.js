const fs = require('fs');

/*
MAX NODE WIDTH = 440px (chiều rộng lớn nhất hiện tại: nCompress)
Tất cả node sẽ dùng 440px.

Sau khi đồng nhất:
- nSplit: left=530 → right=970
- nCompress: left=1000 → right=1440
- nProtect: left=1000 → right=1440

Context Compression cluster fit:
  padding 60px mỗi bên
  left: 530-60 = 470 (làm tròn → 480 cho khoảng trống label)
  right: 1440+60 = 1500
  width: 1500-480 = 1020
  top: 150 (không đổi)
  height: 750 (không đổi, nProtect bottom = 630+h ≈ 630+280=910 ≤ 150+750=900... cần kiểm tra)

Để nProtect fit:
  nProtect top=630, min-height ≈ 220px → bottom ≈ 850
  Cluster bottom: 150+750=900 ✓ (50px padding)

D-Flash nodes:
- nPrefill: left=440 → right=880
- nDraft:   left=900 → right=1340
- nVerify:  left=900 → right=1340
- nBuffer:  left=440 → right=880

D-Flash cluster fit:
  left: 440-40=400 ✓ (đã đúng)
  right: 1340+60=1400
  width: 1400-400 = 1000
  top: 920, height: 560 (bottom=1480)
  nVerify/nBuffer bottom: 1260+220=1480 ✓ (tight fit, use height=580 for padding)
  height: 1400-920+60=560 → 580 for comfort

Edge adjustments after width change:
- nSplit right was 950 (420px wide), now 970 (440px)
  E5: M 950 460 H 975 → M 970 460 H 995
  E6: M 950 560 H 975 → M 970 560 H 995
- nMerge right was 2010 (420px wide), now 2030 (440px)
  E3: M 2010 500 V 1200 → M 2030 500 V 1200
- nPrefill right was 740 (300px), now 880 (440px)
  E7: M 740 1100 H 900 → M 880 1100 H 900 (20px gap, still ok)
  Actually gap = 900-880 = 20px. Let's route: M 880 1100 H 900
- nBuffer top center was (590,1260), now center-x = 440+220=660
  E10: M 590 1260 V 1200 → M 660 1260 V 1200
  nPrefill bottom center = (440+220, 1000+h) → (660, 1000+h)... bottom = top+200=1200
  E10: M 660 1260 V 1200 ← arrives at nPrefill bottom ✓
- nVerify left was 900 (unchanged), but center-y unchanged
  E9 stays: M 900 1360 H 740 → but nBuffer right = 880 now
  E9: M 900 1360 H 880
- nDraft bottom center: top=1000, nDraft top=1000+(300=width? no, height≈200)=1200
  E8: M 1050 1200 V 1260 → X center = 900+220=1120
  E8: M 1120 1200 V 1260
- nVerify bottom center: x=900+220=1120, top=1000... wait
  Actually nDraft top-center was (1050,1000) using 300px/2=150 offset from left=900 → center-x=1050
  With 440px: center-x = 900+220=1120
  E8: M 1120 1200 V 1260 (draft bottom → verify top)
  nVerify left center = (900, 1260+100=1360) → unchanged x
  E9: M 900 1360 H 880 (verify left → buffer right, buffer right=440+440=880)
*/

let css = fs.readFileSync('styles/architecture-graph.css', 'utf8');

// Update all node widths to 440px and recompute positions
const newNodePositions = `#nInput    { width: 440px; left:  40px; top: 350px; }
#nSplit    { width: 440px; left: 530px; top: 360px; }
#nCompress { width: 440px; left:1000px; top: 190px; }
#nProtect  { width: 440px; left:1000px; top: 630px; }
#nMerge    { width: 440px; left:1590px; top: 350px; }
#nPrefill  { width: 440px; left: 440px; top:1000px; }
#nDraft    { width: 440px; left: 900px; top:1000px; }
#nVerify   { width: 440px; left: 900px; top:1260px; }
#nBuffer   { width: 440px; left: 440px; top:1260px; }
#nFinal    { width: 440px; left:  40px; top:1100px; }

#groupCompression {
    left: 480px;
    top: 150px;
    width: 1020px;
    height: 750px;
    background: rgba(255, 80, 0, 0.06);
}

#groupDFlash {
    left: 400px;
    top: 920px;
    width: 1000px;
    height: 580px;
    background: rgba(0, 210, 170, 0.08);
}

#groupDFlashLabel {
    left: 650px;
    top: 936px;
    background: var(--cyan);
}`;

css = css.replace(
  /#nInput[^]+?#groupDFlashLabel\s*\{[^}]+\}/s,
  newNodePositions
);

// Also remove old .node width from base style (so per-node widths dominate)
// The base .node has width: 300px, that's fine since per-node rules override

fs.writeFileSync('styles/architecture-graph.css', css);
console.log('CSS done');

// Update edges to match new widths
let html = fs.readFileSync('index.html', 'utf8');

// E5: nSplit right x was 950 → now 970
html = html.replace(/d="M 950 460 H 975 V 340 H 1000"/g, 'd="M 970 460 H 995 V 340 H 1000"');
// E6: nSplit right x was 950 → now 970
html = html.replace(/d="M 950 560 H 975 V 780 H 1000"/g, 'd="M 970 560 H 995 V 780 H 1000"');
// E3: nMerge right x was 2010 → now 2030
html = html.replace(/d="M 2010 500 V 1200"/g, 'd="M 2030 500 V 1200"');
// E1: nInput right was 430 → now 480
html = html.replace(/d="M 430 500 H 480"/g, 'd="M 480 500 H 490"');
// E2: groupComp right was 1540 → now 1500 (1020+480=1500)
html = html.replace(/d="M 1540 525 H 1590"/g, 'd="M 1500 500 H 1590"');
// E7: nPrefill right was 740 → now 880
html = html.replace(/d="M 740 1100 H 900"/g, 'd="M 880 1100 H 900"');
// E8: nDraft bottom-center X was 1050 → now 1120
html = html.replace(/d="M 1050 1200 V 1260"/g, 'd="M 1120 1200 V 1260"');
// E9: nVerify→nBuffer: nBuffer right was 740 → now 880
html = html.replace(/d="M 900 1360 H 740"/g, 'd="M 900 1360 H 880"');
// E10: nBuffer top-center X was 590 → now 660; nPrefill bottom-center X → 660
html = html.replace(/d="M 590 1260 V 1200"/g, 'd="M 660 1260 V 1200"');

fs.writeFileSync('index.html', html);
console.log('HTML done');
