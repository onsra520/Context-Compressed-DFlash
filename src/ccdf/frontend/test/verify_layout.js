// Verify that all nodes fit inside their containers and no overlap
const nodes = {
  nInput:   { l:40,   t:480, w:390, h:220 },
  nSplit:   { l:530,  t:455, w:420, h:280 },
  nCompress:{ l:1000, t:280, w:440, h:300 },
  nProtect: { l:1000, t:710, w:400, h:200 },
  nMerge:   { l:1590, t:465, w:420, h:250 },
  nPrefill: { l:2100, t:480, w:300, h:200 },
  nDraft:   { l:2560, t:480, w:300, h:200 },
  nVerify:  { l:2560, t:170, w:300, h:200 },
  nBuffer:  { l:2100, t:170, w:300, h:200 },
  nFinal:   { l:3410, t:410, w:300, h:200 },
};
const grp1 = { l:480,  t:250,  r:1540, b:1000 };
const grp2 = { l:2060, t:100,  r:3400, b:920  };

const r = n => ({ l:n.l, t:n.t, r:n.l+n.w, b:n.t+n.h });

console.log('=== CONTAINMENT CHECK ===');

// nSplit, nCompress, nProtect in grp1
for (const [name, node] of [['nSplit',nodes.nSplit],['nCompress',nodes.nCompress],['nProtect',nodes.nProtect]]) {
  const rr = r(node);
  const ok = rr.l >= grp1.l && rr.t >= grp1.t && rr.r <= grp1.r && rr.b <= grp1.b;
  console.log(`${name} in groupComp: ${ok ? 'PASS ✓' : 'FAIL ✗'} [l=${rr.l},t=${rr.t},r=${rr.r},b=${rr.b}] vs cluster [l=${grp1.l},t=${grp1.t},r=${grp1.r},b=${grp1.b}]`);
}

// nPrefill, nDraft, nVerify, nBuffer in grp2
for (const [name, node] of [['nPrefill',nodes.nPrefill],['nDraft',nodes.nDraft],['nVerify',nodes.nVerify],['nBuffer',nodes.nBuffer]]) {
  const rr = r(node);
  const ok = rr.l >= grp2.l && rr.t >= grp2.t && rr.r <= grp2.r && rr.b <= grp2.b;
  console.log(`${name} in groupDFlash: ${ok ? 'PASS ✓' : 'FAIL ✗'} [l=${rr.l},t=${rr.t},r=${rr.r},b=${rr.b}] vs cluster [l=${grp2.l},t=${grp2.t},r=${grp2.r},b=${grp2.b}]`);
}

// nFinal outside both clusters
const nFinalR = r(nodes.nFinal);
console.log(`nFinal outside grp1: ${nFinalR.l > grp1.r ? 'PASS ✓' : 'FAIL ✗'}`);
console.log(`nFinal outside grp2: ${nFinalR.l > grp2.r ? 'PASS ✓' : 'FAIL ✗'}`);
console.log(`nInput outside grp1: ${r(nodes.nInput).r < grp1.l ? 'PASS ✓' : 'FAIL ✗'}`);

// No overlaps among D-Flash nodes
console.log('\n=== D-FLASH OVERLAP CHECK ===');
const dflashNodes = [['nPrefill',nodes.nPrefill],['nDraft',nodes.nDraft],['nVerify',nodes.nVerify],['nBuffer',nodes.nBuffer]];
for (let i = 0; i < dflashNodes.length; i++) {
  for (let j = i+1; j < dflashNodes.length; j++) {
    const [an,a] = dflashNodes[i];
    const [bn,b] = dflashNodes[j];
    const ra = r(a), rb = r(b);
    const overlaps = ra.l < rb.r && ra.r > rb.l && ra.t < rb.b && ra.b > rb.t;
    console.log(`${an} vs ${bn}: ${overlaps ? 'OVERLAP ✗' : 'OK ✓'}`);
  }
}

// COMPRESSOR vs PROTECTED QUESTION gap
const compBot = nodes.nCompress.t + nodes.nCompress.h;
const protTop = nodes.nProtect.t;
console.log(`\nGap between COMPRESSOR bottom(${compBot}) and PROTECTED QUESTION top(${protTop}): ${protTop - compBot}px`);
