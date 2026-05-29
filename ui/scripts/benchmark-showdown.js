import { initBenchmarkLowTier } from './benchmark-low-tier.js';
import { initBenchmarkFullStack } from './benchmark-full-stack.js';

export function initBenchmarkShowdown({ data, metricDefs }) {
    // initialize both benchmark sections
    initBenchmarkLowTier({ data, metricDefs });
    initBenchmarkFullStack({ data, metricDefs });
}
