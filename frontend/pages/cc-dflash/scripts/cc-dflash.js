// ─── Canvases ────────────────────────────────────────────────────────────
const canvas = document.getElementById("particles");
const ctx = canvas.getContext("2d");
// Particles are drawn above the core canvas so some streaks can pass over the
// black-hole shadow and fade into it, which adds depth.
canvas.style.zIndex = "4";

// Second canvas sits below particles for core glow effects (below text at 5)
const coreCanvas = document.createElement("canvas");
coreCanvas.style.cssText =
    "position:fixed;inset:0;width:100%;height:100%;z-index:3;pointer-events:none;";
document.querySelector(".stage").appendChild(coreCanvas);
const cctx = coreCanvas.getContext("2d");

const nebulaCanvas = document.getElementById("nebulaClouds");
let nebula = null;

let width = 0, height = 0;
let dpr = Math.min(window.devicePixelRatio || 1, 2);
let particles = [];
let bottomDust = [];
let tick = 0;
let scrollTarget = 0;
let scrollSmooth = 0;
let rngState = 0xC0DDF1A5;

function rand() {
    // Deterministic LCG so the field is stable across frames and does not
    // rely on nondeterministic random values during rendering.
    rngState = (Math.imul(rngState, 1664525) + 1013904223) >>> 0;
    return rngState / 4294967296;
}

function clamp(v, lo, hi) {
    return Math.max(lo, Math.min(hi, v));
}

function lerp(a, b, t) {
    return a + (b - a) * t;
}

function smoothstep(edge0, edge1, x) {
    const t = clamp((x - edge0) / Math.max(0.0001, edge1 - edge0), 0, 1);
    return t * t * (3 - 2 * t);
}

function updateScrollTarget() {
    const doc = document.documentElement;
    const maxScroll = Math.max(1, doc.scrollHeight - window.innerHeight);
    scrollTarget = clamp((window.scrollY || doc.scrollTop || 0) / maxScroll, 0, 1);
}

// ─── Constants ───────────────────────────────────────────────────────────
// BH center matches CSS translate(-50%, -52%)
const BH_CY_FRAC = 0.48;
// Disc perspective squish — matches visual disc tilt
const SQUISH = 0.36;
// Rotation direction: all particles orbit counter-clockwise (negative = CCW)
const SPIN_DIR = -1;
// Event horizon semi-axes — larger for better symmetry at typical viewport
const EH_RX = 0.200;
const EH_RY = 0.078;
// Spawn band
const R_MIN_FRAC = 0.28;
const R_MAX_FRAC = 1.12;

function bhCenter(exitProgress = 0) {
    // As the user scrolls, the title/black-hole influence leaves the viewport.
    // The particles then stop orbiting and transition to the scroll-flow field.
    return {
        x: width * 0.5,
        y: height * BH_CY_FRAC - height * 0.86 * exitProgress,
    };
}

// ─── Spawn ───────────────────────────────────────────────────────────────
function spawnParticle(cx, cy, forceOuter, idx = 0, total = 1) {
    const mR = Math.min(width, height);
    const ehRx = mR * EH_RX;
    const rMin = forceOuter
        ? mR * 0.60
        : Math.max(mR * R_MIN_FRAC, ehRx * 1.25);
    const rMax = mR * R_MAX_FRAC;

    // Bias toward mid-ring for density
    const u = rand();
    const radial = rMin + (rMax - rMin) * (0.3 * u * u + 0.7 * u);
    const normR = radial / (mR * R_MAX_FRAC);          // 0 = core, 1 = far

    // Angle: random full circle
    const angle = rand() * Math.PI * 2;

    // Orbital speed (Keplerian: ω ∝ r^-1.5 in 3D, simplified here)
    const orbitSpd = SPIN_DIR * (0.006 + 0.022 * Math.pow(1 - normR, 1.8))
        * (0.75 + rand() * 0.5);

    // Infall (radial drift inward) — slow far out, fast near event horizon
    const infallBase = 0.12 + 1.6 * Math.pow(1 - normR, 2.4);
    const infallRate = infallBase * (0.65 + rand() * 0.7);

    // Visual
    const baseSize = 0.25 + rand() * 1.3 * (0.3 + normR * 0.7);
    const baseAlpha = 0.08 + rand() * 0.80 * normR;

    // Final scroll-field target. Use a stratified distribution so the whole screen,
    // including the lower-right corner, is guaranteed to receive particles.
    const aspect = width / Math.max(1, height);
    const cols = Math.max(1, Math.ceil(Math.sqrt(total * aspect)));
    const rows = Math.max(1, Math.ceil(total / cols));
    const col = idx % cols;
    const row = Math.floor(idx / cols);
    const cellU = clamp((col + 0.08 + rand() * 0.84) / cols, 0, 0.999);
    const cellV = clamp((row + 0.08 + rand() * 0.84) / rows, 0, 0.999);

    let fieldX = cellU * width;
    let fieldY = cellV * height;

    // Reserve explicit subsets for the lower region so the whole bottom edge fills in.
    // This fixes the empty-looking lower corner / lower band at full scroll.
    const lowerBandCount = Math.max(28, Math.floor(total * 0.18));
    const lowerRightCount = Math.max(16, Math.floor(total * 0.08));
    const lowerBandStart = total - lowerBandCount;
    const lowerRightStart = total - lowerRightCount;

    // Dedicated bottom strip across most of the width.
    if (idx >= lowerBandStart) {
        fieldX = width * (0.04 + 0.94 * rand());
        fieldY = height * (0.84 + 0.15 * rand());
    }

    // Denser lower-right corner reserve.
    if (idx >= lowerRightStart) {
        fieldX = width * (0.72 + 0.27 * rand());
        fieldY = height * (0.80 + 0.19 * rand());
    }

    // Fill order:
    // 1 2 3 ...
    // 2 3 ...
    // 3 ...
    // Upper-left reveals first, lower-right reveals last.
    const fillRank = clamp(0.5 * (fieldX / Math.max(1, width) + fieldY / Math.max(1, height)), 0, 1);

    // Each particle first travels along a parabolic / Bezier stream, then settles
    // into the field target to fill the background.
    const flowT = clamp(fillRank + (rand() - 0.5) * 0.24, 0, 1);
    const laneOffset = (rand() - 0.5) * mR * (0.10 + 0.24 * rand());

    // Trail length multiplier (longer for faster inner particles)
    const trailMult = 0.5 + rand() * 1.2;
    const streamSpeed = 0.0014 + rand() * 0.0034;
    const fieldDriftAmp = (0.5 + rand() * 1.2) * mR * 0.0028;

    return {
        angle, radial, normR,
        orbitSpd, infallRate,
        r: baseSize, baseAlpha, trailMult,
        tw: rand() * Math.PI * 2,
        twSpd: 0.003 + rand() * 0.016,
        fieldX, fieldY, fillRank, flowT, laneOffset,
        streamSpeed, fieldDriftAmp,
        fieldAlpha: 0.08 + rand() * 0.50,
        shape: rand() < 0.18 ? "square" : "dot",
        phase: rand() * Math.PI * 2,
        // store prev screen pos for streak
        prevX: null, prevY: null,
    };
}

// ─── Resize ──────────────────────────────────────────────────────────────
function resize() {
    width = window.innerWidth;
    height = window.innerHeight;
    dpr = Math.min(window.devicePixelRatio || 1, 2);

    for (const cv of [canvas, coreCanvas]) {
        cv.width = Math.floor(width * dpr);
        cv.height = Math.floor(height * dpr);
        cv.style.width = width + "px";
        cv.style.height = height + "px";
    }
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    cctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    seedParticles();
    resizeNebula();
}

function seedParticles() {
    // Stable seed per viewport size.
    rngState = (0xC0DDF1A5 ^ Math.floor(width * 31 + height * 17)) >>> 0;
    const count = Math.floor(Math.min(1180, Math.max(620, width / (width < 760 ? 2.8 : 1.72))));
    const { x: cx, y: cy } = bhCenter(0);
    particles = Array.from({ length: count }, (_, i) => spawnParticle(cx, cy, false, i, count));
    seedBottomDust();
}

function seedBottomDust() {
    // Extra low-band field that only appears near the end of the scroll.
    // It guarantees the bottom-right and bottom edge are populated even when
    // the scroll smoothing has not numerically reached 1 yet.
    const count = Math.floor(Math.min(260, Math.max(120, width / (width < 760 ? 8.5 : 6.0))));
    bottomDust = Array.from({ length: count }, (_, i) => {
        const rightBias = i > count * 0.56;
        const x = rightBias
            ? width * (0.58 + rand() * 0.40)
            : width * (0.02 + rand() * 0.96);
        const y = height * (0.78 + rand() * 0.205);
        return {
            x,
            y,
            size: 0.35 + rand() * 1.05,
            alpha: 0.05 + rand() * 0.28,
            phase: rand() * Math.PI * 2,
            drift: 0.25 + rand() * 1.2,
            shape: rand() < 0.22 ? "square" : "dot",
            rank: clamp(0.5 * (x / Math.max(1, width) + y / Math.max(1, height)), 0, 1),
        };
    });
}

// ─── Spiral streak ───────────────────────────────────────────────────────
// Instead of a geometric guess, we store the previous frame's position
// and draw a line from prevX/Y → currX/Y. This IS the spiral direction.
function drawSpiral(p, px, py, normR, alpha, size) {
    if (p.prevX === null) return;
    const dx = px - p.prevX;
    const dy = py - p.prevY;
    const dist = Math.sqrt(dx * dx + dy * dy);
    if (dist < 0.1 || dist > 90) return;

    // Extend streak backward from current pos for more visible trail
    const extMult = 1 + p.trailMult * (1 + 5 * (1 - normR));
    const x0 = px - dx * extMult;
    const y0 = py - dy * extMult;

    const grad = ctx.createLinearGradient(x0, y0, px, py);
    grad.addColorStop(0, `rgba(255,255,255,0)`);
    grad.addColorStop(0.5, `rgba(255,255,255,${alpha * 0.28})`);
    grad.addColorStop(1, `rgba(255,255,255,${alpha * 0.72})`);

    ctx.beginPath();
    ctx.moveTo(x0, y0);
    ctx.lineTo(px, py);
    ctx.strokeStyle = grad;
    ctx.lineWidth = Math.max(0.4, size * (0.6 + 1.2 * (1 - normR)));
    ctx.lineCap = "round";
    ctx.stroke();
}


function cubicBezier(t, p0, p1, p2, p3) {
    const u = 1 - t;
    return {
        x:
            u * u * u * p0.x +
            3 * u * u * t * p1.x +
            3 * u * t * t * p2.x +
            t * t * t * p3.x,
        y:
            u * u * u * p0.y +
            3 * u * u * t * p1.y +
            3 * u * t * t * p2.y +
            t * t * t * p3.y,
    };
}

function cubicBezierTangent(t, p0, p1, p2, p3) {
    const u = 1 - t;
    const dx =
        3 * u * u * (p1.x - p0.x) +
        6 * u * t * (p2.x - p1.x) +
        3 * t * t * (p3.x - p2.x);
    const dy =
        3 * u * u * (p1.y - p0.y) +
        6 * u * t * (p2.y - p1.y) +
        3 * t * t * (p3.y - p2.y);
    const len = Math.max(0.0001, Math.sqrt(dx * dx + dy * dy));
    return { x: dx / len, y: dy / len, nx: -dy / len, ny: dx / len };
}

function flowCurve(t, laneOffset) {
    // Upper-left → lower-right parabolic stream.
    const p0 = { x: width * -0.10, y: height * 0.08 };
    const p1 = { x: width * 0.18, y: height * 0.03 };
    const p2 = { x: width * 0.42, y: height * 0.92 };
    const p3 = { x: width * 1.10, y: height * 0.86 };
    const pt = cubicBezier(t, p0, p1, p2, p3);
    const tg = cubicBezierTangent(t, p0, p1, p2, p3);
    return {
        x: pt.x + tg.nx * laneOffset,
        y: pt.y + tg.ny * laneOffset,
        tx: tg.x,
        ty: tg.y,
    };
}

// ─── Core glow effects ───────────────────────────────────────────────────
let corePhase = 0;

function drawCore(cx, cy, mR, coreAlpha = 1) {
    cctx.clearRect(0, 0, width, height);
    corePhase += 0.007;
    if (coreAlpha <= 0.01) return;
    cctx.save();
    cctx.globalAlpha = coreAlpha;

    const ehRx = mR * EH_RX;
    const ehRy = mR * EH_RY;

    // ── 1. Wide ambient accretion field ──────────────────────────────────
    const ambPulse = 0.88 + 0.12 * Math.sin(corePhase * 0.8);
    const ambRx = ehRx * 3.9;
    const ambGrad = cctx.createRadialGradient(cx, cy, ehRx * 0.95, cx, cy, ambRx);
    ambGrad.addColorStop(0, `rgba(180,195,240,${0.038 * ambPulse})`);
    ambGrad.addColorStop(0.40, `rgba(160,178,225,${0.024 * ambPulse})`);
    ambGrad.addColorStop(0.75, `rgba(120,145,200,${0.010 * ambPulse})`);
    ambGrad.addColorStop(1, "rgba(0,0,0,0)");
    cctx.save();
    cctx.scale(1, SQUISH);
    cctx.beginPath();
    cctx.ellipse(cx, cy / SQUISH, ambRx, ambRx, 0, 0, Math.PI * 2);
    cctx.fillStyle = ambGrad;
    cctx.fill();
    cctx.restore();

    // ── 2. Accretion disc — segmented lobes, no full-width column ─────
    // IMPORTANT: never rotate the disc/canvas here. A rotated context also rotates
    // the gradient and eventually creates the white beam/column artifact.
    // Instead we keep the disc horizontal and make the left/right lobes breathe.
    const discRx = ehRx * 2.72;
    const discRy = Math.max(2.0, ehRy * 0.26); // thinner and more localized
    const hotPhase = corePhase * SPIN_DIR;
    const hotBias = Math.cos(hotPhase);         // -1…+1

    // Keep a small base glow on both sides, but bias the hot side.
    // Clamp through max(0, …) to avoid a side becoming too bright/solid.
    const leftAmp = 0.24 + 0.34 * Math.max(0, -hotBias);
    const rightAmp = 0.24 + 0.34 * Math.max(0, hotBias);

    function discSideGradient(maxAlphaLeft, maxAlphaRight) {
        const g = cctx.createLinearGradient(cx - discRx, cy, cx + discRx, cy);
        g.addColorStop(0.00, "rgba(255,255,255,0)");
        g.addColorStop(0.14, `rgba(255,255,255,${0.010 * leftAmp * maxAlphaLeft})`);
        g.addColorStop(0.28, `rgba(255,255,255,${0.080 * leftAmp * maxAlphaLeft})`);
        g.addColorStop(0.36, `rgba(255,255,255,${0.024 * leftAmp * maxAlphaLeft})`);
        // Wider dead-zone around the event horizon. This keeps the center open
        // and prevents a flat overlay layer from spanning across the particles.
        g.addColorStop(0.43, "rgba(255,255,255,0)");
        g.addColorStop(0.57, "rgba(255,255,255,0)");
        g.addColorStop(0.64, `rgba(255,255,255,${0.024 * rightAmp * maxAlphaRight})`);
        g.addColorStop(0.72, `rgba(255,255,255,${0.080 * rightAmp * maxAlphaRight})`);
        g.addColorStop(0.86, `rgba(255,255,255,${0.010 * rightAmp * maxAlphaRight})`);
        g.addColorStop(1.00, "rgba(255,255,255,0)");
        return g;
    }

    // Draw two soft side lobes instead of one filled horizontal oval.
    // The lobes give the sweep impression but cannot merge into a solid beam.
    function fillDiscLobe(side, amp) {
        const lobeCx = cx + side * discRx * 0.34;
        const lobeRx = discRx * 0.28;
        const lobeRy = discRy * 1.55;
        const lg = cctx.createRadialGradient(lobeCx, cy, 0, lobeCx, cy, lobeRx);
        lg.addColorStop(0.00, `rgba(255,255,255,${0.050 * amp})`);
        lg.addColorStop(0.42, `rgba(210,225,255,${0.022 * amp})`);
        lg.addColorStop(0.80, `rgba(160,185,240,${0.008 * amp})`);
        lg.addColorStop(1.00, "rgba(0,0,0,0)");

        cctx.save();
        cctx.beginPath();
        cctx.ellipse(lobeCx, cy, lobeRx, lobeRy, 0, 0, Math.PI * 2);
        cctx.clip();
        cctx.filter = "blur(9px)";
        cctx.fillStyle = lg;
        cctx.fillRect(lobeCx - lobeRx, cy - lobeRy, lobeRx * 2, lobeRy * 2);
        cctx.restore();
    }

    fillDiscLobe(-1, leftAmp);
    fillDiscLobe(1, rightAmp);

    // Thin edge-on arcs. These are strokes, not a filled slab, so the center
    // stays open and no cylinder/white-column artifact can form.
    function strokeDiscArc(start, end, yMul, lineWidth, blurPx, alphaMul) {
        cctx.save();
        cctx.beginPath();
        cctx.ellipse(cx, cy, discRx * 0.92, discRy * yMul, 0, start, end);
        cctx.strokeStyle = discSideGradient(alphaMul, alphaMul);
        cctx.lineWidth = lineWidth;
        cctx.lineCap = "round";
        cctx.filter = `blur(${blurPx}px)`;
        cctx.stroke();
        cctx.restore();
    }

    // Canvas ellipse angles: 0→π is the lower/front half; π→2π is upper/back.
    // Shorter arcs so the ends stay rounded and do not form visible pointed noses.
    strokeDiscArc(0.14 * Math.PI, 0.86 * Math.PI, 1.00, 2.6, 2.2, 0.52);
    strokeDiscArc(1.14 * Math.PI, 1.86 * Math.PI, 0.82, 1.5, 2.8, 0.22);

    // Extra occlusion around the core removes any residual horizontal bridge.
    // This is intentionally before the photon ring, so the ring can be redrawn cleanly.
    const cutGrad = cctx.createRadialGradient(cx, cy, ehRx * 0.82, cx, cy, ehRx * 1.88);
    cutGrad.addColorStop(0.00, "rgba(0,0,0,0.96)");
    cutGrad.addColorStop(0.52, "rgba(0,0,0,0.66)");
    cutGrad.addColorStop(1.00, "rgba(0,0,0,0)");
    cctx.save();
    cctx.globalCompositeOperation = "destination-out";
    cctx.beginPath();
    cctx.ellipse(cx, cy, ehRx * 1.72, ehRy * 1.82, 0, 0, Math.PI * 2);
    cctx.fillStyle = cutGrad;
    cctx.fill();
    cctx.restore();

    // Soft side mask trims the residual horizontal wash so particles remain visible.
    function sideFade(side) {
        const fadeCx = cx + side * discRx * 0.58;
        const fadeRx = discRx * 0.42;
        const fadeRy = ehRy * 1.05;
        const fg = cctx.createRadialGradient(fadeCx, cy, 0, fadeCx, cy, fadeRx);
        fg.addColorStop(0.00, "rgba(0,0,0,0)");
        fg.addColorStop(0.55, "rgba(0,0,0,0)");
        fg.addColorStop(1.00, "rgba(0,0,0,0.42)");
        cctx.save();
        cctx.globalCompositeOperation = "destination-out";
        cctx.beginPath();
        cctx.ellipse(fadeCx, cy, fadeRx, fadeRy, 0, 0, Math.PI * 2);
        cctx.fillStyle = fg;
        cctx.fill();
        cctx.restore();
    }
    sideFade(-1);
    sideFade(1);

    // ── 3. Photon ring — thin bright halo around event horizon ───────────
    const rPulse = 0.92 + 0.08 * Math.sin(corePhase * 1.6);
    const ringRx = ehRx * 1.18 * rPulse;

    cctx.save();
    cctx.scale(1, SQUISH);
    // 3 concentric passes, innermost brightest
    const spreads = [1.48, 1.26, 1.10];
    const opas = [0.045, 0.085, 0.16];
    for (let p = 0; p < 3; p++) {
        const rg = cctx.createRadialGradient(
            cx, cy / SQUISH, ringRx * 0.82,
            cx, cy / SQUISH, ringRx * spreads[p]
        );
        rg.addColorStop(0, `rgba(230,238,255,${opas[p] * rPulse})`);
        rg.addColorStop(0.5, `rgba(255,255,255,${opas[p] * 1.5 * rPulse})`);
        rg.addColorStop(1, "rgba(0,0,0,0)");
        cctx.beginPath();
        cctx.ellipse(cx, cy / SQUISH, ringRx * spreads[p], ringRx * spreads[p], 0, 0, Math.PI * 2);
        cctx.fillStyle = rg;
        cctx.fill();
    }
    cctx.restore();

    // ── 4. Hot plasma rim — sRGB glow just outside EH ───────────────────
    const glowP = 0.75 + 0.25 * Math.sin(corePhase * 2.3);
    const gg = cctx.createRadialGradient(cx, cy, 0, cx, cy, ehRx * 1.08);
    gg.addColorStop(0, `rgba(255,255,255,${0.14 * glowP})`);
    gg.addColorStop(0.50, `rgba(210,225,255,${0.075 * glowP})`);
    gg.addColorStop(0.85, `rgba(160,185,240,${0.028 * glowP})`);
    gg.addColorStop(1, "rgba(0,0,0,0)");
    cctx.save();
    cctx.scale(1, SQUISH * 0.82);
    cctx.beginPath();
    cctx.ellipse(cx, cy / (SQUISH * 0.82), ehRx * 1.08, ehRy * 1.08, 0, 0, Math.PI * 2);
    cctx.fillStyle = gg;
    cctx.fill();
    cctx.restore();

    // ── 5. Event horizon + occlusion — drawn last to punch over disc ─────
    cctx.save();
    cctx.scale(1, SQUISH);

    // Soft dark ring (lensing shadow zone between disc halves)
    const og = cctx.createRadialGradient(cx, cy / SQUISH, ehRx * 0.88, cx, cy / SQUISH, ehRx * 1.56);
    og.addColorStop(0, "rgba(0,0,0,0)");
    og.addColorStop(0.10, "rgba(0,0,0,0.72)");
    og.addColorStop(0.42, "rgba(0,0,0,0.58)");
    og.addColorStop(0.76, "rgba(0,0,0,0.26)");
    og.addColorStop(1, "rgba(0,0,0,0)");
    cctx.beginPath();
    cctx.ellipse(cx, cy / SQUISH, ehRx * 1.56, ehRy * 1.56 / SQUISH, 0, 0, Math.PI * 2);
    cctx.fillStyle = og;
    cctx.fill();

    // Feathered shadow shell. This softens the edge so the center does not read as
    // a flat 2D ellipse when the bright disc momentarily dims.
    const sg = cctx.createRadialGradient(
        cx - ehRx * 0.10,
        cy / SQUISH - (ehRy / SQUISH) * 0.12,
        ehRx * 0.12,
        cx,
        cy / SQUISH,
        ehRx * 1.22
    );
    sg.addColorStop(0.00, "rgba(0,0,0,1)");
    sg.addColorStop(0.55, "rgba(0,0,0,0.98)");
    sg.addColorStop(0.82, "rgba(0,0,0,0.92)");
    sg.addColorStop(1.00, "rgba(0,0,0,0)");
    cctx.save();
    cctx.filter = "blur(10px)";
    cctx.beginPath();
    cctx.ellipse(cx, cy / SQUISH, ehRx * 1.16, ehRy * 1.10 / SQUISH, 0, 0, Math.PI * 2);
    cctx.fillStyle = sg;
    cctx.fill();
    cctx.restore();

    // Inner umbra. Slightly smaller than the feathered shell so the apparent form feels
    // more like a warped spherical shadow rather than a hard flat oval cutout.
    cctx.save();
    cctx.filter = "blur(1px)";
    cctx.beginPath();
    cctx.ellipse(cx, cy / SQUISH, ehRx * 0.95, ehRy * 0.93 / SQUISH, 0, 0, Math.PI * 2);
    cctx.fillStyle = "rgba(0,0,0,0.995)";
    cctx.fill();
    cctx.restore();

    // Extra lower shadow adds a little depth / lensing volume under the center.
    const lg2 = cctx.createRadialGradient(cx, cy / SQUISH + (ehRy / SQUISH) * 0.12, ehRx * 0.14, cx, cy / SQUISH, ehRx * 1.08);
    lg2.addColorStop(0.0, "rgba(0,0,0,0.24)");
    lg2.addColorStop(0.7, "rgba(0,0,0,0.10)");
    lg2.addColorStop(1.0, "rgba(0,0,0,0)");
    cctx.beginPath();
    cctx.ellipse(cx, cy / SQUISH, ehRx * 1.02, ehRy * 0.98 / SQUISH, 0, 0, Math.PI * 2);
    cctx.fillStyle = lg2;
    cctx.fill();

    cctx.restore();

    // Restore the coreAlpha wrapper.
    cctx.restore();
}


function drawBottomDust(finalFill) {
    if (finalFill <= 0.01) return;

    for (const d of bottomDust) {
        // Late reveal follows the same diagonal rule, but it is boosted by
        // scrollTarget so exact bottom scroll fully resolves the last band.
        const reveal = smoothstep(d.rank - 0.30, d.rank + 0.06, finalFill);
        if (reveal <= 0.01) continue;

        const driftX = Math.cos(corePhase * 0.42 + d.phase) * d.drift;
        const driftY = Math.sin(corePhase * 0.36 + d.phase * 1.31) * d.drift * 0.65;
        const x = clamp(d.x + driftX, 2, width - 2);
        const y = clamp(d.y + driftY, 2, height - 2);
        const a = d.alpha * reveal * (0.72 + 0.28 * Math.sin(corePhase * 1.4 + d.phase));

        ctx.fillStyle = `rgba(255,255,255,${Math.max(0, a)})`;
        if (d.shape === "square") {
            const q = Math.max(1, d.size * 1.15);
            ctx.fillRect(x - q * 0.5, y - q * 0.5, q, q);
        } else {
            ctx.beginPath();
            ctx.arc(x, y, d.size, 0, Math.PI * 2);
            ctx.fill();
        }

        // Very subtle animated tail for the bottom band.
        if (reveal > 0.35 && d.alpha > 0.18) {
            const len = 5 + 10 * reveal;
            const sx = x - len * 0.88;
            const sy = y - len * 0.34;
            const g = ctx.createLinearGradient(sx, sy, x, y);
            g.addColorStop(0, "rgba(255,255,255,0)");
            g.addColorStop(1, `rgba(255,255,255,${a * 0.32})`);
            ctx.beginPath();
            ctx.moveTo(sx, sy);
            ctx.lineTo(x, y);
            ctx.strokeStyle = g;
            ctx.lineWidth = Math.max(0.3, d.size * 0.42);
            ctx.lineCap = "round";
            ctx.stroke();
        }
    }
}


function createShader(gl, type, source) {
    const shader = gl.createShader(type);
    gl.shaderSource(shader, source);
    gl.compileShader(shader);
    if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
        console.warn("Nebula shader compile failed:", gl.getShaderInfoLog(shader));
        gl.deleteShader(shader);
        return null;
    }
    return shader;
}

function initNebula() {
    const gl = nebulaCanvas.getContext("webgl", {
        alpha: true,
        antialias: true,
        premultipliedAlpha: true,
    });
    if (!gl) return null;

    const vertexShader = `
        attribute vec2 aPosition;
        void main() {
            gl_Position = vec4(aPosition, 0.0, 1.0);
        }
    `;

    const fragmentShader = `
        precision highp float;
        uniform vec2 uResolution;
        uniform float uTime;
        uniform float uScroll;
        uniform float uPart3;
        uniform float uPart4;
        uniform vec2 uMouse;

        float random(vec2 st) {
            return fract(sin(dot(st.xy, vec2(12.9898, 78.233))) * 43758.5453123);
        }

        float noise(vec2 p) {
            vec2 i = floor(p);
            vec2 f = fract(p);
            vec2 u = f * f * (3.0 - 2.0 * f);
            return mix(
                mix(random(i), random(i + vec2(1.0, 0.0)), u.x),
                mix(random(i + vec2(0.0, 1.0)), random(i + vec2(1.0, 1.0)), u.x),
                u.y
            );
        }

        float fbm(vec2 p) {
            float v = 0.0;
            float a = 0.5;
            for (int i = 0; i < 6; i++) {
                v += a * noise(p);
                p *= 2.02;
                a *= 0.52;
            }
            return v;
        }

        float bayer4(vec2 frag) {
            vec2 p = mod(floor(frag), 4.0);
            float idx = p.x + p.y * 4.0;
            float v = 0.0;
            if (idx == 0.0) v = 0.0; else if (idx == 1.0) v = 8.0; else if (idx == 2.0) v = 2.0; else if (idx == 3.0) v = 10.0;
            else if (idx == 4.0) v = 12.0; else if (idx == 5.0) v = 4.0; else if (idx == 6.0) v = 14.0; else if (idx == 7.0) v = 6.0;
            else if (idx == 8.0) v = 3.0; else if (idx == 9.0) v = 11.0; else if (idx == 10.0) v = 1.0; else if (idx == 11.0) v = 9.0;
            else if (idx == 12.0) v = 15.0; else if (idx == 13.0) v = 7.0; else if (idx == 14.0) v = 13.0; else v = 5.0;
            return v / 16.0;
        }

        void main() {
            vec2 frag = gl_FragCoord.xy;
            vec2 uv01 = frag / uResolution.xy;
            vec2 uv = (frag - 0.5 * uResolution.xy) / uResolution.y;
            vec2 mouse = (uMouse - 0.5 * uResolution.xy) / uResolution.y;

            float reveal = smoothstep(0.0, 1.0, uScroll);
            float part3 = smoothstep(0.0, 1.0, uPart3);
            float part4 = smoothstep(0.0, 1.0, uPart4);
            if (reveal <= 0.001 && part3 <= 0.001 && part4 <= 0.001) {
                discard;
            }

            float md = length(uv - mouse);
            vec2 away = normalize(uv - mouse + vec2(0.0001));
            uv += away * smoothstep(0.34, 0.0, md) / max(35.0, md * 90.0);

            float diagWhite = 0.56 * uv01.x + 0.74 * (1.0 - uv01.y);
            float sweepWhite = smoothstep(1.02 - reveal * 1.18, 1.17 - reveal * 1.18, diagWhite);

            float angleWhite = -0.46 + reveal * 0.34 + uTime * 0.012;
            mat2 rotWhite = mat2(cos(angleWhite), -sin(angleWhite), sin(angleWhite), cos(angleWhite));
            vec2 flowWhite = rotWhite * (uv * 1.42);
            flowWhite += vec2(-uTime * 0.036, uTime * 0.022);
            flowWhite += vec2(reveal * 0.34, -reveal * 0.42);

            float w1 = fbm(flowWhite * 2.0 + vec2(uTime * 0.030, -uTime * 0.020));
            float w2 = fbm(flowWhite * 4.0 - vec2(-uTime * 0.018, uTime * 0.028));
            float whiteRidge = smoothstep(0.40, 0.74, w1) * 0.72 + smoothstep(0.52, 0.82, w2) * 0.38;
            float whiteCorner = smoothstep(0.05, 0.95, 1.18 - length((uv01 - vec2(0.92, 0.10)) * vec2(1.12, 0.88)));
            float whiteVeil = clamp((whiteRidge * 0.86 + whiteCorner * 0.42) * sweepWhite, 0.0, 1.0);

            float diagColor = 0.72 * (1.0 - uv01.x) + 0.86 * (1.0 - uv01.y);
            float sweepColor = smoothstep(1.10 - part3 * 1.34, 1.31 - part3 * 1.34, diagColor);

            float angleColor = 0.58 - part3 * 0.36 + uTime * 0.018;
            mat2 rotColor = mat2(cos(angleColor), -sin(angleColor), sin(angleColor), cos(angleColor));
            vec2 flowColor = rotColor * (uv * 1.18);
            flowColor += vec2(uTime * 0.026, -uTime * 0.034);
            flowColor += vec2(-part3 * 0.62 + part4 * 0.92, part3 * 0.44 + part4 * 0.74);

            float c1 = fbm(flowColor * 2.25 + vec2(-uTime * 0.024, uTime * 0.030));
            float c2 = fbm(flowColor * 4.60 + vec2(uTime * 0.018, -uTime * 0.026));
            float c3 = fbm(flowColor * 7.10 + vec2(-uTime * 0.012, -uTime * 0.018));
            float colorRidge = smoothstep(0.38, 0.70, c1) * 0.62
                             + smoothstep(0.48, 0.78, c2) * 0.42
                             + smoothstep(0.56, 0.86, c3) * 0.24;

            float colorCorner = smoothstep(0.08, 1.08, 1.12 - length((uv01 - vec2(0.08, 0.10)) * vec2(1.08, 0.86)));
            float colorVeil = clamp((colorRidge * 0.88 + colorCorner * 0.56) * sweepColor, 0.0, 1.0);

            // Part 4: the sun is born from the lower-left and drags the colorful
            // nebula with it. Coordinates are in WebGL bottom-left origin.
            float sunProgress = smoothstep(0.0, 1.0, part4);
            vec2 sunCenter = mix(
                vec2(-0.10, -0.08),
                vec2(0.265, 0.335),
                smoothstep(0.02, 0.92, sunProgress)
            );

            vec2 sunAspect01 = uv01 - sunCenter;
            sunAspect01.x *= uResolution.x / uResolution.y;
            float sunDist01 = length(sunAspect01);

            // Pull cloud mass around the growing sphere.
            float cloudPull = smoothstep(0.92, 0.06, sunDist01) * sunProgress;

            // Diagonal plume/wake from the lower-left sun toward the upper-right.
            vec2 plumeVec = uv01 - sunCenter;
            float plumeProj = dot(plumeVec, normalize(vec2(0.86, 0.50)));
            float plumeLine = abs(plumeVec.y - 0.58 * plumeVec.x);
            float plume = smoothstep(0.17, 0.018, plumeLine)
                         * smoothstep(-0.05, 0.18, plumeProj)
                         * (1.0 - smoothstep(0.86, 1.24, plumeProj))
                         * sunProgress;

            // A small dark occult/veil region keeps the transition mysterious instead
            // of simply becoming a flat bright orange blob.
            float occultVeil = smoothstep(0.72, 0.05, length((uv01 - (sunCenter + vec2(0.11, 0.10))) * vec2(1.20, 0.88)))
                             * smoothstep(0.16, 0.88, sunProgress);

            colorVeil = clamp(
                mix(colorVeil, colorVeil * 0.44 + cloudPull * 0.72 + plume * 0.86, sunProgress),
                0.0,
                1.0
            );

            float whiteAlpha = whiteVeil * (0.10 + 0.43 * reveal) * (1.0 - part3 * 0.88);
            whiteAlpha *= smoothstep(0.0, 0.16, uv01.y) * smoothstep(0.0, 0.10, 1.0 - uv01.x);
            whiteAlpha *= 1.0 - part4;

            vec3 smoke = mix(vec3(0.78, 0.80, 0.84), vec3(0.46, 0.52, 0.66), smoothstep(0.45, 0.82, w2));
            vec3 magenta = vec3(0.95, 0.18, 0.58);
            vec3 violet  = vec3(0.40, 0.22, 0.95);
            vec3 cyan    = vec3(0.10, 0.82, 1.00);
            vec3 amber   = vec3(1.00, 0.42, 0.12);

            vec3 colorNebula = mix(magenta, violet, smoothstep(0.30, 0.82, c1));
            colorNebula = mix(colorNebula, cyan, smoothstep(0.46, 0.86, c2) * 0.72);
            colorNebula = mix(colorNebula, amber, smoothstep(0.62, 0.94, c3) * 0.34);

            float colorAlpha = colorVeil * (0.12 + 0.58 * part3) * (1.0 - part4 * 0.18);
            colorAlpha *= smoothstep(0.0, 0.10, uv01.x) * smoothstep(0.0, 0.12, uv01.y);

            vec3 outColor = smoke * whiteAlpha + colorNebula * colorAlpha;
            float outAlpha = clamp(whiteAlpha + colorAlpha, 0.0, 0.82);

            // Part 4: dithered sun sphere, born from the lower-left and growing
            // until it occupies roughly half of the page.
            vec2 sunUv = uv01 - sunCenter;
            sunUv.x *= uResolution.x / uResolution.y;
            float r = length(sunUv);
            float radius = mix(0.045, 0.645, smoothstep(0.02, 0.98, part4));
            float sphereD = 1.0 - pow(r / max(radius, 0.001), 2.0);
            float inside = step(0.0, sphereD);

            vec3 n = normalize(vec3(sunUv / max(radius, 0.001), sqrt(max(0.0, sphereD))));
            vec3 light = normalize(vec3(-0.48 + 0.24 * sin(uTime * 0.5), 0.72, 0.72));
            float shade = clamp(0.30 + 0.82 * dot(n, light), 0.0, 1.0);
            float surface = fbm(sunUv * 14.0 + vec2(uTime * 0.060, -uTime * 0.035));
            surface += 0.52 * fbm(sunUv * 38.0 + vec2(-uTime * 0.025, uTime * 0.030));
            surface += 0.28 * fbm(sunUv * 72.0 + vec2(uTime * 0.015, uTime * 0.018));

            float dither = bayer4(floor(frag / max(1.0, 2.4 - part4 * 1.2)));
            float sphereMask = step(dither * 0.82, clamp(shade * 0.72 + surface * 0.48, 0.0, 1.0)) * inside;
            float sphereEdgeSoft = smoothstep(radius * 1.16, radius * 0.82, r);
            float limbGlow = smoothstep(radius * 1.10, radius * 0.90, r) * (1.0 - inside);

            vec3 sunCore = mix(
                vec3(1.0, 0.20, 0.00),
                vec3(1.0, 0.86, 0.18),
                clamp(surface * 0.92 + shade * 0.56, 0.0, 1.0)
            );

            // Occult crescent / smoky veil over the sphere.
            vec2 veilOffset = sunUv - vec2(radius * 0.22, radius * 0.09);
            float sphereOccult = smoothstep(radius * 0.82, radius * 0.18, length(veilOffset))
                              * inside
                              * smoothstep(0.22, 0.90, part4);
            sunCore = mix(sunCore, vec3(0.09, 0.018, 0.00), sphereOccult * 0.48);

            float sunAlpha = sphereMask * sphereEdgeSoft * smoothstep(0.04, 0.96, part4);

            float coronaBand = smoothstep(radius * 2.10, radius * 0.88, r) * (1.0 - inside);
            float plasma = fbm(vec2(atan(sunUv.y, sunUv.x) * 2.4, r * 9.0) + vec2(uTime * 0.13, -uTime * 0.04));
            float corona = coronaBand * smoothstep(0.34, 0.86, plasma) * smoothstep(0.12, 1.0, part4);
            vec3 coronaColor = mix(vec3(1.0, 0.12, 0.0), vec3(1.0, 0.74, 0.18), plasma);

            // Released energy / matter as procedural dot particles around the sun and plume.
            vec2 ejectUv = uv01 - sunCenter;
            ejectUv.x *= uResolution.x / uResolution.y;
            float ejectR = length(ejectUv);
            float ejectAngle = atan(ejectUv.y, ejectUv.x);
            float burstBand = smoothstep(radius * 0.86, radius * 1.35, ejectR)
                            * (1.0 - smoothstep(radius * 2.85, radius * 4.25, ejectR));
            float radialJets = smoothstep(0.48, 0.92, fbm(vec2(ejectAngle * 3.2, ejectR * 7.0) + vec2(uTime * 0.18, -uTime * 0.055)));
            vec2 dotGrid = (uv01 + normalize(ejectUv + vec2(0.0001)) * uTime * 0.018 * part4) * uResolution.xy / 5.5;
            vec2 cell = floor(dotGrid);
            vec2 gv = fract(dotGrid) - 0.5;
            vec2 dotOffset = vec2(random(cell + 13.7), random(cell + 41.2)) - 0.5;
            float dotSeed = random(cell + 9.3);
            float dotShape = 1.0 - smoothstep(0.025, 0.145, length(gv - dotOffset * 0.55));
            float energyDots = dotShape
                             * step(0.72, dotSeed)
                             * burstBand
                             * radialJets
                             * smoothstep(0.16, 1.0, part4);

            vec3 limbColor = mix(vec3(1.0, 0.34, 0.04), vec3(1.0, 0.78, 0.22), clamp(plasma * 0.7 + 0.25, 0.0, 1.0));
            outColor = outColor * (1.0 - sunAlpha * 0.72) + sunCore * sunAlpha;
            outColor += limbColor * limbGlow * (0.28 + 0.34 * part4);
            outColor += coronaColor * corona * 0.62;
            outColor += mix(vec3(1.0, 0.25, 0.02), vec3(1.0, 0.82, 0.32), dotSeed) * energyDots * 0.95;

            // The smoky veil also darkens the surrounding colorful nebula a little.
            outColor *= 1.0 - occultVeil * 0.20;
            outAlpha = clamp(outAlpha + sunAlpha * 0.96 + limbGlow * 0.30 + corona * 0.58 + energyDots * 0.72, 0.0, 0.995);

            gl_FragColor = vec4(outColor, outAlpha);
        }
    `;

    const vs = createShader(gl, gl.VERTEX_SHADER, vertexShader);
    const fs = createShader(gl, gl.FRAGMENT_SHADER, fragmentShader);
    if (!vs || !fs) return null;

    const program = gl.createProgram();
    gl.attachShader(program, vs);
    gl.attachShader(program, fs);
    gl.linkProgram(program);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
        console.warn("Nebula shader link failed:", gl.getProgramInfoLog(program));
        return null;
    }

    const buffer = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
    gl.bufferData(
        gl.ARRAY_BUFFER,
        new Float32Array([-1, -1, 1, -1, -1, 1, -1, 1, 1, -1, 1, 1]),
        gl.STATIC_DRAW
    );

    const aPosition = gl.getAttribLocation(program, "aPosition");
    const uniforms = {
        uResolution: gl.getUniformLocation(program, "uResolution"),
        uTime: gl.getUniformLocation(program, "uTime"),
        uScroll: gl.getUniformLocation(program, "uScroll"),
        uPart3: gl.getUniformLocation(program, "uPart3"),
        uPart4: gl.getUniformLocation(program, "uPart4"),
        uMouse: gl.getUniformLocation(program, "uMouse"),
    };

    gl.useProgram(program);
    gl.enableVertexAttribArray(aPosition);
    gl.vertexAttribPointer(aPosition, 2, gl.FLOAT, false, 0, 0);

    return {
        gl,
        program,
        buffer,
        uniforms,
        start: performance.now(),
        mouseX: -100,
        mouseY: -100,
    };
}

function resizeNebula() {
    if (!nebula) return;
    const nDpr = Math.min(window.devicePixelRatio || 1, 2);
    nebulaCanvas.width = Math.floor(width * nDpr);
    nebulaCanvas.height = Math.floor(height * nDpr);
    nebulaCanvas.style.width = width + "px";
    nebulaCanvas.style.height = height + "px";
    nebula.gl.viewport(0, 0, nebulaCanvas.width, nebulaCanvas.height);
}

function drawNebula(part2Progress, part3Progress, part4Progress) {
    if (!nebula) return;
    const gl = nebula.gl;
    gl.clearColor(0, 0, 0, 0);
    gl.clear(gl.COLOR_BUFFER_BIT);
    gl.useProgram(nebula.program);
    gl.uniform2f(nebula.uniforms.uResolution, nebulaCanvas.width, nebulaCanvas.height);
    gl.uniform1f(nebula.uniforms.uTime, (performance.now() - nebula.start) * 0.001);
    gl.uniform1f(nebula.uniforms.uScroll, part2Progress);
    gl.uniform1f(nebula.uniforms.uPart3, part3Progress);
    gl.uniform1f(nebula.uniforms.uPart4, part4Progress);
    gl.uniform2f(
        nebula.uniforms.uMouse,
        nebula.mouseX * Math.min(window.devicePixelRatio || 1, 2),
        (height - nebula.mouseY) * Math.min(window.devicePixelRatio || 1, 2)
    );
    gl.drawArrays(gl.TRIANGLES, 0, 6);
}


// ─── Main draw loop ───────────────────────────────────────────────────────
function draw() {
    tick++;
    scrollSmooth += (scrollTarget - scrollSmooth) * 0.075;

    // scrollSmooth is intentionally eased, so it approaches 1 asymptotically.
    // Use a direct bottom boost from scrollTarget for the final fill state;
    // otherwise the last diagonal band can look unfinished even at page bottom.
    const bottomBoost = smoothstep(0.94, 0.998, scrollTarget);
    const effectiveScroll = Math.max(scrollSmooth, lerp(scrollSmooth, 1, bottomBoost));

    const gravity = 1 - smoothstep(0.06, 0.38, effectiveScroll);
    const flowAmount = smoothstep(0.12, 0.90, effectiveScroll);
    const finalFill = Math.max(flowAmount, bottomBoost);
    const bhExit = smoothstep(0.05, 0.42, effectiveScroll);
    const sectionScroll = Math.max(scrollTarget, effectiveScroll);
    const part2Progress = smoothstep(0.28, 0.48, sectionScroll);
    const part3Progress = smoothstep(0.50, 0.70, sectionScroll);
    const part4Progress = smoothstep(0.72, 0.985, sectionScroll);

    // Particle canvas: semi-transparent fill creates trailing smear.
    // The trail becomes slightly shorter in flow mode so the background can fill cleanly.
    ctx.fillStyle = `rgba(3,3,3,${0.16 + 0.08 * flowAmount})`;
    ctx.fillRect(0, 0, width, height);

    const { x: cx, y: cy } = bhCenter(bhExit);
    const mR = Math.min(width, height);
    const maxRadial = mR * R_MAX_FRAC;
    const ehRx = mR * EH_RX;
    const ehRy = mR * EH_RY;

    for (let i = 0; i < particles.length; i++) {
        const p = particles[i];

        // ── Physics: gravity gradually disappears while scrolling ───────
        const pull = 1 - p.radial / maxRadial;   // 0 at edge, 1 at core
        const orbitFactor = 0.18 + 0.82 * gravity;

        p.angle += p.orbitSpd * (0.55 + 1.45 * Math.pow(pull, 1.4)) * orbitFactor;
        p.radial -= p.infallRate * (0.5 + 2.2 * Math.pow(pull, 2.0)) * gravity;
        p.tw += p.twSpd;

        const orbitX = cx + Math.cos(p.angle) * p.radial;
        const orbitY = cy + Math.sin(p.angle) * p.radial * SQUISH;

        const coreNorm = ((orbitX - cx) / ehRx) ** 2 + ((orbitY - cy) / ehRy) ** 2;
        if (gravity > 0.35 && (coreNorm < 0.52 || p.radial < ehRx * 0.36)) {
            p.prevX = null; p.prevY = null;
            particles[i] = spawnParticle(cx, cy, true, i, particles.length);
            continue;
        }

        p.normR = Math.max(0, Math.min(1, p.radial / maxRadial));
        const normR = p.normR;

        // ── Scroll flow: diagonal fill + parabolic stream ───────────────
        const diagonalReveal = smoothstep(p.fillRank - 0.28, p.fillRank + 0.08, finalFill);
        const detach = smoothstep(0.06, 0.52, effectiveScroll);
        const flowWeight = detach * (0.22 + 0.78 * diagonalReveal);

        const lanePulse = p.laneOffset + Math.sin(corePhase * 0.26 + p.phase) * mR * 0.012;

        // Move particles along the parabolic stream while the scroll-flow is active,
        // so the "asteroid tails" remain animated instead of becoming static slashes.
        const travelT = (p.flowT + corePhase * p.streamSpeed * (0.45 + 0.85 * flowAmount)) % 1;
        const curvePt = flowCurve(travelT, lanePulse);
        const settle = smoothstep(0.62, 0.98, finalFill);

        // Even after settling, keep a subtle drift so the field remains alive.
        const fieldDrift = p.fieldDriftAmp * (0.35 + 0.65 * flowAmount);
        const driftX = Math.cos(corePhase * (0.80 + p.streamSpeed * 90) + p.phase) * fieldDrift;
        const driftY = Math.sin(corePhase * (0.64 + p.streamSpeed * 70) + p.phase * 1.17) * fieldDrift * 0.85;

        // First: particles are pulled into the parabola.
        // Later: they settle into their diagonal-ranked field targets to fill the background.
        const flowX = clamp(lerp(curvePt.x, p.fieldX + driftX, settle), 2, width - 2);
        const flowY = clamp(lerp(curvePt.y, p.fieldY + driftY, settle), 2, height - 2);

        let px = lerp(orbitX, flowX, flowWeight);
        let py = lerp(orbitY, flowY, flowWeight);

        // ── Visuals ──────────────────────────────────────────────────────
        const twinkle = 0.78 + Math.sin(p.tw) * 0.22;
        const distFade = normR < 0.10
            ? normR / 0.10
            : normR > 0.80
                ? 1 - (normR - 0.80) / 0.20
                : 1;

        // Top mode: particles sink into the event horizon.
        // Flow mode: they detach from the horizon and become a background field.
        const sinkFade = gravity > 0.05
            ? Math.max(0, Math.min(1, (coreNorm - 0.68) / (2.25 - 0.68)))
            : 1;

        const orbitAlpha = p.baseAlpha * twinkle * distFade * sinkFade * (1 - flowWeight) * (0.38 + 0.62 * gravity);
        const flowAlpha = p.fieldAlpha * finalFill * (0.28 + 0.84 * diagonalReveal) * (p.fieldY > height * 0.78 ? 1.18 : 1);
        let alpha = Math.max(0, orbitAlpha + flowAlpha);

        const size = Math.max(
            0.14,
            p.r * (0.22 + 0.78 * normR) * (0.75 + 0.25 * sinkFade) * (0.85 + 0.20 * diagonalReveal)
        );

        // Part 3 transition: the particle field is pushed to the right and
        // gradually disappears behind the colorful nebula.
        const p3Push = smoothstep(0.04, 1.0, part3Progress);
        if (p3Push > 0.001) {
            px += (width * 0.52 + 120 + p.fillRank * 180) * p3Push;
            py += Math.sin(corePhase * (0.55 + p.streamSpeed * 80.0) + p.phase) * mR * 0.035 * p3Push;
            alpha *= 1 - smoothstep(0.12, 0.94, part3Progress);
        }

        const p4Push = smoothstep(0.02, 1.0, part4Progress);
        if (p4Push > 0.001) {
            px += width * 0.44 * p4Push;
            py -= height * 0.08 * p4Push;
            alpha *= 1 - smoothstep(0.02, 0.72, part4Progress);
        }

        // Spiral / flow streak uses actual previous position. The distance cap in
        // drawSpiral prevents a long teleport streak during mode transition.
        drawSpiral(p, px, py, normR, alpha * (0.55 + 0.45 * diagonalReveal), size);

        // Extra tiny streaks along the parabolic flow direction.
        if (flowAmount > 0.18 && diagonalReveal > 0.24 && p.trailMult > 1.05) {
            const len = (7 + 24 * flowAmount) * (0.45 + p.trailMult) * (0.85 + 0.15 * Math.sin(corePhase * 0.9 + p.phase));
            const sx = px - curvePt.tx * len;
            const sy = py - curvePt.ty * len;
            const fg = ctx.createLinearGradient(sx, sy, px, py);
            fg.addColorStop(0, "rgba(255,255,255,0)");
            fg.addColorStop(0.45, `rgba(255,255,255,${alpha * 0.10})`);
            fg.addColorStop(1, `rgba(255,255,255,${alpha * 0.34})`);
            ctx.beginPath();
            ctx.moveTo(sx, sy);
            ctx.lineTo(px, py);
            ctx.strokeStyle = fg;
            ctx.lineWidth = Math.max(0.35, size * 0.55);
            ctx.lineCap = "round";
            ctx.stroke();
        }

        p.prevX = px;
        p.prevY = py;

        if (alpha < 0.004) continue;

        // Dot / pixel
        ctx.fillStyle = `rgba(255,255,255,${alpha})`;
        if (p.shape === "square" && flowAmount > 0.20) {
            const q = Math.max(1, size * 1.35);
            ctx.fillRect(px - q * 0.5, py - q * 0.5, q, q);
        } else {
            ctx.beginPath();
            ctx.arc(px, py, size, 0, Math.PI * 2);
            ctx.fill();
        }

        // Halo for brighter particles
        if (size > 0.65 && alpha > 0.22 && flowAmount < 0.82) {
            ctx.beginPath();
            ctx.arc(px, py, size * 3.8, 0, Math.PI * 2);
            ctx.fillStyle = `rgba(255,255,255,${alpha * 0.045})`;
            ctx.fill();
        }

        // Diffraction spike only on far bright stars
        if (alpha > 0.50 && size > 0.95 && normR > 0.55 && flowAmount < 0.50) {
            const spk = size * 2.4;
            ctx.beginPath();
            ctx.moveTo(px - spk, py); ctx.lineTo(px + spk, py);
            ctx.moveTo(px, py - spk); ctx.lineTo(px, py + spk);
            ctx.strokeStyle = `rgba(255,255,255,${alpha * 0.13})`;
            ctx.lineWidth = 0.45;
            ctx.stroke();
        }
    }

    // Dedicated final-fill bottom band. This resolves the lower-right corner at full scroll.
    drawBottomDust(finalFill * (1 - part3Progress) * (1 - part4Progress));

    // Part 2/3/4 overlay: white nebula → colored nebula → solar sphere.
    drawNebula(part2Progress, part3Progress, part4Progress);

    // Core effects fade and drift away as the scroll-flow takes over.
    drawCore(cx, cy, mR, gravity * (1 - part2Progress) * (1 - part3Progress) * (1 - part4Progress));

    requestAnimationFrame(draw);
}

nebula = initNebula();

window.addEventListener("resize", resize);
window.addEventListener("scroll", updateScrollTarget, { passive: true });
window.addEventListener("mousemove", (e) => {
    if (!nebula) return;
    nebula.mouseX = e.clientX;
    nebula.mouseY = e.clientY;
}, { passive: true });

resize();
updateScrollTarget();
draw();
