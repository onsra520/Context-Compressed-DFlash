# Phase 2.13 Prompt Shape Refinement Design

## Summary

Phase 2.13 designs a refined controlled eligibility prompt set intended to reduce raw target-baseline empty outputs while preserving low-tier valid-draft contribution classification.

This is a design-only phase. It does not implement the refined prompt set.

## Problem From Phase 2.12

Phase 2.12 evaluated `phase-2-controlled-eligibility-v1`:

- total_records: 16
- valid_draft_continuation_count: 16
- fallback_after_rejection_count: 0
- fallback_only_count: 0
- unknown_contribution_count: 0
- baseline_empty_after_normalization_count: 10
- eligible_valid_draft_record_count: 6
- excluded_empty_baseline_record_count: 10

The low-tier raw path remained healthy: every record classified as `valid_draft_continuation`. The limiting factor was the raw target-baseline path: 10 of 16 baseline outputs were empty after normalization, so those records were excluded from eligible inspection.

## Eligible Prompt Shape Observations

Eligible prompt IDs from Phase 2.12:

- `elig-004`: Define caching in one sentence.
- `elig-008`: Complete this sentence: Machine learning is
- `elig-009`: Give one benefit of batching.
- `elig-010`: Reply with a five-word greeting.
- `elig-013`: Name one difference between RAM and storage.
- `elig-016`: Finish the phrase: A verifier checks

Observed common shape:

- Most eligible prompts invite a short explanatory sentence or natural continuation.
- Completion-style prompts worked in raw mode.
- The prompts are compact but not overly minimal.
- They do not force a bare token, exact two-item list, acronym expansion, or rewrite-only response.

These are observations from one controlled local run, not universal claims about model behavior.

## Empty-Baseline Prompt Shape Observations

Empty-baseline prompt IDs from Phase 2.12:

- `elig-001`: Answer with only: ready
- `elig-002`: Write three words about latency.
- `elig-003`: List two colors.
- `elig-005`: Write exactly one short sentence about GPU inference.
- `elig-006`: Name two common operating systems.
- `elig-007`: Rewrite "fast model" as a short phrase.
- `elig-011`: Is CUDA related to CPU or GPU? Answer briefly.
- `elig-012`: Expand the acronym API in one short phrase.
- `elig-014`: Write two words that describe reliability.
- `elig-015`: Summarize "small draft model" in three words.

Observed common shape:

- Several prompts ask for very constrained outputs.
- Several prompts use list, naming, rewrite, acronym, or exact word-count forms.
- Some prompts require an instruction-following response rather than a natural raw continuation.
- The failed shapes may be poorly matched to raw-mode Gemma baseline generation.

These are hypotheses from this prompt set and runtime, not a claim that the prompt types always fail.

## Refinement Hypotheses

Hypotheses for `phase-2-controlled-eligibility-v2`:

- Raw Gemma baseline may respond better to continuation-style phrasing than to terse command-style prompts.
- Short explanatory prompts may be more reliable than exact-count prompts in raw mode.
- Sentence stems such as "Two common colors are" or "API stands for" may reduce empty baseline outputs compared with direct commands.
- Keeping prompts compact should preserve low-tier valid-draft classification while avoiding long reasoning-heavy outputs.
- Avoiding forced minimal replies should reduce baseline empties without changing runtime policy or selector rules.

These hypotheses must be tested in Phase 2.14 with the existing selector and eligible-record inspection pipeline.

## Refined Prompt Set Metadata

Proposed prompt set:

- prompt_set_id: `phase-2-controlled-eligibility-v2`
- prompt_count: 16
- prompt_ids: `elig2-001` through `elig2-016`

Metadata fields should match the existing prompt-set registry style:

- `prompt_set_id`
- `prompt_id`
- `prompt_text`
- `prompt_type`
- `expected_output_shape`
- `risk_notes`

## Proposed Refined Prompt Set

| Prompt ID | Prompt Text | Prompt Type | Expected Output Shape | Risk Notes |
| --- | --- | --- | --- | --- |
| `elig2-001` | A short readiness reply is | continuation | short phrase | Replaces forced "Answer with only" shape. |
| `elig2-002` | Latency in one short phrase is | continuation | short phrase | Replaces exact three-word constraint. |
| `elig2-003` | Two common colors are | continuation | short list-like completion | Replaces bare list request. |
| `elig2-004` | Caching means | continuation | short definition | Keeps successful caching topic in continuation form. |
| `elig2-005` | GPU inference is useful because | continuation | short explanatory completion | Replaces exact sentence command. |
| `elig2-006` | Two common operating systems are | continuation | two-name completion | Replaces direct naming command. |
| `elig2-007` | A fast model can be described as | continuation | short phrase | Replaces rewrite command. |
| `elig2-008` | Machine learning is | continuation | short definition or completion | Keeps successful sentence stem. |
| `elig2-009` | Batching helps because | continuation | short explanation | Keeps successful batching topic in continuation form. |
| `elig2-010` | A friendly greeting could be | continuation | short greeting | Replaces exact five-word constraint. |
| `elig2-011` | CUDA is related to | continuation | short technical completion | Replaces direct question. |
| `elig2-012` | API stands for | continuation | acronym expansion | Replaces command-style acronym prompt. |
| `elig2-013` | RAM differs from storage because | continuation | short contrast | Keeps successful RAM/storage topic. |
| `elig2-014` | Reliable systems are usually | continuation | short descriptive completion | Replaces exact two-word constraint. |
| `elig2-015` | A small draft model is | continuation | short description | Replaces exact three-word summary. |
| `elig2-016` | A verifier checks | continuation | short completion | Keeps successful verifier stem. |

## Risk Controls

- Keep generation settings deterministic and trace-safe.
- Keep raw output capture opt-in.
- Keep prompts short and local-iteration friendly.
- Avoid safety-sensitive topics.
- Avoid prompts likely to trigger long reasoning.
- Preserve the existing selector priority rules.
- Preserve the existing default prompt set and v1 prompt set.
- Treat any increased eligible count as diagnostic eligibility only.

## Evaluation Plan

Phase 2.14 should implement `phase-2-controlled-eligibility-v2` and run:

```bash
python scripts/run_low_tier_trace.py \
  --capture-raw-output \
  --prompt-mode raw \
  --prompt-set phase-2-controlled-eligibility-v2

python scripts/run_baseline_trace.py \
  --capture-raw-output \
  --prompt-mode raw \
  --prompt-set phase-2-controlled-eligibility-v2

python scripts/select_diagnostic_records.py \
  --low-tier logs/reports/<new-low-tier-trace>.json \
  --baseline logs/reports/<new-baseline-trace>.json

python scripts/inspect_eligible_records.py \
  --low-tier logs/reports/<new-low-tier-trace>.json \
  --baseline logs/reports/<new-baseline-trace>.json
```

Evaluation should report:

- total_prompts
- valid_draft_continuation_count
- fallback_after_rejection_count
- fallback_only_count
- unknown_contribution_count
- baseline_empty_after_normalization_count
- eligible_valid_draft_record_count
- excluded_empty_baseline_record_count
- excluded_fallback_derived_record_count
- excluded_unknown_contribution_record_count
- excluded_prompt_mode_risk_record_count

Allowed interpretation:

- The refined prompt set produced N eligible valid-draft records in this run.
- The refined prompt set reduced empty baseline records in this run.

Disallowed interpretation:

- The refined prompt set proves model quality.
- The refined prompt set proves system correctness.
- The refined prompt set proves target-model equivalence.

## Non-Claims

This is not output equality validation.
No output parity claim is made.
No target-equivalence claim is made.
No correctness claim is made.
No lossless-generation claim is made.
No benchmark claim is made.
No draft-acceptance metric is reported.

## Recommended Next Step

Phase 2.14 should implement the `phase-2-controlled-eligibility-v2` prompt set in the registry, add tests for the stable prompt IDs, run the raw low-tier and raw target-baseline traces, and evaluate selector/inspection counts.

## Conclusion

Phase 2.13 proposes a continuation-friendly refinement of the eligibility prompt set. The design targets the current bottleneck: raw target-baseline empty outputs. It preserves the fallback-aware diagnostic boundary and does not introduce any new comparison claims.
