const fs = require('fs');

/*
NEW LAYOUT DESIGN
==================

SCENE: 2200 wide × 1800 tall  (keep width manageable, grow height)

TOP ROW (main pipeline) at Y ≈ 500:
  nInput: left=40, top=350, w=390      → right=(430, 500)
  groupComp: left=480, top=150, w=1060, h=750   → right=(1540, 525)
    nSplit:   left=530, top=360, w=420           center-y=500
    nCompress: left=1000, top=190, w=440         center-y=340
    nProtect:  left=1000, top=630, w=400         center-y=780
  nMerge: left=1590, top=350, w=420    left=(1590, 500), right=(2010, 500)

BOTTOM CLUSTER at Y ≈ 1050:
  nFinal: left=40, top=1050, w=300     center=(190, 1175) – below ORIGINAL PROMPT

  Connecting edge: nMerge right(2010,500) V down to groupDFlash top (at y=950)
  
  groupDFlash: left=300, top=850, w=1640, h=500
    right edge = 1940
    center-left = (300, 1100)
    center-right = (1940, 1100)
  
  Inside D-Flash:
    nPrefill: left=340, top=940, w=300    center=(490, 1090)
    nDraft:   left=800, top=940, w=300    center=(950, 1090)
    nVerify:  left=800, top=1170, w=300   center=(950, 1320)
    nBuffer:  left=340, top=1170, w=300   center=(490, 1320)

  FINAL OUTPUT: left=40, top=1050, w=300
    → connects from groupDFlash left edge (300, 1100)

  Connecting path from nMerge → groupDFlash:
    M 2010 500 H 2080 V 1100 H 1940  ← enter groupDFlash right

  Wait, but nMerge is at x=1590–2010. groupDFlash is at x=300–1940.
  If nMerge is to the RIGHT of groupDFlash (x=1590 vs groupDFlash right=1940)... they overlap!
  
  Let's separate them. 
  
  Option: nMerge right egress goes DOWN-LEFT to groupDFlash right:
    nMerge right = (2010, 500)
    Route: H right → V down → H left into groupDFlash right center (1940, 1100)
    Path: M 2010 500 H 2080 V 1100 H 1940 → into cluster
    
  But nMerge right = 2010, groupDFlash right = 1940.
  2010 > 1940 so: M 2010 500 V 1100 H 1940
  That's a clean L-shaped path.
  
  FINAL OUTPUT → connected from groupDFlash LEFT:
    groupDFlash left center = (300, 1100)
    nFinal right center = (340, 1175)
    Path: M 300 1100 H 40 V 1175 ← awkward, goes left of groupDFlash
    
  Better: nFinal is to the LEFT of groupDFlash (x=40, groupDFlash left=300)
    nFinal right = (340, 1175)
    groupDFlash left-center = (300, 1100) 
    Edge: groupDFlash left (300,1100) → H left → (40+300=340, 1100) → hmm nFinal left=40
    Edge: M 300 1100 H 40 V 1200 – weird
    
  Simpler: put nFinal to the LEFT with connector:
    Edge: M 300 1100 → H 0 → impossible
    
  Actually cleanest: put nFinal BELOW groupDFlash
    nFinal: left=820, top=1460, w=300  → center=(970, 1560)
    Edge from groupDFlash bottom center: M 970 1350 V 1460 → clean vertical
    
  Then overall scene: 2200 wide × 1700 tall

  But user said FINAL OUTPUT below ORIGINAL PROMPT!
  
  So nFinal should be at roughly x=40–340, y=1050+.
  
  Let me restructure:
  
  D-Flash cluster: placed such that its LEFT edge aligns near x=40 (or nFinal x)
  Or D-Flash cluster starts at x=420 (right of nFinal), 
  nFinal is to the left, and an edge goes from cluster left → nFinal right.
  
  CLEAN DESIGN:
  
  nFinal: left=40, top=1100, w=300  → center=(190, 1250), right=(340,1250)
  groupDFlash: left=400, top=870, w=1600, h=680  → left=(400,1210), right=(2000,1210)
    center-left-y = 870+340=1210
  
  Edge dflash→final: M 400 1210 H 340 → nFinal right center
    Wait: nFinal right=340, top+h/2=1250. So M 400 1210 H 40 V 1250 
    (L-shape down to nFinal center-left = (40, 1250))
    OR: M 400 1250 H 340 → nFinal right-center (nFinal right=340, center-y=1250) → PERFECT H edge!
    So anchor cluster LEFT at y=1250: cluster left-center = (400, 1250)
    This means cluster center-Y = 1250 = top + h/2 → top = 1250 - h/2
    If h=680, top = 1250-340=910.
    Cluster: left=400, top=910, h=680, w=1600 → bottom=1590
    
  nFinal: left=40, top=1150, w=300, h~200 → right=(340,1250) ✓
  
  nMerge → groupDFlash:
    nMerge right = (2010, 500)  [top row]
    groupDFlash right-center = (2000, 1250) ← nMerge right ≈ same X!
    Path: M 2010 500 V 1250 H 2000 → into groupDFlash right side
    Simple L-shaped path downward. ✓
  
  D-Flash nodes (inside groupDFlash, absolute coords):
    nPrefill: left=440, top=1000, w=300 → right=(740,1100), center=(590,1100)
    nDraft:   left=900, top=1000, w=300 → left=(900,1100), top-center=(1050,1000)
    nVerify:  left=900, top=1250, w=300 → left=(900,1350), bottom-center=(1050,1450)
    nBuffer:  left=440, top=1250, w=300 → right=(740,1350), bottom-center=(590,1450)
    
    Cluster: top=910, bottom=910+680=1590 ✓ (all nodes ≤ bottom-40=1550 ✓)
    
    Loop:
    nPrefill right (740,1100) → H → nDraft left (900,1100) ← horizontal ✓
    nDraft top-center (1050,1000) → V up ← wait, loop goes DRAFT→VERIFY
    In standard flow: PREFILL→DRAFT→VERIFY→BUFFER→PREFILL
    So after DRAFT → VERIFY. Put VERIFY below DRAFT:
      nDraft bottom-center (1050,1200) → V down → nVerify top-center (1050,1250) ← 50px gap, too tight
    
    Better vertical spacing:
    nPrefill: top=980
    nDraft:   top=980
    nVerify:  top=1260
    nBuffer:  top=1260
    
    Gap between row 1 bottom(980+200=1180) and row 2 top(1260) = 80px ✓
    
    Loop edges (all midpoint at y=1080 for row1, y=1360 for row2):
    E-prefill→draft: M 740 1080 H 900  [horizontal]
    E-draft→verify: M 1050 1180 V 1260 [vertical down]
    E-verify→buffer: M 900 1360 H 740  [horizontal left]
    E-buffer→prefill: M 590 1260 V 1180 [vertical up] ← going UP!
    
    So nBuffer bottom → V UP into nPrefill bottom? No, we want top of nPrefill.
    
    Rethink: flow PREFILL→DRAFT (→ right), DRAFT→VERIFY (↓ down), VERIFY→BUFFER (← left), BUFFER→PREFILL (↑ up)
    This is a clockwise loop going:
    
    BUFFER(L,T)   VERIFY(R,T)
        ↑               ↓
    PREFILL(L,B)  DRAFT(R,B)
    
    So:
    nBuffer:  left=440, top=980, w=300   center=(590,1080)  right=(740,1080)
    nVerify:  left=900, top=980, w=300   center=(1050,1080)  left=(900,1080)
    nPrefill: left=440, top=1250, w=300  center=(590,1350)  right=(740,1350)
    nDraft:   left=900, top=1250, w=300  center=(1050,1350)  left=(900,1350)
    
    Flow: TARGET PREFILL → DFLASH DRAFT → TARGET VERIFY → OUTPUT BUFFER → TARGET PREFILL
    
    PREFILL(L,B) → DRAFT(R,B): M 740 1350 H 900 [horizontal right] ✓
    DRAFT(R,B) → VERIFY(R,T): M 1050 1250 V 1180 [vertical up] ✓ (DRAFT top → VERIFY bottom)
      Wait: nDraft top=1250 → DRAFT top-center=(1050,1250). nVerify bottom=980+200=1180.
      M 1050 1250 V 1180 → going up, arrow points up ✓
      But then → nVerify bottom-center should be target. nVerify bottom=(1050,1180). 
      Edge: M 1050 1250 V 1180 arrives at (1050,1180) = nVerify bottom ✓
    VERIFY(R,T) → BUFFER(L,T): M 900 1080 H 740 [horizontal left] ✓
    BUFFER(L,T) → PREFILL(L,B): M 590 1180 V 1250 [vertical down]
      nBuffer bottom-center = (590,1180). nPrefill top-center = (590,1250). 
      M 590 1180 V 1250 ✓
    
    Excellent! All 4 loop edges are clean orthogonal lines.
    
    Cluster ingress:
    nMerge right (2010, 500) → into groupDFlash right-center = (2000, 1210)
    Actually let me set groupDFlash cluster center-Y = (PREFILL_center_y + VERIFY_center_y)/2 = (1350+1080)/2 = 1215
    
    And cluster encompassing all nodes with padding:
    Nodes span: left=440 to right=1200 (900+300), top=980 to bottom=1450 (1250+200)
    With 40px padding each side:
    cluster left = 440-40 = 400
    cluster right = 1200+40 = 1240
    But we need the cluster right to be near 2000 to connect from nMerge!
    
    Let me extend the cluster rightward to make the ingress arrow visible:
    groupDFlash: left=400, top=920, width=1620, height=560
    → right = 2020, center-right-y = 920+280 = 1200
    nMerge right (2010, 500) → V down to (2010, 1200) → H left into cluster right (2020, 1200)
    
    Wait: nMerge right X = 2010, cluster right X = 2020. Same X almost.
    Path: M 2010 500 V 1200 H 2020 → 10px H move? Awkward.
    
    Let me use: M 2010 500 V 1200 (enter at right side of cluster).
    groupDFlash right = 2010 (match nMerge right), so the edge enters from top-right corner:
    
    Better: keep groupDFlash right=1960 and connect:
    M 2010 500 H 2050 V 1200 H 1960 → enter from right 
    
    OR: simply make groupDFlash extend to x=2060 and edge goes:
    M 2010 500 V 1200 (straight vertical down, arrives at right side of cluster)
    
    groupDFlash: left=400, top=920, width=1660, height=560 → right=2060
    center-right-y = 920 + 280 = 1200
    
    Edge from nMerge: M 2010 500 V 1200 → clean vertical
    
    But now nodes at left=440..1200 vs cluster right=2060... big empty right area.
    Let's add some routing:
    Entry path inside cluster goes from right (2060,1200) → H left → nPrefill or ingress.
    
    Actually in SVG layout, we can just show the edge going straight down:
    M 2010 500 V 1200 (enters cluster visually)
    Then separately inside cluster the nodes are arranged in their 2x2 grid.
    
    For cleanliness, let me finalize:
    
    groupDFlash: left=400, top=920, width=1660, height=560
    Right edge: 2060, center-Y: 1200 (920+280)
    
    nPrefill: left=440, top=1000, width=300  center=(590,1100), right=(740,1100)
    nDraft:   left=900, top=1000, width=300  center=(1050,1100), top=(1050,1000)
    nVerify:  left=900, top=1260, width=300  center=(1050,1360), bottom=(1050,1460)
    nBuffer:  left=440, top=1260, width=300  center=(590,1360), bottom=(590,1460)
    
    Wait cluster bottom = 920+560=1480. nVerify bottom = 1260+200=1460 ✓ (within cluster)
    nBuffer bottom = 1260+200=1460 ✓
    
    Loop (PREFILL→DRAFT→VERIFY→BUFFER→PREFILL):
    PREFILL right(740,1100) → DRAFT left(900,1100): M 740 1100 H 900 ✓
    DRAFT top-center(1050,1000) → VERIFY bottom-center(1050,1460): M 1050 1000 V ... wait
      DRAFT→VERIFY means we go from DRAFT bottom to VERIFY top?
      Or DRAFT top → VERIFY top? No - DRAFT bottom to VERIFY top makes more visual sense since VERIFY is below DRAFT.
      
      Wait: I have DRAFT at top=1000, bottom=1200. VERIFY at top=1260, bottom=1460.
      DRAFT goes DOWN into VERIFY:
      DRAFT bottom-center = (1050, 1200) → V down → VERIFY top-center = (1050, 1260)
      M 1050 1200 V 1260 ✓ (60px gap)
      
    VERIFY left(900,1360) → BUFFER right(740,1360): M 900 1360 H 740 ✓
    BUFFER top-center(590,1260) → PREFILL bottom-center(590,1200): M 590 1260 V 1200
      nBuffer top = 1260, so top-center = (590, 1260). Going UP.
      nPrefill bottom = 1000+200=1200, so bottom-center = (590,1200).
      M 590 1260 V 1200 ✓ (going up, arrow points up = toward PREFILL)
    
    So the visual is:
    BUFFER(L,top row)   VERIFY(R,top row)
         ↑                    ↓
    PREFILL(L,bot row)  DRAFT(R,bot row)
    
    Wait DRAFT is at top=1000 (same as PREFILL)... Let me reconsider.
    I defined PREFILL and DRAFT at top=1000, and BUFFER and VERIFY at top=1260.
    
    So the visual grid is:
    PREFILL(L,top)    DRAFT(R,top)
         ↑                 ↓
    BUFFER(L,bot)  ← VERIFY(R,bot)
    
    Flow: PREFILL→DRAFT (→ right at row top), DRAFT→VERIFY (↓ down), VERIFY→BUFFER (← left at row bot), BUFFER→PREFILL (↑ up)
    
    Arrows:
    PREFILL right → DRAFT left: horizontal → at y=1100
    DRAFT bottom → VERIFY top: vertical ↓
    VERIFY left → BUFFER right: horizontal ← at y=1360
    BUFFER top → PREFILL bottom: vertical ↑
    
    This creates a nice clockwise loop! ✓
    
  FINAL OUTPUT at x=40 connected from groupDFlash LEFT:
    groupDFlash left-center = (400, 1200)
    nFinal: left=40, top=1150, width=300, height~200 → right=(340,1250) center=(190,1250)
    Edge: M 400 1200 H 340 → nFinal right(340,1250)? Y doesn't match.
    
    Let me line up Y: if nFinal center-Y = 1250, and cluster left-center-Y should be 1250 too.
    cluster center-Y = 1200 (920+280). nFinal center-Y = 1250. Slight mismatch.
    
    Route: M 400 1200 H 40 V 1250 → L-shape to nFinal left-center (40,1250) ✓ 
    OR: adjust nFinal top: nFinal center-Y = 1200 → top = 1100
    Then: M 400 1200 H 340 → nFinal right-center (340,1200) ✓ PERFECT HORIZONTAL!
    
    nFinal: left=40, top=1100, width=300, height~200 → right=(340,1200), center=(190,1200)

SCENE SIZE: 2200 wide × 1700 tall (fits all nodes with margin)
*/

const nodes = {
  // Top row
  nInput:   { left: 40,   top: 350, w: 390 },  // right-center: (430,500)
  nSplit:   { left: 530,  top: 360, w: 420 },  // right-upper: (950,460), right-lower: (950,560)
  nCompress:{ left:1000,  top: 190, w: 440 },  // left-center: (1000,340)
  nProtect: { left:1000,  top: 630, w: 400 },  // left-center: (1000,780)
  nMerge:   { left:1590,  top: 350, w: 420 },  // right-center: (2010,500)
  
  // Bottom row (D-Flash)
  nPrefill: { left: 440,  top:1000, w: 300 },  // right: (740,1100)
  nDraft:   { left: 900,  top:1000, w: 300 },  // left: (900,1100)
  nBuffer:  { left: 440,  top:1260, w: 300 },  // top-center: (590,1260), right: (740,1360)
  nVerify:  { left: 900,  top:1260, w: 300 },  // left: (900,1360)
  nFinal:   { left:  40,  top:1100, w: 300 },  // right: (340,1200)
};

const clusters = {
  groupComp: { left: 480, top: 150, w: 1060, h: 750 },
  groupDFlash: { left: 400, top: 920, w: 1660, h: 560 },
};

// Verification
const nodeH = 200; // approximate default height for non-5-node items
console.log('=== CONTAINMENT ===');
const grp1 = { l:480, t:150, r:1540, b:900 };
const grp2 = { l:400, t:920, r:2060, b:1480 };

for (const [name,n] of [['nSplit',nodes.nSplit],['nCompress',nodes.nCompress],['nProtect',nodes.nProtect]]) {
  const r = {l:n.left, t:n.top, r:n.left+n.w, b:n.top+nodeH};
  const ok = r.l>=grp1.l && r.t>=grp1.t && r.r<=grp1.r && r.b<=grp1.b;
  console.log(`${name} in groupComp: ${ok?'PASS ✓':'FAIL ✗'} r=${r.r} b=${r.b} vs ${grp1.r},${grp1.b}`);
}
for (const [name,n] of [['nPrefill',nodes.nPrefill],['nDraft',nodes.nDraft],['nBuffer',nodes.nBuffer],['nVerify',nodes.nVerify]]) {
  const r = {l:n.left, t:n.top, r:n.left+n.w, b:n.top+nodeH};
  const ok = r.l>=grp2.l && r.t>=grp2.t && r.r<=grp2.r && r.b<=grp2.b;
  console.log(`${name} in groupDFlash: ${ok?'PASS ✓':'FAIL ✗'} r=${r.r} b=${r.b} vs ${grp2.r},${grp2.b}`);
}

console.log('\n=== EDGES ===');
console.log('E1 nInput→groupComp: M 430 500 H 480');
console.log('E2 groupComp→nMerge: M 1540 525 H 1590');
console.log('E3 nMerge→groupDFlash (via right→down): M 2010 500 V 1200');
console.log('E4 groupDFlash→nFinal: M 400 1200 H 340');
console.log('E5 nSplit→nCompress: M 950 460 H 975 V 340 H 1000');
console.log('E6 nSplit→nProtect: M 950 560 H 975 V 780 H 1000');
console.log('E7 nPrefill→nDraft: M 740 1100 H 900');
console.log('E8 nDraft→nVerify: M 1050 1200 V 1260');
console.log('E9 nVerify→nBuffer: M 900 1360 H 740');
console.log('E10 nBuffer→nPrefill: M 590 1260 V 1200');
