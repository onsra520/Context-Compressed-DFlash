import { liveMetricDefinitions } from '../data/live-metrics.js';

export function initMetricsExplained() {
    const colorClasses = [
        'def-yellow', 'def-cyan', 'def-hot', 'def-orange',
        'def-purple', 'def-blue', 'def-green', 'def-cyan',
        'def-hot', 'def-yellow', 'def-purple', 'def-orange'
    ];

    document.getElementById('metricDefs').innerHTML = liveMetricDefinitions.map((metric, index) => `
        <article class="def-card ${colorClasses[index % colorClasses.length]}" data-fields="${metric.fields.join(',')}">
            <span class="metric-index">${String(index + 1).padStart(2, '0')}</span>
            <h3>${metric.title}</h3>
            <p>${metric.description}</p>
        </article>
    `).join('');
}
