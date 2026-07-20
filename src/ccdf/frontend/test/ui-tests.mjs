import assert from 'assert';
import { readFileSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = resolve(__dirname, '..');

function runUITests() {
    console.log('Running frontend UI tests...');

    const script = readFileSync(resolve(root, 'scripts/benchmark-showdown.js'), 'utf8');
    const html = readFileSync(resolve(root, 'index.html'), 'utf8');

    // --- Must NOT contain mock computation ---
    assert(!script.includes('computeSimulation'), 'FAIL: Mock computeSimulation still present');
    assert(!script.includes('inputTokens * 0.12'), 'FAIL: Deterministic mock math still present');
    assert(!script.includes('Math.random()'), 'FAIL: Random values still present');

    // --- Must use real API ---
    assert(script.includes('/api/compare'), 'FAIL: Missing /api/compare API call');
    assert(script.includes('EventSource'), 'FAIL: Missing EventSource SSE client');
    assert(script.includes('/api/capabilities'), 'FAIL: Missing capabilities probe');

    // --- SSE event data must be parsed as JSON ---
    assert(script.includes("JSON.parse(e.data)"), 'FAIL: condition.started data not parsed as JSON');

    // --- Correct metric labels ---
    assert(script.includes('Warm end-to-end'), 'FAIL: Missing "Warm end-to-end" label');
    assert(!script.includes("'END-TO-END'"), 'FAIL: Old "END-TO-END" label still present');

    // --- decode_total_ms used for generation latency ---
    assert(script.includes('decode_total_ms'), 'FAIL: decode_total_ms not used for generation latency');

    // --- Effective prefill uses input_tokens_final ---
    assert(script.includes('input_tokens_final'), 'FAIL: input_tokens_final not referenced');

    // --- Null guards (format value or show dash) ---
    assert(script.includes("'—'"), 'FAIL: Missing em-dash fallback for null metrics');

    // --- CPU/CUDA dropdown present ---
    assert(html.includes('compressionDevice'), 'FAIL: compressionDevice dropdown missing from HTML');
    assert(html.includes('option value="cuda"'), 'FAIL: CUDA option missing from dropdown');
    assert(html.includes('option value="cpu"'), 'FAIL: CPU option missing from dropdown');

    // --- Failure display ---
    assert(script.includes('showConditionError') || script.includes('job.failed'), 'FAIL: No failure display handler');

    // --- Reset handler ---
    assert(script.includes('resetComparison'), 'FAIL: Missing resetComparison function');
    assert(script.includes("'compareReset'"), 'FAIL: compareReset button not wired');

    console.log('Frontend UI tests PASSED');
}

runUITests();
