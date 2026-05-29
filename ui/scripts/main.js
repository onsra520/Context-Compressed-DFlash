import { data, cycles, metricDefs } from "../mocks/mock-data.js";

const cycle0 = cycles[0] ?? null;
const cycle1 = cycles[1] ?? cycle0;
const cycle2 = cycles[2] ?? cycle1 ?? cycle0;

        function metricClass(k) { k = k.toLowerCase(); if (k.includes('speedup')) return 'm-speed'; if (k.includes('accepted') || k.includes('acceptance')) return 'm-accept'; if (k.includes('rejected')) return 'm-reject'; if (k.includes('fallback')) return 'm-fallback'; if (k.includes('tokens/sec')) return 'm-tps'; if (k.includes('latency')) return 'm-lat'; return 'm-token' }
        function metricsFor(obj, kind) { const keys = kind === 'low' ? ['latency_seconds', 'decode_tokens_per_sec', 'total_tokens_per_sec', 'prompt_tokens', 'completion_tokens', 'total_tokens', 'prefill_ms', 'decode_ms', 'memory_gb', 'draft_block_size', 'cycle_count', 'accepted_draft_tokens', 'rejected_draft_tokens', 'fallback_tokens', 'acceptance_rate', 'verification_mode', 'correctness_note', 'speedup'] : ['latency_seconds', 'decode_tokens_per_sec', 'total_tokens_per_sec', 'prompt_tokens', 'completion_tokens', 'total_tokens', 'prefill_ms', 'decode_ms', 'memory_gb', 'low_tier_accepted_tokens', 'low_tier_rejected_tokens', 'low_tier_fallback_tokens', 'high_tier_accepted_tokens', 'high_tier_rejected_tokens', 'high_tier_fallback_tokens', 'low_tier_acceptance_rate', 'high_tier_acceptance_rate', 'verification_mode', 'correctness_note', 'speedup']; return keys.map(k => ({ label: k.replaceAll('_', ' '), value: obj[k], cls: metricClass(k) })) }
        function renderMetrics(id, arr) { document.getElementById(id).innerHTML = arr.map(m => `<div class="metric ${m.cls}"><span>${m.label}</span><b>${m.value}</b></div>`).join('') }
        function setStatus(id, t) { const el = document.getElementById(id); el.textContent = t; el.className = 'status ' + (t === 'RUNNING' ? 'running' : t === 'DONE' ? 'done' : '') }
        function progress(wrap, fill, dur) { return new Promise(res => { const w = document.getElementById(wrap), f = document.getElementById(fill); w.style.display = 'block'; f.style.width = '0%'; let start; function step(ts) { if (!start) start = ts; const p = Math.min((ts - start) / dur, 1); f.style.width = (p * 100) + '%'; if (p < 1) requestAnimationFrame(step); else setTimeout(() => { w.style.display = 'none'; res() }, 180) } requestAnimationFrame(step) }) }
        function markSteps(id, index) { [...document.getElementById(id).children].forEach((s, i) => { s.className = 'step ' + (i < index ? 'done' : i === index ? 'active' : '') }) }
        function resetSteps(id) { [...document.getElementById(id).children].forEach(s => s.className = 'step') }
        async function startLow() { document.getElementById('ltStart').disabled = true; document.getElementById('ltCompare').style.display = 'none'; resetSteps('ltSteps'); setStatus('ltBaseStatus', 'RUNNING'); markSteps('ltSteps', 0); await progress('ltBaseProg', 'ltBaseFill', 1300); document.getElementById('ltBaseResp').textContent = data.low.baseline.response; renderMetrics('ltBaseMetrics', metricsFor(data.low.baseline, 'low')); setStatus('ltBaseStatus', 'DONE'); markSteps('ltSteps', 1); await new Promise(r => setTimeout(r, 500)); setStatus('ltArchStatus', 'RUNNING'); markSteps('ltSteps', 2); await progress('ltArchProg', 'ltArchFill', 1500); document.getElementById('ltArchResp').textContent = data.low.arch.response; renderMetrics('ltArchMetrics', metricsFor(data.low.arch, 'low')); setStatus('ltArchStatus', 'DONE'); markSteps('ltSteps', 3); await new Promise(r => setTimeout(r, 500)); markSteps('ltSteps', 4); const b = data.low.baseline, a = data.low.arch; document.getElementById('ltCompareBody').innerHTML = `D-Flash Low-tier reached <b>${a.speedup}</b> speedup over the E2B baseline. Latency changed from <b>${b.latency_seconds}s</b> to <b>${a.latency_seconds}s</b>, while decode throughput increased from <b>${b.decode_tokens_per_sec}</b> to <b>${a.decode_tokens_per_sec}</b> tok/s. Accepted draft tokens: <b>${a.accepted_draft_tokens}</b>, rejected: <b>${a.rejected_draft_tokens}</b>, fallback: <b>${a.fallback_tokens}</b>.`; document.getElementById('ltCompare').style.display = 'block'; markSteps('ltSteps', 5); document.getElementById('ltStart').disabled = false }
        function resetLow() { resetSteps('ltSteps');['ltBaseMetrics', 'ltArchMetrics'].forEach(id => document.getElementById(id).innerHTML = ''); document.getElementById('ltBaseResp').textContent = 'Waiting for baseline run...'; document.getElementById('ltArchResp').textContent = 'Waiting for D-Flash run...'; setStatus('ltBaseStatus', 'IDLE'); setStatus('ltArchStatus', 'IDLE'); document.getElementById('ltCompare').style.display = 'none' }
        async function startFull() { document.getElementById('fullStart').disabled = true; document.getElementById('fullCompare').style.display = 'none'; resetSteps('fullSteps'); setStatus('fullBaseStatus', 'RUNNING'); markSteps('fullSteps', 0); await progress('fullBaseProg', 'fullBaseFill', 1600); document.getElementById('fullBaseResp').textContent = data.full.baseline.response; renderMetrics('fullBaseMetrics', metricsFor(data.full.baseline, 'full')); setStatus('fullBaseStatus', 'DONE'); markSteps('fullSteps', 1); await new Promise(r => setTimeout(r, 500)); setStatus('fullArchStatus', 'RUNNING'); markSteps('fullSteps', 2); await progress('fullArchProg', 'fullArchFill', 1800); document.getElementById('fullArchResp').textContent = data.full.arch.response; renderMetrics('fullArchMetrics', metricsFor(data.full.arch, 'full')); setStatus('fullArchStatus', 'DONE'); markSteps('fullSteps', 3); await new Promise(r => setTimeout(r, 500)); markSteps('fullSteps', 4); const b = data.full.baseline, a = data.full.arch; document.getElementById('fullCompareBody').innerHTML = `Full HTFSD reached <b>${a.speedup}</b> end-to-end speedup over the E4B baseline. Latency changed from <b>${b.latency_seconds}s</b> to <b>${a.latency_seconds}s</b>, while decode throughput increased from <b>${b.decode_tokens_per_sec}</b> to <b>${a.decode_tokens_per_sec}</b> tok/s. Low-tier acceptance: <b>${a.low_tier_acceptance_rate}</b>; high-tier acceptance: <b>${a.high_tier_acceptance_rate}</b>.`; document.getElementById('fullCompare').style.display = 'block'; markSteps('fullSteps', 5); document.getElementById('fullStart').disabled = false }
        function resetFull() { resetSteps('fullSteps');['fullBaseMetrics', 'fullArchMetrics'].forEach(id => document.getElementById(id).innerHTML = ''); document.getElementById('fullBaseResp').textContent = 'Waiting for E4B baseline run...'; document.getElementById('fullArchResp').textContent = 'Waiting for Full HTFSD run...'; setStatus('fullBaseStatus', 'IDLE'); setStatus('fullArchStatus', 'IDLE'); document.getElementById('fullCompare').style.display = 'none' }
        document.getElementById('ltStart').addEventListener('click', startLow); document.getElementById('ltReset').addEventListener('click', resetLow); document.getElementById('fullStart').addEventListener('click', startFull); document.getElementById('fullReset').addEventListener('click', resetFull); document.getElementById('metricDefs').innerHTML = metricDefs.map((d, i) => { const metricColors = ["var(--yellow)", "var(--cyan)", "var(--green)", "var(--paper)", "var(--silver)", "#fff", "var(--orange)", "var(--hot)", "var(--purple)", "var(--cyan)", "var(--yellow)", "var(--green)", "var(--red)", "var(--orange)", "var(--purple)", "var(--hot)", "var(--silver)", "#fff"]; const whiteText = [6, 7, 8, 12, 13, 14, 15].includes(i); return `<div class="def-card" style="background:${metricColors[i % metricColors.length]};${whiteText ? 'color:white;' : ''}"><h3>${d[0]}</h3><p>${d[1]}</p></div>` }).join('');

/* ===== arc.html native graph simulator ===== */

        const steps = [
            { title: 'Prompt enters system', desc: 'Prompt bắt đầu đi vào architecture graph.', node: 'nPrompt', edge: null, packet: 'prompt', pos: [155, 223], cycle: 'Start', type: 'normal', payload: ['Explain', 'caching', '...'], result: [] },
            { title: 'Enter Low-tier D-Flash', desc: 'Hệ thống đi vào low-tier: Qwen draft + Gemma E2B verify + context loop.', node: 'nQwen', edge: 'ePromptQwen', packet: 'context', pos: [340, 233], cycle: 'Cycle 1 / 3', cluster: 'clusterLow', type: 'normal', data: cycle0, phase: 'draft' },
            { title: 'Cycle 1 — Qwen drafts block', desc: 'Qwen sinh block 8 token. Đây chỉ là nháp, chưa phải output chính thức.', node: 'nQwen', edge: null, packet: 'draft x8', pos: [615, 233], cycle: 'Cycle 1 / 3', cluster: 'clusterLow', type: 'normal', data: cycle0, phase: 'draft' },
            { title: 'Cycle 1 — Gemma E2B verifies', desc: 'Gemma accept prefix đúng, deny token “so”, fallback đúng 1 token “to”.', node: 'nVerify', edge: 'eQwenVerify', packet: 'verify', pos: [960, 233], cycle: 'Cycle 1 / 3', cluster: 'clusterLow', type: 'warn', data: cycle0, phase: 'verify' },
            { title: 'Cycle 1 — Update context', desc: 'Context được cộng accepted prefix + fallback. Unused suffix không dùng lại.', node: 'nBuffer', edge: 'eVerifyBuffer', packet: 'context+', pos: [1315, 233], cycle: 'Cycle 1 / 3', cluster: 'clusterLow', type: 'ok', data: cycle0, phase: 'buffer' },
            { title: 'Loop to next cycle', desc: 'Context mới quay lại Qwen để sinh draft block mới.', node: 'nQwen', edge: 'eBufferQwen', packet: 'loop', pos: [615, 350], cycle: 'Cycle 2 / 3', cluster: 'clusterLow', type: 'normal', data: cycle1, phase: 'draft' },
            { title: 'Cycle 2 — Full block accepted', desc: 'Gemma E2B accept toàn bộ 8 token, không cần fallback.', node: 'nVerify', edge: 'eQwenVerify', packet: 'accept all', pos: [960, 233], cycle: 'Cycle 2 / 3', cluster: 'clusterLow', type: 'ok', data: cycle1, phase: 'verify' },
            { title: 'Cycle 2 — Context grows', desc: 'Accepted context dài hơn và tiếp tục loop.', node: 'nBuffer', edge: 'eVerifyBuffer', packet: 'context+', pos: [1315, 233], cycle: 'Cycle 2 / 3', cluster: 'clusterLow', type: 'ok', data: cycle1, phase: 'buffer' },
            { title: 'Cycle 3 — New draft', desc: 'Qwen draft tiếp từ context mới.', node: 'nQwen', edge: 'eBufferQwen', packet: 'loop', pos: [615, 350], cycle: 'Cycle 3 / 3', cluster: 'clusterLow', type: 'normal', data: cycle2, phase: 'draft' },
            { title: 'Cycle 3 — First mismatch', desc: 'Gemma accept “It avoids repeated”, deny “work”, fallback “computation”.', node: 'nVerify', edge: 'eQwenVerify', packet: 'verify', pos: [960, 233], cycle: 'Cycle 3 / 3', cluster: 'clusterLow', type: 'warn', data: cycle2, phase: 'verify' },
            { title: 'Low-tier context committed', desc: 'Low-tier đã có accepted context ổn định để đưa sang feature bridge.', node: 'nBuffer', edge: 'eVerifyBuffer', packet: 'context+', pos: [1315, 233], cycle: 'Low-tier done', cluster: 'clusterLow', type: 'ok', data: cycle2, phase: 'buffer' },
            { title: 'Extract hidden states', desc: 'Gemma E2B chuyển accepted tokens thành hidden states / feature vectors h1, h2, h3...', node: 'nHidden', edge: 'eLowHigh', packet: 'h states', pos: [1315, 645], cycle: 'Bridge', cluster: null, type: 'future', phase: 'hidden' },
            { title: 'EAGLE-2 speculates', desc: 'EAGLE-2 dùng feature path để dự đoán path tiếp theo: by, reusing, results...', node: 'nEagle', edge: 'eHiddenEagle', packet: 'pred_h', pos: [960, 645], cycle: 'Future', cluster: 'clusterHigh', type: 'future', phase: 'eagle' },
            { title: 'Gemma E4B verifies', desc: 'Gemma E4B kiểm token candidates và giữ quyền quyết định cuối cùng.', node: 'nE4B', edge: 'eEagleE4B', packet: 'verify G4', pos: [615, 645], cycle: 'Future', cluster: 'clusterHigh', type: 'future', phase: 'e4b' },
            { title: 'Final output', desc: 'Output cuối được commit sau đường low-tier + high-tier speculation.', node: 'nFinal', edge: 'eE4BFinal', packet: 'final', pos: [175, 645], cycle: 'Done', cluster: null, type: 'ok', phase: 'final' }
        ];

        let idx = -1;
        let timer = null;
        let animLock = false;
        const el = id => document.getElementById(id);
        const graphEl = el('graph');
        const graphScene = el('graphScene');
        const graphViewport = el('graphViewport');
        const BASE_GRAPH_W = 1560;
        const BASE_GRAPH_H = 830;
        let zoom = 1;
        const MIN_ZOOM = 0.45;
        const MAX_ZOOM = 1.8;
        let panState = null;
        function clamp(v, min, max) { return Math.max(min, Math.min(max, v)); }
        function updateZoomLabel() { el('zoomLevel').textContent = Math.round(zoom * 100) + '%'; }
        function applyZoom(center = false) {
            const scaledW = BASE_GRAPH_W * zoom;
            const scaledH = BASE_GRAPH_H * zoom;
            const vw = graphViewport ? graphViewport.clientWidth : BASE_GRAPH_W;
            const vh = graphViewport ? graphViewport.clientHeight : BASE_GRAPH_H;
            const surfaceW = Math.max(vw, scaledW);
            const surfaceH = Math.max(vh, scaledH);
            graphEl.style.width = surfaceW + 'px';
            graphEl.style.height = surfaceH + 'px';
            const tx = scaledW < surfaceW ? (surfaceW - scaledW) / 2 : 0;
            const ty = scaledH < surfaceH ? (surfaceH - scaledH) / 2 : 0;
            graphScene.style.transform = `translate(${tx}px, ${ty}px) scale(${zoom})`;
            updateZoomLabel();
            if (center && graphViewport) {
                graphViewport.scrollLeft = Math.max(0, (surfaceW - vw) / 2);
                graphViewport.scrollTop = Math.max(0, (surfaceH - vh) / 2);
            }
        }
        function setZoom(next, center = false) {
            const nextZoom = clamp(next, MIN_ZOOM, MAX_ZOOM);
            if (nextZoom === zoom) return;
            zoom = nextZoom;
            applyZoom(center);
        }
        function zoomIn() { setZoom(zoom + 0.08); }
        function zoomOut() { setZoom(zoom - 0.08); }
        function zoomReset() { setZoom(1, true); }
        function zoomFit() {
            if (!graphViewport) return;
            const fitW = (graphViewport.clientWidth - 8) / BASE_GRAPH_W;
            const fitH = ((graphViewport.clientHeight || BASE_GRAPH_H) - 8) / BASE_GRAPH_H;
            const fit = Math.min(fitW, fitH, 1);
            setZoom(Math.max(MIN_ZOOM, fit), true);
        }

        function isInteractiveElement(target) {
            return !!target?.closest('button, a, input, textarea, select, label, [role="button"]');
        }

        function initGraphPan() {
            if (!graphViewport) return;
            graphViewport.style.cursor = 'grab';
            graphViewport.style.touchAction = 'none';
            graphViewport.style.userSelect = 'none';
            graphEl.style.transition = 'width 160ms ease, height 160ms ease';
            graphScene.style.transition = 'transform 160ms ease';

            const startPan = (e, pointerId) => {
                if (panState || e.button !== 0 || isInteractiveElement(e.target)) return;
                e.preventDefault();
                panState = {
                    pointerId: pointerId ?? null,
                    startX: e.clientX,
                    startY: e.clientY,
                    startLeft: graphViewport.scrollLeft,
                    startTop: graphViewport.scrollTop,
                };
                graphViewport.style.cursor = 'grabbing';
                if (pointerId != null) {
                    graphViewport.setPointerCapture?.(pointerId);
                }
            };

            const movePan = (e, pointerId) => {
                if (!panState || (pointerId != null && panState.pointerId != null && pointerId !== panState.pointerId)) return;
                e.preventDefault();
                if (!panState.pointerId && pointerId != null) {
                    panState.pointerId = pointerId;
                }
                const dx = e.clientX - panState.startX;
                const dy = e.clientY - panState.startY;
                graphViewport.scrollLeft = panState.startLeft - dx;
                graphViewport.scrollTop = panState.startTop - dy;
            };

            const stopPan = (e, pointerId) => {
                if (!panState) return;
                if (pointerId != null && panState.pointerId != null && pointerId !== panState.pointerId) return;
                panState = null;
                graphViewport.style.cursor = 'grab';
            };

            graphViewport.addEventListener('pointerdown', (e) => startPan(e, e.pointerId));
            graphViewport.addEventListener('pointermove', (e) => movePan(e, e.pointerId));
            graphViewport.addEventListener('pointerup', (e) => stopPan(e, e.pointerId));
            graphViewport.addEventListener('pointercancel', (e) => stopPan(e, e.pointerId));
            graphViewport.addEventListener('lostpointercapture', (e) => stopPan(e, e.pointerId));
            document.addEventListener('mousedown', (e) => startPan(e, null));
            document.addEventListener('mousemove', (e) => movePan(e, null));
            document.addEventListener('mouseup', (e) => stopPan(e, null));
        }

        function tok(text, cls = '') { return `<span class="tok ${cls}">${escapeHtml(text)}</span>`; }
        function escapeHtml(s) { return String(s).replace(/[&<>]/g, m => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[m])); }


        function getPacketCoords(step) {
            const margin = 26;
            if (step.edge) {
                const path = document.getElementById(step.edge);
                if (path && path.getTotalLength) {
                    const len = path.getTotalLength();
                    const mid = path.getPointAtLength(len * 0.5);
                    const p1 = path.getPointAtLength(Math.max(0, len * 0.46));
                    const p2 = path.getPointAtLength(Math.min(len, len * 0.54));
                    const dx = p2.x - p1.x;
                    const dy = p2.y - p1.y;
                    let x = mid.x, y = mid.y;
                    if (Math.abs(dx) >= Math.abs(dy)) {
                        y -= margin;
                    } else {
                        x += dx >= 0 ? margin : -margin;
                    }
                    if (step.edge === 'eBufferQwen') {
                        y -= 10;
                    }
                    if (step.edge === 'eLowHigh') {
                        x += 34;
                    }
                    return { x, y };
                }
            }
            if (step.node) {
                const node = document.getElementById(step.node);
                if (node) {
                    const x = node.offsetLeft + node.offsetWidth / 2;
                    const y = node.offsetTop - 20;
                    return { x, y };
                }
            }
            return { x: step.pos[0], y: step.pos[1] };
        }

        function movePacket(step) {
            const packet = el('packet');
            packet.classList.remove('show');
            const apply = () => {
                const pos = getPacketCoords(step);
                packet.textContent = step.packet || 'payload';
                packet.style.left = pos.x + 'px';
                packet.style.top = pos.y + 'px';
                requestAnimationFrame(() => packet.classList.add('show'));
            };
            if (!packet.classList.contains('show')) { apply(); }
            else { setTimeout(apply, 80); }
        }

        function resetClasses() {
            document.querySelectorAll('.node,.edge,.cluster').forEach(x => x.classList.remove('active', 'done'));
        }
        function markDone(until) {
            const seen = new Set();
            for (let i = 0; i < until; i++) if (steps[i].node) seen.add(steps[i].node);
            seen.forEach(id => el(id)?.classList.add('done'));
        }
        function renderData(step) {
            let context = 'Explain caching in one sentence.';
            let payload = [tok('—')];
            let result = [tok('—')];
            if (step.data) {
                const c = step.data;
                context = step.phase === 'draft' ? c.contextIn : c.contextOut;
                if (step.phase === 'draft') {
                    payload = c.draft.map(t => tok(t));
                    result = [tok('draft block x8')];
                } else if (step.phase === 'verify') {
                    payload = c.draft.map((t, i) => {
                        if (i < c.accepted.length) return tok(t, 'accept');
                        if (c.denied && t === c.denied && i === c.accepted.length) return tok(t, 'deny');
                        return tok(t, 'unused');
                    });
                    result = [
                        ...c.accepted.map(t => tok('✓ ' + t, 'accept')),
                        c.denied ? tok('✗ ' + c.denied, 'deny') : tok('✓ full block', 'accept'),
                        c.fallback ? tok('↩ ' + c.fallback, 'fallback') : tok('no fallback')
                    ];
                } else if (step.phase === 'buffer') {
                    context = c.contextOut;
                    payload = c.accepted.map(t => tok(t, 'accept'));
                    if (c.fallback) payload.push(tok(c.fallback, 'fallback'));
                    result = [tok('context updated', 'accept')];
                }
            } else if (step.phase === 'hidden') {
                context = cycle2.contextOut;
                payload = ['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'h7', '...'].map(x => tok(x, 'feature'));
                result = [tok('feature path ready', 'feature')];
            } else if (step.phase === 'eagle') {
                context = cycle2.contextOut;
                payload = ['pred_h18', 'pred_h19', 'pred_h20', 'pred_h21'].map(x => tok(x, 'pred'));
                result = ['by', 'reusing', 'results', '.'].map(x => tok(x, 'fallback'));
            } else if (step.phase === 'e4b') {
                context = cycle2.contextOut;
                payload = ['by', 'reusing', 'results', '.'].map(x => tok(x, 'fallback'));
                result = ['by ✅', 'reusing ✅', 'results ✅', '. ✅'].map(x => tok(x, 'e4b'));
            } else if (step.phase === 'final') {
                context = 'Caching stores data temporarily to speed up future requests and reduce latency. It avoids repeated computation by reusing results.';
                payload = [tok('final committed output', 'accept')];
                result = [tok('Gemma E4B final authority', 'e4b')];
            } else if (step.payload) {
                payload = step.payload.map(x => tok(x));
            }
            el('contextBox').textContent = context;
            el('payloadBox').innerHTML = payload.join('');
            el('resultBox').innerHTML = result.join('');
        }
        function lineClass(step) { return step.type === 'ok' ? 'ok' : step.type === 'warn' ? 'warn' : step.type === 'future' ? 'futureLog' : ''; }
        function rebuildLog() {
            const box = el('logBox');
            if (idx < 0) { box.innerHTML = '<div>System initialized.</div>'; return; }
            box.innerHTML = '';
            for (let i = 0; i <= idx; i++) {
                const step = steps[i];
                const line = document.createElement('div');
                line.className = lineClass(step);
                line.textContent = `${step.cycle}: ${step.title}`;
                box.appendChild(line);
            }
            box.scrollTop = box.scrollHeight;
        }
        function render() {
            resetClasses();
            if (idx < 0) {
                el('stepTitle').textContent = 'Ready'; el('stepDesc').textContent = 'Bấm Run hoặc Next Step để bắt đầu mô phỏng architecture graph.';
                el('cycleChip').textContent = 'Idle'; el('bar').style.width = '0%'; el('cycleLabel').textContent = 'Cycle: idle';
                el('packet').classList.remove('show'); renderData({ payload: ['—'] }); el('prevBtn').disabled = true; el('nextBtn').disabled = false; rebuildLog(); return;
            }
            const step = steps[idx];
            markDone(idx);
            if (step.node) el(step.node)?.classList.add('active');
            if (step.edge) el(step.edge)?.classList.add('active');
            if (step.cluster) el(step.cluster)?.classList.add('active');
            if (step.node === 'nHidden') el('clusterLow').classList.add('done');
            if (['nEagle', 'nE4B'].includes(step.node)) el('clusterHigh').classList.add('active');
            el('stepTitle').textContent = step.title;
            el('stepDesc').textContent = step.desc;
            el('cycleChip').textContent = step.cycle;
            el('cycleLabel').textContent = `Cycle: ${step.cycle}`;
            el('bar').style.width = `${Math.round(((idx + 1) / steps.length) * 100)}%`;
            movePacket(step);
            renderData(step);
            rebuildLog();
            el('nextBtn').disabled = idx >= steps.length - 1;
            el('prevBtn').disabled = idx <= -1;
        }
        function navigateTo(nextIdx) {
            if (animLock) return;
            animLock = true;
            idx = Math.max(-1, Math.min(steps.length - 1, nextIdx));
            render();
            setTimeout(() => { animLock = false; }, 170);
        }
        function next() { if (idx < steps.length - 1) { navigateTo(idx + 1); } else stopAuto(); }
        function prev() { stopAuto(); if (idx > -1) { navigateTo(idx - 1); } }
        function run() { reset(); startAuto(980); }
        function startAuto(ms = 1150) { stopAuto(false); el('autoBtn').classList.add('active'); el('autoBtn').textContent = 'Pause'; timer = setInterval(() => { if (idx >= steps.length - 1) { stopAuto(); } else next(); }, ms); }
        function stopAuto(update = true) { if (timer) clearInterval(timer); timer = null; if (update) { el('autoBtn').classList.remove('active'); el('autoBtn').textContent = 'Auto Play'; } }
        function reset() { stopAuto(); animLock = false; idx = -1; el('nextBtn').disabled = false; el('prevBtn').disabled = true; render(); }

        el('runBtn').addEventListener('click', run);
        el('zoomInBtn').addEventListener('click', zoomIn);
        el('zoomOutBtn').addEventListener('click', zoomOut);
        el('zoomResetBtn').addEventListener('click', zoomReset);
        el('zoomFitBtn').addEventListener('click', zoomFit);
        graphViewport.addEventListener('wheel', (e) => { if (e.ctrlKey || e.metaKey) { e.preventDefault(); setZoom(zoom + (e.deltaY < 0 ? 0.08 : -0.08)); } }, { passive: false });
        el('prevBtn').addEventListener('click', prev);
        el('nextBtn').addEventListener('click', next);
        el('autoBtn').addEventListener('click', () => timer ? stopAuto() : startAuto());
        el('resetBtn').addEventListener('click', reset);
        document.addEventListener('keydown', (e) => {
            if (e.key === 'ArrowRight') { e.preventDefault(); next(); }
            if (e.key === 'ArrowLeft') { e.preventDefault(); prev(); }
        });
        initGraphPan();
        render();
        requestAnimationFrame(() => setTimeout(zoomFit, 40));

