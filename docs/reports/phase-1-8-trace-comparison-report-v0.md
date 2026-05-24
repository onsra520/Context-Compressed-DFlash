# Phase 1.8 Trace Comparison Report v0

## Summary

Phase 1.8 passed. The project now has a descriptive trace comparison utility that reads one live low-tier trace and one target-baseline trace, validates both schemas, and writes a neutral markdown comparison report.

This is not a benchmark. No performance-improvement claim is made. No output-equivalence claim is made. No draft-acceptance metric is reported.

## Comparison Command

Run:

```bash
python scripts/compare_trace_report.py \
  --low-tier logs/reports/<low-tier-trace>.json \
  --baseline logs/reports/<target-baseline-trace>.json
```

Generated comparison report:

- `logs/reports/20260524T145129Z-trace-comparison-v0.md`

## Input Traces

- Low-tier trace: `logs/reports/20260524T145127Z-low-tier-trace.json`
- Target-baseline trace: `logs/reports/20260524T145128Z-target-baseline-trace.json`

## Schema Status

- `low_tier_schema_status: ok`
- `baseline_schema_status: ok`

## Record Counts

- `low_tier_records: 3`
- `baseline_records: 3`

## Prompt Coverage

- `prompt_id_overlap: 3`
- `missing_prompt_ids: []`
- `extra_prompt_ids: []`

Prompt IDs are compared by normalized numeric suffix, because live traces use `trace-001` and baseline traces use `baseline-001`.

## Runtime Policy Metadata

- `qwen_device_statuses: ['ok']`
- `low_tier_gemma_device_statuses: ['ok']`
- `baseline_gemma_device_statuses: ['ok']`
- `gemma_model_file_match: True`

## Low-Tier Bridge Accounting

- `low_tier_total_fallback_count: 0`
- `low_tier_total_draft_valid_count: 3`
- `low_tier_total_draft_rejected_count: 0`

## Descriptive Latency Summary

Low-tier latency field summary:

```text
count: 3
min: 1.201445163009339
max: 3.066748479002854
mean: 1.8317025116703007
```

Target-baseline latency field summary:

```text
count: 3
min: 0.018854990004911087
max: 0.8500463039963506
mean: 0.48460008100179647
```

These are descriptive latency fields only.

## Non-Claims

This is not a benchmark.

No performance-improvement claim is made.

No output-equivalence claim is made.

No draft-acceptance metric is reported.

## Tests

Added tests for:

- Matching prompt coverage
- Record counts
- Missing and extra prompt IDs
- Low-tier bridge accounting
- Descriptive latency summaries
- Schema validation before comparison
- Markdown report non-claims
- CLI markdown report writing

Full test suite passed: 81 tests.

Forbidden-claim scan passed with zero matches.

## Remaining Issues

- Comparison v0 does not compare output equality.
- Comparison v0 does not report quality or correctness.
- Comparison v0 does not compute or claim performance improvement.
- Exact token-level speculative acceptance remains out of scope.

## Conclusion

passed

## Next Step

Move to low-tier baseline comparison design, defining which descriptive fields are safe to compare and what evidence would eventually be required before any benchmark or equivalence claim.
