export function initBenchmarkLowTier({ data, metricDefs }) {
    function metricClass(k) {
        k = k.toLowerCase();
        if (k.includes('speedup')) return 'm-speed';
        if (k.includes('accepted') || k.includes('acceptance')) return 'm-accept';
        if (k.includes('rejected')) return 'm-reject';
        if (k.includes('fallback')) return 'm-fallback';
        if (k.includes('tokens/sec')) return 'm-tps';
        if (k.includes('latency')) return 'm-lat';
        return 'm-token';
    }

    function metricsFor(obj) {
        const keys = ['latency_seconds', 'decode_tokens_per_sec', 'total_tokens_per_sec', 'prompt_tokens', 'completion_tokens', 'total_tokens', 'prefill_ms', 'decode_ms', 'memory_gb', 'draft_block_size', 'cycle_count', 'accepted_draft_tokens', 'rejected_draft_tokens', 'fallback_tokens', 'acceptance_rate', 'verification_mode', 'correctness_note', 'speedup'];
        return keys.map((k) => ({
            label: k.replaceAll('_', ' '),
            value: obj[k],
            cls: metricClass(k),
        }));
    }

    function renderMetrics(id, arr) {
        document.getElementById(id).innerHTML = arr.map((m) => `<div class="metric ${m.cls}"><span>${m.label}</span><b>${m.value}</b></div>`).join('');
    }

    function setStatus(id, text) {
        const el = document.getElementById(id);
        el.textContent = text;
        el.className = `status ${text === 'RUNNING' ? 'running' : text === 'DONE' ? 'done' : ''}`;
    }

    function progress(wrap, fill, dur) {
        return new Promise((resolve) => {
            const w = document.getElementById(wrap);
            const f = document.getElementById(fill);
            w.style.display = 'block';
            f.style.width = '0%';
            let start;

            function step(ts) {
                if (!start) start = ts;
                const p = Math.min((ts - start) / dur, 1);
                f.style.width = `${p * 100}%`;
                if (p < 1) {
                    requestAnimationFrame(step);
                    return;
                }
                setTimeout(() => {
                    w.style.display = 'none';
                    resolve();
                }, 180);
            }

            requestAnimationFrame(step);
        });
    }

    function markSteps(id, index) {
        [...document.getElementById(id).children].forEach((s, i) => {
            s.className = `step ${i < index ? 'done' : i === index ? 'active' : ''}`;
        });
    }

    function resetSteps(id) {
        [...document.getElementById(id).children].forEach((s) => {
            s.className = 'step';
        });
    }

    async function startLow() {
        document.getElementById('ltStart').disabled = true;
        document.getElementById('ltCompare').style.display = 'none';
        resetSteps('ltSteps');
        setStatus('ltBaseStatus', 'RUNNING');
        markSteps('ltSteps', 0);
        await progress('ltBaseProg', 'ltBaseFill', 1300);
        document.getElementById('ltBaseResp').textContent = data.low.baseline.response;
        renderMetrics('ltBaseMetrics', metricsFor(data.low.baseline));
        setStatus('ltBaseStatus', 'DONE');
        markSteps('ltSteps', 1);
        await new Promise((r) => setTimeout(r, 500));
        setStatus('ltArchStatus', 'RUNNING');
        markSteps('ltSteps', 2);
        await progress('ltArchProg', 'ltArchFill', 1500);
        document.getElementById('ltArchResp').textContent = data.low.arch.response;
        renderMetrics('ltArchMetrics', metricsFor(data.low.arch));
        setStatus('ltArchStatus', 'DONE');
        markSteps('ltSteps', 3);
        await new Promise((r) => setTimeout(r, 500));
        markSteps('ltSteps', 4);
        const b = data.low.baseline;
        const a = data.low.arch;
        document.getElementById('ltCompareBody').innerHTML = `D-Flash Low-tier reached <b>${a.speedup}</b> speedup over the E2B baseline. Latency changed from <b>${b.latency_seconds}s</b> to <b>${a.latency_seconds}s</b>, while decode throughput increased from <b>${b.decode_tokens_per_sec}</b> to <b>${a.decode_tokens_per_sec}</b> tok/s. Accepted draft tokens: <b>${a.accepted_draft_tokens}</b>, rejected: <b>${a.rejected_draft_tokens}</b>, fallback: <b>${a.fallback_tokens}</b>.`;
        document.getElementById('ltCompare').style.display = 'block';
        markSteps('ltSteps', 5);
        document.getElementById('ltStart').disabled = false;
    }

    function resetLow() {
        resetSteps('ltSteps');
        ['ltBaseMetrics', 'ltArchMetrics'].forEach((id) => {
            document.getElementById(id).innerHTML = '';
        });
        document.getElementById('ltBaseResp').textContent = 'Waiting for baseline run...';
        document.getElementById('ltArchResp').textContent = 'Waiting for D-Flash run...';
        setStatus('ltBaseStatus', 'IDLE');
        setStatus('ltArchStatus', 'IDLE');
        document.getElementById('ltCompare').style.display = 'none';
    }

    document.getElementById('ltStart').addEventListener('click', startLow);
    document.getElementById('ltReset').addEventListener('click', resetLow);
}
/* Placeholder: low-tier benchmark logic is currently kept in scripts/main.js for parity-first restore. */
