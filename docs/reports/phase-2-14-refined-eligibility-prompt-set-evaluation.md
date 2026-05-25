# Phase 2.14 Refined Eligibility Prompt Set Evaluation

## Summary

Phase 2.14 implemented `phase-2-controlled-eligibility-v2` and evaluated it through the existing raw-mode diagnostic eligibility pipeline.

The refined v2 prompt set produced 16 low-tier raw records, all classified as `valid_draft_continuation`. The raw target-baseline trace produced non-empty normalized output for all 16 records. The selector marked all 16 records as `eligible_valid_draft_record`.

## Prompt Set Registry Update

The prompt-set registry now contains:

- `phase-1-controlled-trace-v1`
- `phase-2-controlled-eligibility-v1`
- `phase-2-controlled-eligibility-v2`

Existing prompt sets were preserved.

## Input Prompt Set

- prompt_set_id: `phase-2-controlled-eligibility-v2`
- total_prompts: 16
- prompt_ids: `elig2-001` through `elig2-016`

The v2 prompt set uses continuation-friendly sentence stems:

- `elig2-001`: A short readiness reply is
- `elig2-002`: Latency in one short phrase is
- `elig2-003`: Two common colors are
- `elig2-004`: Caching means
- `elig2-005`: GPU inference is useful because
- `elig2-006`: Two common operating systems are
- `elig2-007`: A fast model can be described as
- `elig2-008`: Machine learning is
- `elig2-009`: Batching helps because
- `elig2-010`: A friendly greeting could be
- `elig2-011`: CUDA is related to
- `elig2-012`: API stands for
- `elig2-013`: RAM differs from storage because
- `elig2-014`: Reliable systems are usually
- `elig2-015`: A small draft model is
- `elig2-016`: A verifier checks

## Raw Low-Tier Trace Result

Trace file:

- `logs/reports/20260525T132815Z-low-tier-trace.json`

Result:

- total_records: 16
- fallback_count: 0
- qwen_device_status: ok
- gemma_device_status: ok

Low-tier classification:

- valid_draft_continuation_count: 16
- fallback_after_rejection_count: 0
- fallback_only_count: 0
- unknown_contribution_count: 0

## Raw Baseline Trace Result

Trace file:

- `logs/reports/20260525T132830Z-target-baseline-trace.json`

Result:

- total_records: 16
- gemma_device_status: ok

Output health:

- low_tier_empty_after_normalization_count: 0
- baseline_empty_after_normalization_count: 0
- all_low_tier_outputs_present: true
- all_baseline_outputs_present: true
- prompt_mode_risk: `none`

## Selector Result

Selector reports:

- markdown: `logs/reports/20260525T132845Z-diagnostic-record-selection.md`
- json: `logs/reports/20260525T132845Z-diagnostic-record-selection.json`

Selection counts:

- total_records: 16
- eligible_valid_draft_record_count: 16
- excluded_empty_baseline_record_count: 0
- excluded_fallback_derived_record_count: 0
- excluded_unknown_contribution_record_count: 0
- excluded_prompt_mode_risk_record_count: 0
- blocking_reasons: []

Eligible prompt IDs:

- `elig2-001`
- `elig2-002`
- `elig2-003`
- `elig2-004`
- `elig2-005`
- `elig2-006`
- `elig2-007`
- `elig2-008`
- `elig2-009`
- `elig2-010`
- `elig2-011`
- `elig2-012`
- `elig2-013`
- `elig2-014`
- `elig2-015`
- `elig2-016`

Excluded empty-baseline prompt IDs:

- none

## Eligible Inspection Result

Eligible inspection reports:

- markdown: `logs/reports/20260525T132845Z-eligible-record-inspection.md`
- json: `logs/reports/20260525T132845Z-eligible-record-inspection.json`

Inspection result:

- inspection_ready: yes
- eligible_record_count: 16
- excluded_empty_baseline_record_count: 0
- excluded_fallback_derived_record_count: 0
- excluded_unknown_contribution_record_count: 0
- excluded_prompt_mode_risk_record_count: 0
- blocking_reasons: []

## Comparison Against v1

Phase 2.12 v1 raw-mode diagnostic result:

- total_prompts: 16
- valid_draft_continuation_count: 16
- baseline_empty_after_normalization_count: 10
- eligible_valid_draft_record_count: 6
- excluded_empty_baseline_record_count: 10

Phase 2.14 v2 raw-mode diagnostic result:

- total_prompts: 16
- valid_draft_continuation_count: 16
- baseline_empty_after_normalization_count: 0
- eligible_valid_draft_record_count: 16
- excluded_empty_baseline_record_count: 0

The refined v2 prompt set produced 16 eligible valid-draft records in this run. The refined v2 prompt set produced 0 empty baseline records in this run.

This comparison is diagnostic only.

## Warnings

No selector blocking reasons were reported.

Runtime logs continued to include expected llama.cpp/CUDA model-loading and graph messages. Gemma E2B device status remained `ok`.

## Tests

Verification commands run:

```bash
python scripts/check_env.py
python scripts/run_low_tier_trace.py --capture-raw-output --prompt-mode raw --prompt-set phase-2-controlled-eligibility-v2
python scripts/run_baseline_trace.py --capture-raw-output --prompt-mode raw --prompt-set phase-2-controlled-eligibility-v2
python scripts/select_diagnostic_records.py --low-tier logs/reports/20260525T132815Z-low-tier-trace.json --baseline logs/reports/20260525T132830Z-target-baseline-trace.json
python scripts/inspect_eligible_records.py --low-tier logs/reports/20260525T132815Z-low-tier-trace.json --baseline logs/reports/20260525T132830Z-target-baseline-trace.json
.venv/bin/pytest -v
```

## Non-Claims

This phase implements and evaluates a refined prompt set only.

This is not output equality validation.
No output parity claim is made.
No target-equivalence claim is made.
No correctness claim is made.
No lossless-generation claim is made.
No benchmark claim is made.
No draft-acceptance metric is reported.

## Remaining Issues

The v2 result increases the number of eligible diagnostic records, but those records are still inspection inputs only. They do not establish target-equivalent generation or exact speculative decoding behavior.

## Conclusion

Phase 2.14 passed. The refined continuation-style prompt set preserved low-tier `valid_draft_continuation` classification for all 16 records and removed raw target-baseline empty-output exclusions in this run.

## Next Step

Recommended next step: design a small eligible-record diagnostic inspection pass over the 16 v2 records, still grouped as diagnostic metadata only and without target-equivalence claims.
