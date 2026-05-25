# Phase 2.8 Controlled Record Selection Design

## Summary

Phase 2.8 defines controlled record-selection rules for future deeper diagnostic inspection.

Phase 2.7 introduced diagnostic exact-string flags grouped by contribution category. Phase 2.8 keeps that interpretation boundary and adds a design for deciding which records are eligible for future draft-contribution diagnostics.

This phase is design only. It does not implement a selector and does not add new comparison logic.

## Problem From Phase 2.7

Phase 2.7 showed two different trace shapes:

```text
raw mode:
  total_records: 3
  valid_draft_continuation_count: 3
  diagnostic_exact_string_match_count: 0

chat mode:
  total_records: 3
  fallback_after_rejection_count: 3
  diagnostic_exact_string_match_count: 3
```

The raw-mode trace exercised the Qwen draft contribution path, but its diagnostic exact-string flags did not match the target-baseline strings. The chat-mode trace matched diagnostically, but every low-tier record was fallback-derived. Those chat-mode matches mostly describe Gemma fallback behavior and must not be interpreted as successful Qwen draft contribution.

Future deeper inspection needs a selection layer before it summarizes any draft-contribution diagnostics.

## Selection Categories

The selector should assign each joined low-tier/preview record to one primary selection category.

```text
eligible_valid_draft_record
  record is a valid-draft continuation
  baseline normalized output is present
  required diagnostic fields are present
  no prompt-mode risk blocks interpretation

excluded_fallback_derived_record
  record is fallback_after_rejection or fallback_only
  output was produced through Gemma fallback behavior
  record must not enter draft-contribution diagnostic summaries

excluded_unknown_contribution_record
  record category is unknown_contribution
  contribution fields are missing, contradictory, or ambiguous
  record must not enter draft-contribution diagnostic summaries

excluded_empty_baseline_record
  baseline normalized output is empty
  record is uninformative for target-baseline string diagnostics

excluded_prompt_mode_risk_record
  prompt mode makes the diagnostic unreliable for the intended read
  example: raw Gemma baseline output is empty for the prompt set
  example: chat low-tier output matches but is fallback-derived
```

If multiple exclusions apply, the selector should preserve all exclusion reasons while still assigning a primary category. A safe priority is:

```text
unknown contribution
fallback-derived
empty baseline
prompt-mode risk
eligible valid draft
```

## Eligibility Rules

A record can be selected as `eligible_valid_draft_record` only when all of these conditions hold:

```text
contribution_category = valid_draft_continuation
bridge_status = valid
fallback_count = 0
draft_valid_count > 0
draft_rejected_count = 0
baseline_empty_after_normalization = false
low_tier_empty_after_normalization = false
normalized_outputs_exact_string_match is present
generation_settings are present
prompt_id is present
```

Eligible records are allowed to appear in future draft-contribution diagnostic summaries. The allowed fields remain diagnostic:

```text
normalized output length
empty-after-normalization flags
diagnostic exact-string flag
preview snippets
prompt id
prompt hash or prompt summary
```

Even when a valid-draft record is eligible, the diagnostic exact-string flag remains inspection metadata only.

## Exclusion Rules

Fallback-derived records must be excluded from draft-contribution summaries:

```text
contribution_category = fallback_after_rejection
contribution_category = fallback_only
fallback_count > 0
gemma_fallback_used = true
```

Unknown records must be excluded:

```text
contribution_category = unknown_contribution
missing classification fields
conflicting classification fields
missing generation_settings.prompt_mode
```

Records with empty baseline normalized output must be excluded or marked uninformative:

```text
baseline_empty_after_normalization = true
baseline_normalized_length = 0
baseline output field missing when raw capture is required
```

Prompt-mode risk must be recorded when prompt formatting affects interpretability:

```text
prompt_mode = raw and baseline_empty_after_normalization = true
prompt_mode = chat and contribution_category is fallback-derived
generation settings mismatch between low-tier and baseline traces
```

## Required Fields

The selector should consume records produced by the existing precheck, preview, classifier, and fallback-aware diagnostic summary layers.

Required low-tier classification fields:

```text
prompt_id
bridge_status
rejection_reason
fallback_count
draft_valid_count
draft_rejected_count
generation_settings.prompt_mode
contribution_category
```

Required preview fields:

```text
prompt_id
low_tier_output_present
baseline_output_present
low_tier_normalized_length
baseline_normalized_length
low_tier_empty_after_normalization
baseline_empty_after_normalization
normalized_outputs_exact_string_match
```

Required trace/precheck fields:

```text
capture_raw_output
generation_settings_match
prompt_coverage_status
runtime_metadata_match
gemma_model_file_match
blocking_reasons
```

Useful optional fields:

```text
prompt_summary
prompt_hash
gemma_fallback_used
qwen_raw_output
gemma_raw_output
baseline_raw_output
warnings
```

Raw text fields should remain optional and absent by default outside raw-capture traces.

## Warning Policy

The selector should emit record-level and trace-level warnings.

For fallback-derived records:

```text
This record used Gemma fallback. It is excluded from draft-contribution diagnostics.
```

For fallback-derived diagnostic matches:

```text
Diagnostic string matches in fallback-derived records mostly reflect Gemma fallback behavior, not successful Qwen draft contribution.
```

For unknown records:

```text
This record has unknown contribution category due to missing or contradictory fields.
```

For empty baseline outputs:

```text
The baseline output is empty after normalization. This record is uninformative for target-baseline string diagnostics.
```

For raw prompt-mode risk:

```text
Raw prompt mode may produce empty Gemma baseline outputs for this prompt set. Consider chat mode for output-comparison preparation.
```

For chat fallback-heavy traces:

```text
Chat prompt mode produced fallback-derived low-tier records in this run. Matches in this mode must not be read as Qwen draft contribution.
```

## Proposed Future Implementation

Phase 2.9 should implement a small selector module without adding new string comparison logic.

Possible module:

```text
src/htfsd/metrics/diagnostic_record_selection.py
```

Possible functions:

```text
select_diagnostic_record(record) -> DiagnosticRecordSelection
summarize_diagnostic_record_selection(records) -> DiagnosticRecordSelectionSummary
select_diagnostic_records_from_traces(low_tier_path, baseline_path) -> DiagnosticRecordSelectionSummary
```

Possible dataclasses:

```text
DiagnosticRecordSelection:
  prompt_id
  selection_category
  contribution_category
  eligible_for_draft_contribution_diagnostic
  exclusion_reasons
  warnings

DiagnosticRecordSelectionSummary:
  total_records
  eligible_valid_draft_record_count
  excluded_fallback_derived_record_count
  excluded_unknown_contribution_record_count
  excluded_empty_baseline_record_count
  excluded_prompt_mode_risk_record_count
  eligible_prompt_ids
  excluded_prompt_ids_by_reason
  warnings
```

Possible command:

```bash
python scripts/select_diagnostic_records.py \
  --low-tier logs/reports/<low-tier-raw-capture-trace>.json \
  --baseline logs/reports/<target-baseline-raw-capture-trace>.json
```

The command should write a compact markdown report under `logs/reports/` and optionally a JSON summary. It should not compare output strings beyond consuming the existing diagnostic preview fields.

## Non-Claims

This is not output equality validation.
No output parity claim is made.
No target-equivalence claim is made.
No correctness claim is made.
No lossless-generation claim is made.
No benchmark claim is made.
No draft-acceptance metric is reported.

## Recommended Next Step

Phase 2.9 should implement the controlled diagnostic record selector.

The implementation should:

```text
reuse Phase 2.1 precheck
reuse Phase 2.2 preview metadata
reuse Phase 2.5 contribution classification
reuse Phase 2.7 diagnostic output comparison records
emit selection categories and exclusion reasons
write markdown and optional JSON reports
add tests for eligibility and exclusion behavior
```

It should not add a new equivalence layer, benchmark layer, or speculative decoding acceptance layer.

## Conclusion

passed

Phase 2.8 defines the record-selection policy needed before deeper diagnostic inspection. Only valid-draft records with present baseline outputs and complete metadata should be eligible for future draft-contribution diagnostics. Fallback-derived, unknown, empty-baseline, and prompt-mode-risk records should be excluded or clearly marked with warnings.
