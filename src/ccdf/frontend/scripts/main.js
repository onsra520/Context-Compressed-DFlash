import { initArchitectureGraph } from './architecture-graph.js';
import { initBenchmarkShowdown } from './benchmark-showdown.js';
import { initMetricsExplained } from './metrics-explained.js';
import { initEvidenceCharts } from './evidence-charts.js';
import '../styles/evidence.css';

function initNavigation() {
    const links = [...document.querySelectorAll('.nav a[href^="#"]')];
    const sections = links
        .map((link) => document.querySelector(link.getAttribute('href')))
        .filter(Boolean);

    const observer = new IntersectionObserver((entries) => {
        const visible = entries
            .filter((entry) => entry.isIntersecting)
            .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
        if (!visible) return;
        links.forEach((link) => {
            link.classList.toggle('active', link.getAttribute('href') === `#${visible.target.id}`);
        });
    }, { rootMargin: '-25% 0px -60% 0px', threshold: [0.05, 0.2, 0.5] });

    sections.forEach((section) => observer.observe(section));
}

initArchitectureGraph();
initBenchmarkShowdown();
initMetricsExplained();
initEvidenceCharts();
initNavigation();

