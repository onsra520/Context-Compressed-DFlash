# Phase 1.7 Target Baseline Trace Scaffold

## Summary

Phase 1.7 passed. The project now has target-model-only baseline trace scaffolding for Gemma E2B. The baseline trace runs Gemma directly over the same small prompt set used by the live low-tier trace and writes compact metadata for future comparison work.

This is not a benchmark. No speedup or equivalence claim is made.

## Baseline Trace Command

Run:

```bash
python scripts/run_baseline_trace.py
```

The command uses the default config, loads only Gemma E2B, writes a compact trace JSON under `logs/reports/`, and prints a short status summary.

Latest baseline trace:

- `logs/reports/20260524T144244Z-target-baseline-trace.json`

## Baseline Trace Fields

Required baseline fields:

- `prompt_id`
- `gemma_model_file`
- `gemma_expected_device`
- `gemma_device_status`
- `gemma_n_gpu_layers`
- `latency_seconds`
- `trace_kind`

Optional baseline fields currently emitted:

- `prompt_summary`
- `prompt_hash`
- `gemma_decode_tokens_per_second`
- `gemma_output_summary`

Baseline records do not require Qwen fields, bridge fields, fallback fields, or long raw prompt/output text.

## Baseline Schema Result

The baseline trace schema passed:

```text
records: 3
mode: target-baseline
trace schema: ok
```

## Low-Tier vs Baseline Schema/Count Check

Latest live low-tier trace:

- `logs/reports/20260524T144241Z-low-tier-trace.json`

Count/schema check:

- `low_tier_records: 3`
- `baseline_records: 3`
- `prompt_id_overlap: 3`
- `missing_prompt_ids: []`
- `extra_prompt_ids: []`
- `schema_status: ok`

This check is schema/count-only. It does not compare output equality, quality, latency advantage, or speed.

## Tests

Added tests for:

- Baseline trace generation with a fake Gemma backend
- `trace_kind = target_baseline`
- Gemma model file and device metadata
- Baseline schema excluding Qwen/bridge/fallback fields
- Baseline schema missing-field failure
- Long raw text absence by default
- Baseline command smoke behavior

Full test suite passed: 76 tests.

Forbidden-claim scan passed with zero matches.

## Remaining Issues

- Baseline trace scaffolding is metadata-only and claim-free.
- No output equality comparison is implemented.
- No speedup or benchmark report is implemented.
- Exact token-level speculative acceptance remains out of scope.

## Conclusion

passed

## Next Step

Add trace comparison report v0 that summarizes low-tier and baseline trace fields descriptively, while still avoiding speedup, equivalence, or acceptance-rate claims.
