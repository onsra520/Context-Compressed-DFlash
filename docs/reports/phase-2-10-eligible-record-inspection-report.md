# Phase 2.10 Eligible-Record Inspection Report

## Summary

Phase 2.10 added a compact eligible-record inspection layer for records selected by the Phase 2.9 diagnostic selector. The new report lists only `eligible_valid_draft_record` entries and summarizes excluded records without dumping long raw outputs.

## Inspection Command

```bash
python scripts/inspect_eligible_records.py \
  --low-tier logs/reports/<low-tier-raw-capture-trace>.json \
  --baseline logs/reports/<target-baseline-raw-capture-trace>.json
```

The command writes:

```text
logs/reports/<timestamp>-eligible-record-inspection.md
logs/reports/<timestamp>-eligible-record-inspection.json
```

## Raw Mode Result

Input traces:

```text
low-tier: logs/reports/20260525T091136Z-low-tier-trace.json
baseline: logs/reports/20260525T091144Z-target-baseline-trace.json
```

Inspection result:

```text
inspection_ready: yes
eligible_record_count: 1
excluded_fallback_derived_record_count: 0
excluded_unknown_contribution_record_count: 0
excluded_empty_baseline_record_count: 2
excluded_prompt_mode_risk_record_count: 0
blocking_reasons: []
```

The raw-mode eligible record was:

```text
prompt_id: trace-003
selection_category: eligible_valid_draft_record
contribution_category: valid_draft_continuation
fallback_count: 0
draft_valid_count: 1
draft_rejected_count: 0
low_tier_normalized_length: 9
baseline_normalized_length: 355
diagnostic exact-string flag: false
```

The excluded raw-mode records were `trace-001` and `trace-002`, both with `empty_baseline` and `prompt_mode_risk` exclusion reasons.

## Chat Mode Result

Input traces:

```text
low-tier: logs/reports/20260525T091211Z-low-tier-trace.json
baseline: logs/reports/20260525T091228Z-target-baseline-trace.json
```

Inspection result:

```text
inspection_ready: yes
eligible_record_count: 0
excluded_fallback_derived_record_count: 3
excluded_unknown_contribution_record_count: 0
excluded_empty_baseline_record_count: 0
excluded_prompt_mode_risk_record_count: 0
blocking_reasons: []
```

All chat-mode records were excluded with `fallback_derived` and `prompt_mode_risk` reasons. This keeps chat fallback behavior separate from future draft-contribution diagnostics.

## Eligible Records

The inspection layer lists only records selected as `eligible_valid_draft_record`.

Current raw mode has one eligible record:

```text
trace-003
```

Current chat mode has no eligible records.

## Excluded Record Summary

Raw mode:

```text
empty_baseline: trace-001, trace-002
prompt_mode_risk: trace-001, trace-002
```

Chat mode:

```text
fallback_derived: trace-001, trace-002, trace-003
prompt_mode_risk: trace-001, trace-002, trace-003
```

## Warnings

Raw mode warnings:

```text
The baseline output is empty after normalization. This record is uninformative for target-baseline string diagnostics.
Raw prompt mode may produce empty Gemma baseline outputs for this prompt set. Consider chat mode for output-comparison preparation.
```

Chat mode warnings:

```text
This record used Gemma fallback. It is excluded from draft-contribution diagnostics.
Chat prompt mode produced fallback-derived low-tier records in this run. Matches in this mode must not be read as Qwen draft contribution.
```

## Tests

Verification passed:

```text
tests/test_eligible_record_inspection.py: 8 passed
tests/test_eligible_record_inspection.py tests/test_diagnostic_record_selection.py: 20 passed
```

Full-suite verification is recorded in the final Phase 2.10 result.

## Non-Claims

This is not an output equality report.
No output parity claim is made.
No target-equivalence claim is made.
No correctness claim is made.
No lossless-generation claim is made.
No benchmark claim is made.
No draft-acceptance metric is reported.

## Remaining Issues

Raw mode currently leaves only one eligible valid-draft record because two baseline outputs are empty after normalization.

Chat mode produces non-empty baseline outputs, but the low-tier records are fallback-derived and therefore excluded from draft-contribution inspection.

## Conclusion

Phase 2.10 passed. Eligible-record inspection now provides a narrow report for draft-contribution candidates while preserving exclusion reasons for fallback-derived, unknown, and empty-baseline records.

## Next Step

The next safe step is a design phase for a larger controlled prompt set that aims to produce more eligible valid-draft records without weakening the existing fallback-aware interpretation rules.
