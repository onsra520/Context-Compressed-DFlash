# Phase 2.4 Fallback-Aware Output Diagnostic Comparison Design

## Summary

Phase 2.4 defines fallback-aware rules for future output diagnostic comparison.

The core requirement is that low-tier records must be classified by contribution behavior before any future string-level diagnostic is summarized. A normalized string match between a low-tier record and a target-baseline record has different meaning depending on whether the low-tier output came from:

```text
Qwen draft contribution -> Gemma continuation
Gemma fallback after rejected Qwen draft
ambiguous or missing trace data
```

This phase is design only. It does not implement comparison logic.

## Problem Observed In Phase 2.3

Phase 2.3 showed two important facts:

```text
baseline raw prompt_mode:
  baseline_empty_after_normalization: 2/3

baseline chat prompt_mode:
  baseline_empty_after_normalization: 0/3
```

That supports using `prompt_mode = chat` for Gemma baseline traces used in output-comparison preparation.

Phase 2.3 also showed:

```text
low-tier chat prompt_mode:
  low_tier_empty_after_normalization: 0/3
  fallback_count: 3
```

This means the chat-mode low-tier trace produced non-empty output, but all three records used Gemma fallback. Any future string diagnostic over that trace would mostly describe fallback behavior, not useful Qwen draft contribution.

## Record Categories

Future output diagnostics should classify every low-tier record into one of these categories.

```text
valid_draft_continuation
  bridge_status = valid
  fallback_count = 0
  draft_valid_count > 0
  draft_rejected_count = 0
  gemma_fallback_used is false or absent

fallback_after_rejection
  bridge_status = rejected
  fallback_count > 0
  draft_rejected_count > 0
  rejection_reason is present
  gemma_fallback_used is true when available

fallback_only
  fallback_count > 0
  low-tier output was produced through Gemma fallback behavior
  may overlap with fallback_after_rejection when rejection metadata is present

unknown_contribution
  required classification fields are missing, contradictory, or ambiguous
```

`fallback_after_rejection` is the most specific rejection category. `fallback_only` is the broader interpretation category for output diagnostics: the output should be treated as fallback-derived, even if the exact rejection metadata is incomplete.

## Required Classification Fields

Minimum fields for classification:

```text
bridge_status
rejection_reason
fallback_count
draft_valid_count
draft_rejected_count
generation_settings.prompt_mode
```

Useful optional fields:

```text
gemma_fallback_used
qwen_raw_output
gemma_raw_output
capture_raw_output
raw_output_captured
prompt_id
prompt_hash
prompt_summary
```

The current live low-tier records include enough fields to classify most records by bridge and fallback behavior:

```text
bridge_status
rejection_reason
fallback_count
draft_valid_count
draft_rejected_count
generation_settings
qwen_raw_output when capture_raw_output=true
gemma_raw_output when capture_raw_output=true
```

Current live records do not always include `gemma_fallback_used`; that field exists in controlled fallback records. A future classifier should infer fallback usage from `fallback_count > 0` when `gemma_fallback_used` is absent.

## Diagnostic Comparison Policy

Future output diagnostics may report string-level fields only after:

```text
Phase 2.1 precheck passes
Phase 2.2 normalization preview is available
prompt coverage matches
generation settings match
Gemma model file matches
Gemma device status is ok
raw output fields are present
low-tier contribution category is known
```

Allowed diagnostic fields:

```text
normalized output length
empty-after-normalization flag
diagnostic exact-string flag
normalized string match preview
preview diff summary
category-level counts
category-level warnings
```

The diagnostic exact-string flag should be treated as an inspection field only. It must not be used as proof of target-equivalent generation.

## Fallback-Only Record Handling

Fallback-derived records must be summarized separately from valid-draft records.

Allowed fields for fallback-derived records:

```text
fallback_count
rejection_reason
fallback output present
normalized fallback output length
empty-after-normalization flag
diagnostic exact-string flag with warning
```

Required warning:

```text
This record used Gemma fallback. Any string match mostly reflects fallback behavior, not successful draft contribution.
```

Fallback-derived records must not be included in summaries labeled as draft-contribution diagnostics.

If a future trace has many fallback-derived records, the report should include a trace-level warning:

```text
Most low-tier outputs in this trace came from Gemma fallback. Draft-contribution diagnostics are limited for this run.
```

## Valid-Draft Record Handling

Valid-draft records are the only current record category that can support a draft-contribution diagnostic summary.

Allowed fields for valid-draft records:

```text
normalized output length
empty-after-normalization flag
diagnostic exact-string flag
normalized string match preview
preview diff summary
qwen draft output present
gemma continuation output present
```

Even for valid-draft records, a diagnostic exact-string match only shows that normalized captured strings matched under the current preview policy. It does not prove token-level target generation, correctness, or exact speculative decoding behavior.

## Unknown Record Handling

Records should be classified as `unknown_contribution` when:

```text
bridge_status is missing
fallback_count is missing or not numeric
draft_valid_count and draft_rejected_count are both missing
bridge_status conflicts with fallback_count
raw output fields required for the requested diagnostic are absent
generation_settings.prompt_mode is missing
```

Unknown records should be excluded from draft-contribution summaries and listed with missing or contradictory fields.

Required behavior:

```text
mark record as unknown_contribution
report missing_fields
report conflicting_fields when applicable
do not include in valid-draft diagnostic counts
do not include in fallback-only diagnostic counts unless fallback_count is clear
```

## Terminology Rules

Use safe terms:

```text
diagnostic exact-string flag
normalized string match preview
fallback-aware diagnostic summary
output inspection metadata
valid-draft diagnostic records
fallback-derived records
unknown contribution records
```

Avoid unsafe terms:

```text
output equality
output parity
target equivalence
lossless
correctness
accepted-token terminology
acceptance-rate terminology
speedup
```

If future reports need to state non-claims, use explicit non-claim wording:

```text
No output parity claim is made.
No target-equivalence claim is made.
No lossless-generation claim is made.
No benchmark claim is made.
```

## Proposed Future Implementation

Recommended future module:

```text
src/htfsd/metrics/output_diagnostics.py
```

Possible functions:

```text
classify_low_tier_record(record) -> contribution_category
summarize_fallback_aware_records(low_tier_records, baseline_records)
build_diagnostic_comparison_preview(...)
render_fallback_aware_diagnostic_markdown(...)
```

Possible future command:

```bash
python scripts/diagnose_output_comparison.py \
  --low-tier logs/reports/<low-tier-raw-trace>.json \
  --baseline logs/reports/<baseline-raw-trace>.json
```

Possible output fields:

```text
total_records
valid_draft_continuation_count
fallback_after_rejection_count
fallback_only_count
unknown_contribution_count
diagnostic_string_match_count
fallback_string_match_count
unknown_record_ids
missing_fields_by_record
warnings
```

The first implementation should classify low-tier records only. It should not compare strings yet.

## Non-Claims

This phase does not compare output equality.
No output parity claim is made.
No target-equivalence claim is made.
No correctness claim is made.
No lossless-generation claim is made.
No benchmark claim is made.
No draft-acceptance metric is reported.

## Recommended Next Step

The next implementation phase should be:

```text
Phase 2.5: Fallback-Aware Output Diagnostic Classifier
```

Scope for Phase 2.5:

```text
implement classify_low_tier_record(record)
implement category counts for low-tier trace files
report missing or contradictory classification fields
add tests for valid_draft_continuation, fallback_after_rejection, fallback_only, unknown_contribution
do not compare target-baseline strings yet
do not make target-equivalence claims
```

## Conclusion

passed

Fallback-aware classification is now a required design gate before future output diagnostics. Any future string-level diagnostic must be interpreted through the low-tier record category first, especially when Gemma fallback produced the output.
