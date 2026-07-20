const fs = require('fs');

/*
====================================================
LAYOUT DESIGN
====================================================

Pipeline flows L→R at center Y ≈ 600 (scene height 1000)

ORIGINAL PROMPT (nInput): 
  width=390, left=40, top=407  → center=(235, 602)
  right edge = 430

CONTEXT COMPRESSION cluster (groupCompression):
  left=480, top=220, width=1040, height=740
  → right edge = 1520
  → center-left anchor: (480, 590)  [Y: top + height/2 = 220+370=590]
  → center-right anchor: (1520, 590)

  Inside cluster (coords relative to graphScene, i.e. absolute):
  PROMPT SEGMENTER (nSplit): width=420, left=520, top=400 → center=(730, 600)
    → right edge center-upper: (940, 520) → to Compressor
    → right edge center-lower: (940, 680) → to Protected Q
  
  COMPRESSOR (nCompress): width=440, left=1020, top=260 → top=(260+350/2=435), center=(1240, 435)
    → left edge center: (1020, 435)
    → right edge: (1460, 435) → feeds cluster egress
  
  PROTECTED QUESTION (nProtect): width=400, left=1020, top=720 → center=(1220, 830)
    → left edge center: (1020, 830)
    → right edge: (1420, 830) → feeds cluster egress

PROMPT COMPRESSION (nMerge):
  width=420, left=1570, top=465 → center=(1780, 600)
  → left edge: (1570, 600)  ← from cluster right (1520, 590) ≈ match
  → right edge: (1990, 600)

D-FLASH GENERATION LOOP cluster (groupDFlash):
  left=2040, top=160, width=1060, height=740
  → center-left anchor: (2040, 530)
  → center-right anchor: (3100, 530) 

  Inside cluster:
  TARGET PREFILL (nPrefill): width=300, left=2080, top=490 → center=(2230, 600)
    right edge: (2380, 600) → to Draft

  DFLASH DRAFT (nDraft): width=300, left=2540, top=490 → center=(2690, 600)
    top edge: (2690, 490) → to Verify going up

  TARGET VERIFY (nVerify): width=300, left=2540, top=220 → center=(2690, 310)
    left edge: (2540, 310) → to Buffer going left

  OUTPUT BUFFER (nBuffer): width=300, left=2080, top=220 → center=(2230, 310)
    bottom edge: (2230, 390) → to Prefill going down

  FINAL OUTPUT (nFinal): width=300, left=3150, top=465 → center=(3300, 600)
    left edge: (3150, 600) ← from cluster right (3100, 530) ≈

Let me recalculate to be precise and use manageable scene size.
Actually, let's keep scene width=3500, height=1000 for comfort.

Let's redefine:
- Main pipeline Y center = 600
- Everything flows L→R

ORIGINAL PROMPT:
  width=390, height~auto(~220), top = 600-110 = 490, left=40
  center-right = (430, 600)

CONTEXT COMPRESSION cluster:
  left=480, width=1040
  The cluster needs 44px top label, padding 40px each side
  Content area: left=520..1480 (width 960)
    nSplit: width=420, left=520, 
      Height auto, say ~280px. top = 600-140=460, so bottom~740
    nCompress: width=440, left=980
      Height auto, say ~300px, top=340
    nProtect: width=400, left=980
      Height auto, say ~220px, top=730

  Cluster top: 340-60=280, bottom=730+220+40=990
  → top=280, height=710

  Actually let's simplify: cluster top=250, height=760
  → bottom=1010 (just barely)
  
  Actually I should not go over 1000 in height. Let me adjust:
  nCompress top=340 → bottom=340+300=640
  nProtect top=700 → bottom=700+220=920
  Gap between: 700-640=60 (good)
  Cluster: top=260, height=700 → bottom=960 (fits in 1000)

  center-left anchor = (480, 260+350=610)
  center-right anchor = (1520, 610)

PROMPT COMPRESSION:
  left=1570, width=420, top=490, height~220
  center-left = (1570, 600)
  center-right = (1990, 600)

D-FLASH GENERATION LOOP:
  Input at (1990, 600) → cluster left edge at ~2040
  Cluster: left=2040, top=200, width=1100, height=800
  → right edge = 3140
  center-left = (2040, 600) → ingress to nPrefill

  nPrefill: left=2080, top=490, width=300 → center=(2230,600), right=(2380,600)
  nDraft: left=2560, top=490, width=300 → center=(2710,600), top-center=(2710,490)
  nVerify: left=2560, top=230, width=300 → center=(2710,310), left-center=(2560,310)
  nBuffer: left=2080, top=230, width=300 → center=(2230,310), bottom-center=(2230,390)

  Loop flow:
  nPrefill right (2380,600) → nDraft left (2560,600)  [horizontal]
  nDraft top (2710,490) → nVerify bottom (2710,390)   wait no. nDraft top=490, nVerify bottom=230+220=450 -- too close!
  
  Let me fix heights:
  nPrefill height~200: top=490, bottom=690
  nDraft height~200: top=490, bottom=690
  nVerify height~170: top=240, bottom=410
  nBuffer height~170: top=240, bottom=410
  
  Gap between nVerify bottom and nPrefill top: 490-410=80 (ok)
  
  Loop:
  nPrefill right (2380,590) → H to 2520 → nDraft left (2560,590) [horizontal]
  nDraft top-center (2710,490) → V up to (2710,410) → nVerify bottom-center (2710,410) [vertical]
  nVerify left-center (2560,325) → H left to (2080+300=2380?) no
  → nVerify left (2560, 325) → to nBuffer right (2080+300=2380, 325) 
  nBuffer bottom-center (2230,410) → V down to (2230, 490) → nPrefill top... 
  Wait, nPrefill top=490 which means top-center=(2230,490), but nPrefill left=2080.
  Actually bottom of nBuffer is (2230, 410). nPrefill top-center would be (2080+150=2230, 490).
  That works: (2230,410) → V down → (2230,490) nPrefill top.

  Cluster right egress at (3140, 600): That's after nDraft right (2560+300=2860, 590).
  We need an edge from the loop to cluster egress. This represents loop completion.
  The OUTPUT BUFFER conceptually feeds the output. 
  Actually the cluster output is OUTPUT BUFFER → FINAL OUTPUT.
  So we do: nBuffer right (2380, 325) → H to (3140, 325) → V down to (3140, 600) egress?
  That's messy. Let me reconsider.

  Better approach: nBuffer is the "done" state. Edge from nBuffer right goes directly out cluster to FINAL OUTPUT.
  So nBuffer at left=2080, right=2380, top=240, center=(2230, 325).
  FINAL OUTPUT at left=3190.
  
  Edge: nBuffer right (2380, 325) → H right to cluster right edge at X=3140 → no direct.
  Or just route: nBuffer right(2380,325) → H to (3190, 325) → V down to (3190, 600) → into nFinal center-left(3190,600)?
  That's clean! But FINAL OUTPUT needs top around 490.

  Let me settle:
  FINAL OUTPUT: left=3190, top=490, width=300, height~200 → center=(3340, 590)
  center-left = (3190, 590)

  Edge: nBuffer right(2380, 325) → H→ (3190,325) → V down to (3190,590) → into nFinal 

  But cluster right should be at 3190 too so this stays inside... 
  Actually nFinal is OUTSIDE the cluster. So cluster boundary = 3140, nFinal starts at 3190.

  Let's put it simply:
  groupDFlash: left=2040, width=1100, → right=3140
  nFinal: left=3190 (outside), top=490, width=300

  Edge: cluster right (3140, 600) → H→ nFinal left (3190, 600) short
  nBuffer feeds into cluster egress internally.
  We need an edge from within the loop to represent "loop done → output".
  
  In the architecture: OUTPUT BUFFER → TARGET PREFILL (loop back)
  The "completion" of the loop produces output somehow.
  But in the steps, the final step is FINAL OUTPUT...

  Let me look at what architectureSteps defines as the last few steps to understand the edge from D-Flash → FINAL OUTPUT.
  
  Looking at the mock data, there is a step for final output. The edge "dflash-container-to-final-output" represents this.
  In practice, OUTPUT BUFFER contains the accumulated tokens which go to FINAL OUTPUT.
  The visual edge should go from the OUTPUT BUFFER or from the cluster right edge to FINAL OUTPUT.

  For simplicity in routing:
  - The cluster egress edge goes from nBuffer right → across → FINAL OUTPUT
  - The edge id is "dflash-container-to-final-output" 
  - Source: nBuffer right center = (2380, 325)
  - Target: nFinal left center = (3190, 600)
  - Route: (2380,325) H→ (3340,325) V↓ (3340,600) H← (3190,600) - awkward
  - Better: (2380,325) H→(3190,325) V↓(3190,600) then into nFinal top-left corner? No.
  
  Actually let me change nFinal position: left=3190, top=240 → center=(3340, 325)
  Then edge: nBuffer right(2380,325) → H → nFinal left(3190,325). Clean horizontal!

  And the external pipeline (nMerge → groupDFlash): 
  nMerge right(1990,600) → H → groupDFlash left(2040,600). Very short gap, 50px.
  Then internal: groupDFlash ingress(2040,600) → nPrefill left(2080,600). Also short.

Let me finalize the design:

SCENE: width=3600, height=1050 (extend scene to fit all nodes)

nInput: left=40, top=400, width=390, min-height=220
  right-center: (430, 510)  [top+min-height/2 = 400+110=510]

groupCompression: left=480, top=250, width=1060, height=750
  left-center: (480, 625) [250+375=625]
  right-center: (1540, 625)

nSplit: left=530, top=455, width=420, height=auto, min-height=280
  center: (740, 595)  [top+minH/2=455+140=595]
  right-center: (950, 595)

nCompress: left=1000, top=290, width=440, height=auto, min-height=300
  center: (1220, 440) [290+150=440]
  left-center: (1000, 440)
  right-center: (1440, 440) → feeds cluster egress internally

nProtect: left=1000, top=700, width=400, height=auto, min-height=200
  center: (1200, 800) [700+100=800]
  left-center: (1000, 800)
  right-center: (1400, 800) → feeds cluster egress internally

Checking cluster: 
  nCompress: left=1000, right=1440, top=290, bottom=590
  nProtect: left=1000, right=1400, top=700, bottom=900
  nSplit: left=530, right=950, top=455, bottom=735
  Cluster: left=480, right=1540, top=250, bottom=1000 (h=750) ✓
  All nodes inside ✓ (1440<1540, 1400<1540, 900<1000) ✓

nMerge: left=1590, top=465, width=420, min-height=250
  center: (1800, 590)
  left-center: (1590, 590) ← from cluster right (1540, 625) [slight Y offset, use (1590, 607)]
  right-center: (2010, 590)

groupDFlash: left=2060, top=130, width=1220, height=740
  left-center: (2060, 500) [130+370=500]
  right-center: (3280, 500)

nPrefill: left=2100, top=490, width=300, min-height=200
  center: (2250, 590) [490+100=590]
  left-center: (2100, 590) ← cluster ingress
  right-center: (2400, 590) → to nDraft

nDraft: left=2550, top=490, width=300, min-height=200  
  center: (2700, 590)
  left-center: (2550, 590) ← from nPrefill
  top-center: (2700, 490) → V up → to nVerify bottom

nVerify: left=2550, top=190, width=300, min-height=200
  center: (2700, 290) [190+100=290]
  bottom-center: (2700, 390) ← from nDraft
  left-center: (2550, 290) → H left → to nBuffer right

nBuffer: left=2100, top=190, width=300, min-height=200
  center: (2250, 290)
  right-center: (2400, 290) ← from nVerify
  bottom-center: (2250, 390) → V down → to nPrefill top

nFinal: left=3330, top=190, width=300, min-height=200
  center: (3480, 290)
  left-center: (3330, 290) ← from nBuffer right?
  
Hmm nFinal needs to be accessible from cluster output.
Let me change: nFinal is at left=3330. Cluster right = 3280. 
Edge from cluster right (3280, 500) → nFinal left (3330, ...). 

But nFinal top=190 puts center at 290, which means edge would be:
(3280, 500) → H→ (3330, 500) → V up → (3330, 290) → into nFinal left... that goes backwards.

Let me put nFinal outside to the right but at a convenient Y:
nFinal: left=3330, top=400, width=300, min-height=200
  center Y = 500
  left-center: (3330, 500)

Edge: cluster right (3280, 500) → H → nFinal left (3330, 500). Perfect!

Now the cluster output arc from nBuffer → cluster egress → FINAL OUTPUT:
- nBuffer needs an edge to cluster egress
- The cluster right-center is at (3280, 500)
- But nBuffer is at center (2250, 290) - far from egress on X axis and different Y

For the D-Flash loop visual, the "output" comes from nBuffer. 
One approach: nBuffer has a right edge that goes to nFinal directly (treating it as the cluster's logical output), with the path: 
nBuffer right (2400, 290) → H to (3330, 290) → V down to (3330, 500) → into nFinal left (3330, 500)

But we need the cluster's right border to NOT be crossed by this edge from inside... 
Actually the SVG path can extend beyond the cluster div borders - the cluster is just a visual div, edges are drawn in the SVG layer above.

FINAL REVISED DESIGN:
Let me just do a clean approach where everything fits.

Scene: 3600 × 1050

Node Y-center alignment at Y≈590 for the main pipeline.

nInput: left=40, top=480, width=390, → right=(430, 590)
groupComp: left=480, top=250, width=1060, height=750 → right=(1540, 625)
  nSplit: left=530, top=455, width=420 → right=(950, 595)
  nCompress: left=1000, top=280, width=440 → center=(1220, 430)
  nProtect: left=1000, top=710, width=400 → center=(1200, 810)
nMerge: left=1590, top=465, width=420 → left=(1590, 590), right=(2010, 590)
groupDFlash: left=2060, top=100, width=1340, height=820 → right=(3400, 510)
  nPrefill: left=2100, top=490, width=300 → right=(2400, 590)
  nDraft: left=2550, top=490, width=300 → top=(2700, 490), left=(2550, 590)
  nVerify: left=2550, top=160, width=300 → left=(2550, 260), bottom=(2700, 360)
  nBuffer: left=2100, top=160, width=300 → right=(2400, 260), bottom=(2250, 360)
nFinal: left=3410, top=410, width=300 → left=(3410, 510)

Cluster groupDFlash right = 3400, nFinal left = 3410 → 10px gap (fine)
groupDFlash center-right = (3400, 100+410=510) = (3400, 510) ✓

*/

// Final coordinates used:
const L = {
  // Scene
  sceneW: 3600, sceneH: 1050,

  // nInput
  nInput:  { left: 40,   top: 480, w: 390 },  // right-center: (430, 590)
  
  // Context Compression cluster
  group1:  { left: 480,  top: 250, w: 1060, h: 750 },  // right=(1540), center-Y=625
  
  // Inside cluster (absolute positions in graphScene):
  nSplit:  { left: 530,  top: 455, w: 420 },  // right=(950), center-Y=595
  nCompress:{ left:1000, top: 280, w: 440 },  // right=(1440), center-Y=430
  nProtect: { left:1000, top: 710, w: 400 },  // right=(1400), center-Y=810

  // nMerge (Prompt Compression)
  nMerge:  { left: 1590, top: 465, w: 420 },  // left=(1590,590), right=(2010,590)

  // D-Flash cluster
  group2:  { left: 2060, top: 100, w: 1340, h: 820 }, // right=(3400), center-Y=510

  // Inside D-Flash cluster:
  nPrefill: { left: 2100, top: 480, w: 300 }, // right=(2400,580), left=(2100,580)
  nDraft:   { left: 2560, top: 480, w: 300 }, // top-c=(2710,480), left=(2560,580)
  nVerify:  { left: 2560, top: 170, w: 300 }, // left-c=(2560,270), bottom=(2710,370)
  nBuffer:  { left: 2100, top: 170, w: 300 }, // right-c=(2400,270), bottom=(2250,370)

  // nFinal (Final Output)
  nFinal:   { left: 3410, top: 410, w: 300 }, // left=(3410,510)
};

// Compute derived values
const nInput_cx = L.nInput.left + L.nInput.w/2;
const nInput_right_y = L.nInput.top + 110;  // approximate center (min-height 220)
const nInput_right_x = L.nInput.left + L.nInput.w;

const grp1_left_x = L.group1.left;
const grp1_left_y = L.group1.top + L.group1.h/2;
const grp1_right_x = L.group1.left + L.group1.w;
const grp1_right_y = grp1_left_y;

const nSplit_right_x = L.nSplit.left + L.nSplit.w;
const nSplit_center_y = L.nSplit.top + 140; // ~half of min 280 content
// Two source anchors on right of nSplit:
const nSplit_right_upper_y = L.nSplit.top + 90;  // upper third
const nSplit_right_lower_y = L.nSplit.top + 190; // lower third

const nCompress_left_x = L.nCompress.left;
const nCompress_center_y = L.nCompress.top + 150; // ~half of ~300px

const nProtect_left_x = L.nProtect.left;
const nProtect_center_y = L.nProtect.top + 100; // ~half of ~200px

const nMerge_left_x = L.nMerge.left;
const nMerge_right_x = L.nMerge.left + L.nMerge.w;
const nMerge_center_y = L.nMerge.top + 125; // ~half of ~250px

const grp2_left_x = L.group2.left;
const grp2_left_y = L.group2.top + L.group2.h/2;
const grp2_right_x = L.group2.left + L.group2.w;
const grp2_right_y = grp2_left_y;

const nPrefill_left_x = L.nPrefill.left;
const nPrefill_right_x = L.nPrefill.left + L.nPrefill.w;
const nPrefill_center_y = L.nPrefill.top + 100;

const nDraft_left_x = L.nDraft.left;
const nDraft_top_center_x = L.nDraft.left + L.nDraft.w/2;
const nDraft_top_y = L.nDraft.top;
const nDraft_center_y = L.nDraft.top + 100;

const nVerify_left_x = L.nVerify.left;
const nVerify_bottom_center_x = L.nVerify.left + L.nVerify.w/2;
const nVerify_bottom_y = L.nVerify.top + 200; // approximate bottom of ~200px node
const nVerify_center_y = L.nVerify.top + 100;

const nBuffer_right_x = L.nBuffer.left + L.nBuffer.w;
const nBuffer_bottom_center_x = L.nBuffer.left + L.nBuffer.w/2;
const nBuffer_bottom_y = L.nBuffer.top + 200;
const nBuffer_center_y = L.nBuffer.top + 100;

const nFinal_left_x = L.nFinal.left;
const nFinal_center_y = L.nFinal.top + 100;

// Midpoint for routing
const mid_seg_compress_x = nSplit_right_x + 30; // routing elbow X

console.log('=== GEOMETRY ===');
console.log(`nInput: left=${L.nInput.left}, top=${L.nInput.top}, width=${L.nInput.w}`);
console.log(`  right-center: (${nInput_right_x}, ${nInput_right_y})`);
console.log(`groupComp: left=${L.group1.left}, top=${L.group1.top}, w=${L.group1.w}, h=${L.group1.h}`);
console.log(`  ingress (left-center): (${grp1_left_x}, ${grp1_left_y})`);
console.log(`  egress (right-center): (${grp1_right_x}, ${grp1_right_y})`);
console.log(`nSplit right-upper: (${nSplit_right_x}, ${nSplit_right_upper_y})`);
console.log(`nSplit right-lower: (${nSplit_right_x}, ${nSplit_right_lower_y})`);
console.log(`nCompress left-center: (${nCompress_left_x}, ${nCompress_center_y})`);
console.log(`nProtect left-center: (${nProtect_left_x}, ${nProtect_center_y})`);
console.log(`nMerge left: (${nMerge_left_x}, ${nMerge_center_y})`);
console.log(`nMerge right: (${nMerge_right_x}, ${nMerge_center_y})`);
console.log(`groupDFlash left-center: (${grp2_left_x}, ${grp2_left_y})`);
console.log(`groupDFlash right-center: (${grp2_right_x}, ${grp2_right_y})`);
console.log(`nFinal left-center: (${nFinal_left_x}, ${nFinal_center_y})`);

// Elbow routing mid-x between Segmenter right and Compressor/Protect left
const elbX = nSplit_right_x + 25;
console.log(`\n=== EDGES ===`);
console.log(`E1 orig→cluster: M ${nInput_right_x} ${nInput_right_y} H ${grp1_left_x}`);
console.log(`E2 cluster→merge: M ${grp1_right_x} ${grp1_right_y} H ${nMerge_left_x}`);
console.log(`E3 merge→dflash: M ${nMerge_right_x} ${nMerge_center_y} H ${grp2_left_x}`);
console.log(`E4 dflash→final: M ${grp2_right_x} ${grp2_right_y} H ${nFinal_left_x}`);
console.log(`E5 split→compress: M ${nSplit_right_x} ${nSplit_right_upper_y} H ${elbX} V ${nCompress_center_y} H ${nCompress_left_x}`);
console.log(`E6 split→protect: M ${nSplit_right_x} ${nSplit_right_lower_y} H ${elbX} V ${nProtect_center_y} H ${nProtect_left_x}`);
console.log(`E7 prefill→draft: M ${nPrefill_right_x} ${nPrefill_center_y} H ${nDraft_left_x}`);
console.log(`E8 draft→verify: M ${nDraft_top_center_x} ${nDraft_top_y} V ${nVerify_bottom_y}`);
console.log(`E9 verify→buffer: M ${nVerify_left_x} ${nVerify_center_y} H ${nBuffer_right_x}`);
console.log(`E10 buffer→prefill: M ${nBuffer_bottom_center_x} ${nBuffer_bottom_y} V ${nPrefill_center_y}`);  // Hmm this would go into nPrefill vertically - no anchor rule broken
// Actually must go into top edge of nPrefill from buffer bottom:
console.log(`E10 buffer→prefill top: M ${nBuffer_bottom_center_x} ${nBuffer_bottom_y} V ${L.nPrefill.top}`);
