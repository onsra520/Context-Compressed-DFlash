export function initBenchmarkFullStack({ data, metricDefs }) {
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
        const keys = ['latency_seconds', 'decode_tokens_per_sec', 'total_tokens_per_sec', 'prompt_tokens', 'completion_tokens', 'total_tokens', 'prefill_ms', 'decode_ms', 'memory_gb', 'low_tier_accepted_tokens', 'low_tier_rejected_tokens', 'low_tier_fallback_tokens', 'high_tier_accepted_tokens', 'high_tier_rejected_tokens', 'high_tier_fallback_tokens', 'low_tier_acceptance_rate', 'high_tier_acceptance_rate', 'verification_mode', 'correctness_note', 'speedup'];
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

    async function startFull() {
        document.getElementById('fullStart').disabled = true;
        document.getElementById('fullCompare').style.display = 'none';
        resetSteps('fullSteps');
        setStatus('fullBaseStatus', 'RUNNING');
        markSteps('fullSteps', 0);
        await progress('fullBaseProg', 'fullBaseFill', 1600);
        document.getElementById('fullBaseResp').textContent = data.full.baseline.response;
        renderMetrics('fullBaseMetrics', metricsFor(data.full.baseline));
        setStatus('fullBaseStatus', 'DONE');
        markSteps('fullSteps', 1);
        await new Promise((r) => setTimeout(r, 500));
        setStatus('fullArchStatus', 'RUNNING');
        markSteps('fullSteps', 2);
        await progress('fullArchProg', 'fullArchFill', 1800);
        document.getElementById('fullArchResp').textContent = data.full.arch.response;
        renderMetrics('fullArchMetrics', metricsFor(data.full.arch));
        setStatus('fullArchStatus', 'DONE');
        markSteps('fullSteps', 3);
        await new Promise((r) => setTimeout(r, 500));
        markSteps('fullSteps', 4);
        const b = data.full.baseline;
        const a = data.full.arch;
        document.getElementById('fullCompareBody').innerHTML = `Full HTFSD reached <b>${a.speedup}</b> end-to-end speedup over the E4B baseline. Latency changed from <b>${b.latency_seconds}s</b> to <b>${a.latency_seconds}s</b>, while decode throughput increased from <b>${b.decode_tokens_per_sec}</b> to <b>${a.decode_tokens_per_sec}</b> tok/s. Low-tier acceptance: <b>${a.low_tier_acceptance_rate}</b>; high-tier acceptance: <b>${a.high_tier_acceptance_rate}</b>.`;
        document.getElementById('fullCompare').style.display = 'block';
        markSteps('fullSteps', 5);
        document.getElementById('fullStart').disabled = false;
    }

    function resetFull() {
        resetSteps('fullSteps');
        ['fullBaseMetrics', 'fullArchMetrics'].forEach((id) => {
            document.getElementById(id).innerHTML = '';
        });
        document.getElementById('fullBaseResp').textContent = 'Waiting for E4B baseline run...';
        document.getElementById('fullArchResp').textContent = 'Waiting for Full HTFSD run...';
        setStatus('fullBaseStatus', 'IDLE');
        setStatus('fullArchStatus', 'IDLE');
        document.getElementById('fullCompare').style.display = 'none';
    }

    document.getElementById('fullStart').addEventListener('click', startFull);
    document.getElementById('fullReset').addEventListener('click', resetFull);
}
/* Placeholder: full-stack benchmark logic is currently kept in scripts/main.js for parity-first restore. */
