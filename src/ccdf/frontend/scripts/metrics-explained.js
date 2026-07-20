import { metricDefs } from '../mocks/mock-data.js';

export function initMetricsExplained() {
    const colorClasses = [
        'def-yellow', 'def-cyan', 'def-hot', 'def-orange',
        'def-purple', 'def-blue', 'def-green', 'def-cyan',
        'def-hot', 'def-yellow', 'def-purple', 'def-orange'
    ];

    document.getElementById('metricDefs').innerHTML = metricDefs.map(([title, description], index) => `
        <article class="def-card ${colorClasses[index % colorClasses.length]}">
            <span class="metric-index">${String(index + 1).padStart(2, '0')}</span>
            <h3>${title}</h3>
            <p>${description}</p>
        </article>
    `).join('');
}
