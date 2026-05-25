# Phase 2.6 Fallback-Aware Diagnostic Summary Scaffold

## Summary

Phase 2.6 passed.

This phase adds a fallback-aware diagnostic summary scaffold that combines output-comparison precheck metadata, conservative output preview metadata, and low-tier contribution classification. The summary groups diagnostic exact-string flags by contribution category before reporting them.

## Summary Command

```bash
python scripts/summarize_output_diagnostics.py \
  --low-tier logs/reports/<low-tier-raw-capture-trace>.json \
  --baseline logs/reports/<target-baseline-raw-capture-trace>.json
```

The command writes both markdown and JSON reports under `logs/reports/`.

## Input Traces

Raw-mode traces used for verification:

```text
low-tier: logs/reports/20260525T055709Z-low-tier-trace.json
baseline: logs/reports/20260525T055715Z-target-baseline-trace.json
summary: logs/reports/20260525T060445Z-fallback-aware-output-diagnostic-summary.md
```

Chat-mode traces used for verification:

```text
low-tier: logs/reports/20260525T055733Z-low-tier-trace.json
baseline: logs/reports/20260525T055740Z-target-baseline-trace.json
summary: logs/reports/20260525T060445Z-fallback-aware-output-diagnostic-summary-2.md
```

## Contribution Category Counts

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

## Category-Level Diagnostic Fields

Raw mode grouped all diagnostic exact-string flags under `valid_draft_continuation` records:

```text
record_count: 3
empty_low_tier_count: 0
empty_baseline_count: 2
diagnostic_exact_string_match_count: 0
diagnostic_exact_string_mismatch_count: 3
```

Chat mode grouped all diagnostic exact-string flags under `fallback_after_rejection` records:

```text
record_count: 3
empty_low_tier_count: 0
empty_baseline_count: 0
diagnostic_exact_string_match_count: 3
diagnostic_exact_string_mismatch_count: 0
```

The chat-mode exact-string flags are fallback-derived diagnostics and should not be interpreted as successful Qwen draft contribution.

## Warnings

Raw mode emitted these warnings:

```text
Some baseline outputs are empty after normalization. Output diagnostics may be uninformative for those prompts.
Raw prompt mode may produce empty Gemma baseline outputs for this prompt set. Consider chat mode for output-comparison preparation.
```

Chat mode emitted these warnings:

```text
This trace contains fallback-derived records. String diagnostics for those records mostly reflect Gemma fallback behavior, not successful Qwen draft contribution.
Most low-tier records in this trace are fallback-derived. Draft-contribution diagnostics are limited for this run.
```

## Raw Mode Result

Raw mode is useful for observing valid low-tier draft continuation records in this run, but the baseline still produced empty normalized outputs for 2 of 3 prompts.

## Chat Mode Result

Chat mode produced non-empty baseline outputs for all prompts, but the low-tier trace was fallback-derived for all 3 records. The diagnostic summary now makes that contribution category explicit before presenting string-level preview counts.

## Tests

Verification passed:

```text
.venv/bin/pytest -v
134 passed
```

## Non-Claims

This is not an output equality report.
No output parity claim is made.
No target-equivalence claim is made.
No correctness claim is made.
No lossless-generation claim is made.
No benchmark claim is made.
No draft-acceptance metric is reported.

## Remaining Issues

The raw baseline can still produce empty normalized outputs for this prompt set. Chat mode fixes baseline output presence, but the current low-tier chat path is fallback-derived for all records in the observed run.

## Conclusion

passed

Phase 2.6 adds the intended diagnostic summary scaffold and keeps diagnostic exact-string fields separated by contribution category.

## Next Step

Phase 2.7 should design a diagnostic-only exact-string comparison report that consumes the Phase 2.6 category summaries, treats fallback-derived records separately, and continues to avoid output parity or target-equivalence claims.
