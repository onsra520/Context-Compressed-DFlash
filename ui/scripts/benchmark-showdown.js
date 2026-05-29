import { initBenchmarkLowTier } from './benchmark-low-tier.js';
import { initBenchmarkFullStack } from './benchmark-full-stack.js';

export function initBenchmarkShowdown({ data, metricDefs }) {
    // render metric definition cards
    document.getElementById('metricDefs').innerHTML = metricDefs.map((d, i) => {
        const metricColors = [
            'var(--yellow)',
            'var(--cyan)',
            'var(--green)',
            'var(--paper)',
            'var(--silver)',
            '#fff',
            'var(--orange)',
            'var(--hot)',
            'var(--purple)',
            'var(--cyan)',
            'var(--yellow)',
            'var(--green)',
            'var(--red)',
            'var(--orange)',
            'var(--purple)',
            'var(--hot)',
            'var(--silver)',
            '#fff',
        ];
        const whiteText = [6, 7, 8, 12, 13, 14, 15].includes(i);
        return `<div class="def-card" style="background:${metricColors[i % metricColors.length]};${whiteText ? 'color:white;' : ''}"><h3>${d[0]}</h3><p>${d[1]}</p></div>`;
    }).join('');

    // initialize both benchmark sections
    initBenchmarkLowTier({ data, metricDefs });
    initBenchmarkFullStack({ data, metricDefs });
}
