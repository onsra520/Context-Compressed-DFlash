# Phase 2.12 Controlled Prompt Set Registry and Eligibility Evaluation

## Summary

Phase 2.12 added named prompt-set selection for low-tier and target-baseline trace commands, then evaluated the new controlled eligibility prompt set through the existing diagnostic stack.

The new prompt set produced 16 low-tier raw-mode records. All 16 classified as `valid_draft_continuation`. The selector marked 6 records as `eligible_valid_draft_record` and excluded 10 records because the target-baseline normalized output was empty.

## Prompt Set Registry

The prompt-set registry now contains:

- `phase-1-controlled-trace-v1`
- `phase-2-controlled-eligibility-v1`

The default three-prompt trace set remains available and unchanged.

## CLI Changes

Both trace commands now accept `--prompt-set`:

```bash
python scripts/run_low_tier_trace.py --prompt-set phase-2-controlled-eligibility-v1
python scripts/run_baseline_trace.py --prompt-set phase-2-controlled-eligibility-v1
```

The argument works with `--capture-raw-output` and `--prompt-mode raw`.

Trace metadata records:

- `prompt_set_id`
- `prompt_count`
- per-record `prompt_id`

## Input Prompt Set

- prompt_set_id: `phase-2-controlled-eligibility-v1`
- total_prompts: 16
- prompt_ids: `elig-001` through `elig-016`

The prompt set uses short, controlled prompts intended to increase the number of records that can pass the existing diagnostic selector.

## Raw-Mode Trace Result

Input traces:

- low-tier: `logs/reports/20260525T093751Z-low-tier-trace.json`
- target-baseline: `logs/reports/20260525T093846Z-target-baseline-trace.json`

Low-tier classification:

- total_records: 16
- valid_draft_continuation_count: 16
- fallback_after_rejection_count: 0
- fallback_only_count: 0
- unknown_contribution_count: 0

Output preview health:

- low_tier_empty_after_normalization_count: 0
- baseline_empty_after_normalization_count: 10
- all_low_tier_outputs_present: true
- all_baseline_outputs_present: true
- prompt_mode_risk: `baseline_empty_outputs`

## Selector Result

Selector report:

- markdown: `logs/reports/20260525T093900Z-diagnostic-record-selection.md`
- json: `logs/reports/20260525T093900Z-diagnostic-record-selection.json`

Selection counts:

- total_records: 16
- eligible_valid_draft_record_count: 6
- excluded_empty_baseline_record_count: 10
- excluded_fallback_derived_record_count: 0
- excluded_unknown_contribution_record_count: 0
- excluded_prompt_mode_risk_record_count: 0

Eligible prompt IDs:

- `elig-004`
- `elig-008`
- `elig-009`
- `elig-010`
- `elig-013`
- `elig-016`

Excluded empty-baseline prompt IDs:

- `elig-001`
- `elig-002`
- `elig-003`
- `elig-005`
- `elig-006`
- `elig-007`
- `elig-011`
- `elig-012`
- `elig-014`
- `elig-015`

## Eligible Inspection Result

Eligible inspection report:

- markdown: `logs/reports/20260525T093900Z-eligible-record-inspection.md`
- json: `logs/reports/20260525T093900Z-eligible-record-inspection.json`

Inspection result:

- inspection_ready: yes
- eligible_record_count: 6
- excluded_empty_baseline_record_count: 10
- excluded_fallback_derived_record_count: 0
- excluded_unknown_contribution_record_count: 0
- excluded_prompt_mode_risk_record_count: 0
- blocking_reasons: []

## Comparison Against Previous Three-Prompt Set

Previous three-prompt raw-mode diagnostic selection from Phase 2.10:

- eligible_record_count: 1
- excluded_empty_baseline_record_count: 2

Phase 2.12 raw-mode diagnostic selection:

- eligible_record_count: 6
- excluded_empty_baseline_record_count: 10

This comparison is diagnostic only. It indicates that the larger controlled prompt set produced more eligible valid-draft records in this run, while raw-mode target-baseline empty outputs remain a limiting factor.

## Warnings

Selector and inspection warnings:

- Raw prompt mode may produce empty Gemma baseline outputs for this prompt set. Consider chat mode for output-comparison preparation.
- The baseline output is empty after normalization. This record is uninformative for target-baseline string diagnostics.

## Tests

Verification commands run:

```bash
python scripts/check_env.py
python scripts/run_low_tier_trace.py --capture-raw-output --prompt-mode raw --prompt-set phase-2-controlled-eligibility-v1
python scripts/run_baseline_trace.py --capture-raw-output --prompt-mode raw --prompt-set phase-2-controlled-eligibility-v1
python scripts/select_diagnostic_records.py --low-tier logs/reports/20260525T093751Z-low-tier-trace.json --baseline logs/reports/20260525T093846Z-target-baseline-trace.json
python scripts/inspect_eligible_records.py --low-tier logs/reports/20260525T093751Z-low-tier-trace.json --baseline logs/reports/20260525T093846Z-target-baseline-trace.json
.venv/bin/pytest -v
```

## Non-Claims

This phase implements prompt-set selection and diagnostic eligibility evaluation only.

This is not output equality validation.
No output parity claim is made.
No target-equivalence claim is made.
No correctness claim is made.
No lossless-generation claim is made.
No benchmark claim is made.
No draft-acceptance metric is reported.

## Remaining Issues

Raw target-baseline traces still contain empty normalized output for 10 of 16 prompts. Those records are excluded from eligible valid-draft inspection.

## Conclusion

Phase 2.12 passed. Named prompt-set selection works for low-tier and target-baseline traces, and the new controlled eligibility prompt set produced 6 eligible valid-draft records in raw mode.

## Next Step

Recommended next step: design a prompt-mode or prompt-shape refinement pass focused on reducing raw target-baseline empty outputs while preserving valid-draft contribution classification.
