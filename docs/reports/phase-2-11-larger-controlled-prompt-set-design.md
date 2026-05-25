# Phase 2.11 Larger Controlled Prompt Set Design

## Summary

Phase 2.11 designs a larger controlled prompt set for future eligibility experiments. The goal is to increase the number of records that can pass the current diagnostic selector as `eligible_valid_draft_record` while preserving the existing fallback-aware interpretation rules.

This phase is design only. It does not change runtime behavior, prompt loading, trace generation, or diagnostic selection.

## Problem From Phase 2.10

Phase 2.10 showed that the current three-prompt trace set is too small and brittle for deeper draft-contribution inspection:

```text
raw mode:
  eligible_record_count: 1
  excluded_empty_baseline_record_count: 2

chat mode:
  eligible_record_count: 0
  excluded_fallback_derived_record_count: 3
```

The current interpretation remains:

```text
raw mode:
  exercises the Qwen draft path, but some Gemma baseline outputs are empty

chat mode:
  produces non-empty Gemma baseline outputs, but low-tier records are fallback-derived
```

The next prompt set should make raw-mode Gemma baseline outputs less likely to be empty while keeping Qwen drafts simple enough to pass text-bridge normalization.

## Prompt Design Goals

The prompt set should optimize for trace eligibility, not model quality assessment.

Design goals:

```text
short expected completions
low ambiguity
instruction-following friendly
Gemma raw-mode less likely to produce empty output
Qwen draft likely to pass bridge normalization
avoid long reasoning
avoid prompts likely to trigger heavy thinking output
avoid open-ended creative writing
avoid safety-sensitive content
small enough for local iteration
```

Suggested size:

```text
16 prompts
```

Sixteen prompts is large enough to avoid over-reading a three-record trace, but still small enough for local Qwen CPU plus Gemma CUDA iteration.

## Prompt Set Metadata

Proposed prompt set id:

```text
phase-2-controlled-eligibility-v1
```

Prompt metadata fields:

```text
prompt_set_id
prompt_id
prompt_text
prompt_type
expected_output_shape
risk_notes
```

Stable prompt IDs:

```text
elig-001
elig-002
...
elig-016
```

Future implementation should add a named prompt-set registry rather than replacing `phase-1-controlled-trace-v1`. The existing default trace path should remain available for continuity.

## Proposed Prompt Set

| prompt_id | prompt_type | prompt_text | expected_output_shape | risk_notes |
| --- | --- | --- | --- | --- |
| elig-001 | fixed reply | Answer with only: ready | single token or short word | Very constrained; useful for baseline non-empty check. |
| elig-002 | short phrase | Write three words about latency. | three-word phrase | May produce punctuation, but should stay short. |
| elig-003 | short list | List two colors. | two-item list or short phrase | Low ambiguity; likely non-empty in raw mode. |
| elig-004 | short definition | Define caching in one sentence. | one sentence | Common concept; low safety risk. |
| elig-005 | short sentence | Write exactly one short sentence about GPU inference. | one short sentence | May not obey exactly, but expected output is compact. |
| elig-006 | naming | Name two common operating systems. | two names | Factual/general; likely short. |
| elig-007 | transformation | Rewrite "fast model" as a short phrase. | short phrase | Low ambiguity; keeps generation brief. |
| elig-008 | sentence completion | Complete this sentence: Machine learning is | short completion | Raw-mode friendly because it invites continuation. |
| elig-009 | short answer | Give one benefit of batching. | short sentence or phrase | Common systems topic; likely compact. |
| elig-010 | greeting | Reply with a five-word greeting. | five-word greeting | Similar to prior prompt but explicitly response-shaped. |
| elig-011 | classification | Is CUDA related to CPU or GPU? Answer briefly. | short answer | Low ambiguity; tests concise factual response. |
| elig-012 | acronym | Expand the acronym API in one short phrase. | short phrase | Common enough; low reasoning demand. |
| elig-013 | contrast | Name one difference between RAM and storage. | short sentence | Controlled general explanation. |
| elig-014 | count | Write two words that describe reliability. | two words | Compact and low risk. |
| elig-015 | simple summary | Summarize "small draft model" in three words. | three-word phrase | Domain-adjacent but concise. |
| elig-016 | completion | Finish the phrase: A verifier checks | short completion | Raw continuation style; relevant to the project. |

## Risk Controls

Prompt-level controls:

```text
avoid sensitive topics
avoid open-ended story prompts
avoid multi-step reasoning requests
avoid prompts that invite hidden reasoning
prefer short phrases, fixed replies, and one-sentence answers
prefer raw-continuation-friendly prompts where possible
```

Trace-level controls:

```text
keep max_tokens unchanged unless Phase 2.12 explicitly designs a settings update
keep temperature at 0.0
keep raw output capture opt-in
record prompt_set_id in trace metadata
preserve prompt IDs across low-tier and baseline traces
run selector after each trace pair
do not weaken fallback-derived exclusions
```

Interpretation controls:

```text
eligible records remain diagnostic candidates only
fallback-derived records remain excluded from draft-contribution inspection
empty-baseline records remain excluded or uninformative
unknown-contribution records remain excluded
diagnostic exact-string flags remain inspection metadata only
```

## Evaluation Plan

Phase 2.12 should implement prompt-set selection and then run the new set through the existing diagnostic stack.

Proposed commands:

```bash
python scripts/run_low_tier_trace.py \
  --capture-raw-output \
  --prompt-mode raw \
  --prompt-set phase-2-controlled-eligibility-v1

python scripts/run_baseline_trace.py \
  --capture-raw-output \
  --prompt-mode raw \
  --prompt-set phase-2-controlled-eligibility-v1

python scripts/inspect_eligible_records.py \
  --low-tier logs/reports/<low-tier-trace>.json \
  --baseline logs/reports/<target-baseline-trace>.json
```

If `--prompt-set` does not exist yet, Phase 2.12 should implement it minimally for:

```text
scripts/run_low_tier_trace.py
scripts/run_baseline_trace.py
src/htfsd/metrics/prompt_sets.py
```

Evaluation fields to report:

```text
prompt_set_id
total_prompts
valid_draft_continuation_count
fallback_after_rejection_count
fallback_only_count
unknown_contribution_count
baseline_empty_after_normalization_count
eligible_valid_draft_record_count
excluded_empty_baseline_record_count
excluded_fallback_derived_record_count
excluded_unknown_contribution_record_count
excluded_prompt_mode_risk_record_count
```

The evaluation should compare the new prompt set against the current three-prompt set only as diagnostic metadata. It should not convert eligibility counts into correctness or runtime claims.

## Non-Claims

This is not output equality validation.
No output parity claim is made.
No target-equivalence claim is made.
No correctness claim is made.
No lossless-generation claim is made.
No benchmark claim is made.
No draft-acceptance metric is reported.

## Recommended Next Step

Phase 2.12 should implement named prompt-set selection:

```text
Phase 2.12: Controlled Prompt Set Registry and Eligibility Evaluation
```

Recommended implementation scope:

```text
add phase-2-controlled-eligibility-v1 to the prompt-set registry
add --prompt-set to low-tier and baseline trace CLIs
preserve the existing default prompt set
run raw-mode low-tier and baseline traces with the new prompt set
run eligible-record inspection
write a diagnostic eligibility report
avoid output, target, correctness, lossless, or runtime claims
```

## Conclusion

Phase 2.11 defines a controlled prompt set intended to produce more eligible valid-draft records for future inspection. The design keeps the existing diagnostic guardrails intact: eligibility is a filter for further inspection, not a claim about generation quality or target behavior.
