# Phase 2.5 Fallback-Aware Output Diagnostic Classifier

## Summary

Phase 2.5 adds a fallback-aware classifier for low-tier trace records.

The classifier categorizes low-tier records by contribution behavior before any future output diagnostic comparison. It does not compare target-baseline output strings.

## Classifier Command

Command added:

```bash
python scripts/classify_low_tier_trace.py logs/reports/<low-tier-trace>.json
```

The command writes a compact markdown report:

```text
logs/reports/<timestamp>-low-tier-classification.md
```

If multiple reports are written in the same second, a numeric suffix is added to avoid overwriting earlier reports.

## Classification Rules

Implemented categories:

```text
valid_draft_continuation
fallback_after_rejection
fallback_only
unknown_contribution
```

`valid_draft_continuation` requires:

```text
bridge_status = valid
fallback_count = 0
draft_valid_count > 0
draft_rejected_count = 0
gemma_fallback_used is false or absent
```

`fallback_after_rejection` requires:

```text
bridge_status = rejected
fallback_count > 0
draft_rejected_count > 0
rejection_reason is present
```

`fallback_only` is used when:

```text
fallback_count > 0
```

but rejection metadata is incomplete.

`unknown_contribution` is used when required fields are missing, contradictory, or ambiguous.

## Live Raw Trace Result

Input trace:

```text
logs/reports/20260525T031842Z-low-tier-trace.json
```

Classifier report:

```text
logs/reports/20260525T032021Z-low-tier-classification.md
```

Result:

```text
total_records: 3
valid_draft_continuation_count: 3
fallback_after_rejection_count: 0
fallback_only_count: 0
unknown_contribution_count: 0
```

Interpretation: raw low-tier trace records were classified as valid-draft continuation records.

## Live Chat Trace Result

Input trace:

```text
logs/reports/20260525T031905Z-low-tier-trace.json
```

Classifier report:

```text
logs/reports/20260525T032021Z-low-tier-classification-2.md
```

Result:

```text
total_records: 3
valid_draft_continuation_count: 0
fallback_after_rejection_count: 3
fallback_only_count: 0
unknown_contribution_count: 0
```

Interpretation: chat low-tier trace records were classified as fallback-derived records after rejected drafts. These records should not be interpreted as useful Qwen draft contribution.

## Controlled Fallback Trace Result

Input trace:

```text
logs/reports/20260525T031916Z-low-tier-trace.json
```

Classifier report:

```text
logs/reports/20260525T032021Z-low-tier-classification-3.md
```

Result:

```text
total_records: 4
valid_draft_continuation_count: 1
fallback_after_rejection_count: 3
fallback_only_count: 0
unknown_contribution_count: 0
```

Interpretation: controlled fallback classification matches the expected controlled cases.

## Category Counts

Summary of verification traces:

```text
live raw:
  valid_draft_continuation: 3
  fallback_after_rejection: 0
  fallback_only: 0
  unknown_contribution: 0

live chat:
  valid_draft_continuation: 0
  fallback_after_rejection: 3
  fallback_only: 0
  unknown_contribution: 0

controlled fallback:
  valid_draft_continuation: 1
  fallback_after_rejection: 3
  fallback_only: 0
  unknown_contribution: 0
```

## Missing or Conflicting Fields

The verifier traces had no unknown records and no missing or conflicting classification fields.

Tests cover:

```text
missing required fields -> unknown_contribution
contradictory fields -> unknown_contribution
incomplete rejection metadata with fallback_count > 0 -> fallback_only
```

## Tests

Focused verification:

```text
.venv/bin/pytest tests/test_output_diagnostics.py tests/test_low_tier_trace.py -v
23 passed
```

Full verification is expected to include:

```text
.venv/bin/pytest -v
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

The classifier intentionally does not inspect target-baseline strings. A future diagnostic phase may use these categories to decide how to summarize string-level inspection fields, but fallback-derived records must remain separate from valid-draft records.

## Conclusion

passed

The project can now classify low-tier contribution behavior before future output diagnostics.

## Next Step

Phase 2.6 should add a fallback-aware diagnostic summary scaffold that consumes classifier output and preview metadata, while still avoiding target-equivalence or correctness claims.
