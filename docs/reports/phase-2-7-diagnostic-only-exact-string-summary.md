# Phase 2.7 Diagnostic-Only Exact-String Summary

## Summary

Phase 2.7 passed.

This phase adds a diagnostic-only output comparison report that summarizes normalized exact-string diagnostic flags by low-tier contribution category. The report consumes precheck readiness, normalization preview metadata, low-tier contribution classification, and the fallback-aware Phase 2.6 summary.

## Diagnostic Command

```bash
python scripts/diagnose_output_comparison.py \
  --low-tier logs/reports/<low-tier-raw-capture-trace>.json \
  --baseline logs/reports/<target-baseline-raw-capture-trace>.json
```

The command writes markdown and JSON reports under `logs/reports/`.

## Input Traces

Raw-mode traces:

```text
low-tier: logs/reports/20260525T081800Z-low-tier-trace.json
baseline: logs/reports/20260525T081816Z-target-baseline-trace.json
diagnostic report: logs/reports/20260525T081915Z-diagnostic-output-comparison.md
```

Chat-mode traces:

```text
low-tier: logs/reports/20260525T081844Z-low-tier-trace.json
baseline: logs/reports/20260525T081858Z-target-baseline-trace.json
diagnostic report: logs/reports/20260525T081915Z-diagnostic-output-comparison-2.md
```

## Category Counts

Raw mode:

```text
total_records: 3
valid_draft_continuation_count: 3
fallback_after_rejection_count: 0
fallback_only_count: 0
unknown_contribution_count: 0
```

Chat mode:

```text
total_records: 3
valid_draft_continuation_count: 0
fallback_after_rejection_count: 3
fallback_only_count: 0
unknown_contribution_count: 0
```

## Diagnostic String Flags

Raw mode:

```text
diagnostic_exact_string_match_count: 0
diagnostic_exact_string_mismatch_count: 3
valid_draft_diagnostic_match_count: 0
valid_draft_diagnostic_mismatch_count: 3
fallback_derived_diagnostic_match_count: 0
fallback_derived_diagnostic_mismatch_count: 0
unknown_diagnostic_count: 0
```

Chat mode:

```text
diagnostic_exact_string_match_count: 3
diagnostic_exact_string_mismatch_count: 0
valid_draft_diagnostic_match_count: 0
valid_draft_diagnostic_mismatch_count: 0
fallback_derived_diagnostic_match_count: 3
fallback_derived_diagnostic_mismatch_count: 0
unknown_diagnostic_count: 0
```

## Raw Mode Result

Raw mode produced valid-draft diagnostic records in this run. The diagnostic string flags are grouped under `valid_draft_continuation`. The raw baseline still produced empty normalized outputs for some prompts, so the report includes prompt-mode and empty-output warnings.

## Chat Mode Result

Chat mode produced fallback-derived low-tier records in this run. The diagnostic string flags are grouped under `fallback_after_rejection`, and the report warns that these matches mostly reflect Gemma fallback behavior rather than successful Qwen draft contribution.

## Warnings

Raw mode warnings:

```text
Some baseline outputs are empty after normalization. Output diagnostics may be uninformative for those prompts.
Raw prompt mode may produce empty Gemma baseline outputs for this prompt set. Consider chat mode for output-comparison preparation.
```

Chat mode warnings:

```text
This trace contains fallback-derived records. String diagnostics for those records mostly reflect Gemma fallback behavior, not successful Qwen draft contribution.
Most low-tier records in this trace are fallback-derived. Draft-contribution diagnostics are limited for this run.
Fallback-derived diagnostic string matches must not be interpreted as Qwen draft success.
```

## Tests

Verification passed:

```text
tests/test_output_diagnostic_compare.py: 10 passed
tests/test_output_diagnostic_compare.py tests/test_output_diagnostic_summary.py tests/test_output_preview.py tests/test_output_diagnostics.py: 38 passed
```

Full suite verification is recorded in the final Phase 2.7 result.

## Non-Claims

This is not an output equality report.
No output parity claim is made.
No target-equivalence claim is made.
No correctness claim is made.
No lossless-generation claim is made.
No benchmark claim is made.
No draft-acceptance metric is reported.

## Remaining Issues

Raw prompt mode can still produce empty Gemma baseline outputs for this prompt set. Chat prompt mode fixes baseline output presence, but the observed low-tier chat trace remains fallback-derived.

## Conclusion

passed

Phase 2.7 adds diagnostic string inspection grouped by contribution category. The generated reports separate valid-draft diagnostic records from fallback-derived diagnostic records.

## Next Step

Phase 2.8 should design a small diagnostic report reader/index that lists recent raw/chat diagnostic reports and highlights category counts, warnings, and readiness without adding new interpretation claims.
