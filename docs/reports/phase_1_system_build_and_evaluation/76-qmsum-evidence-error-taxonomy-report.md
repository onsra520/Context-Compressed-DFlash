# Task 76 — QMSum Evidence-Error Taxonomy After Balanced Policy

Date: 2026-06-13

Status: PASS_WITH_NOTES

## Scope

Task 76 is a read-only taxonomy analysis of Task 75 QMSum balanced-policy artifacts. It does not run benchmarks, load models, load LLMLingua, use CUDA, run n=100, run mnt512, or modify old Task 71, Task 73, or Task 75 artifacts.

This is lexical/sample-level evidence triage only. It is not semantic judging and not a final correctness or speedup claim.

## Task 75 Commit

Task 75 was already committed before this task:

- Commit: `3287fbd test: calibrate qmsum balanced answer policy`

## Why This Task Exists

Task 75 fixed QMSum compressed cap pressure:

- LLMLingua-AR-R2 cap hits: 0/30
- CC-DFlash-R2 cap hits: 0/30
- Balanced policy preserved: 30/30 for both compressed conditions

However, Task 75 did not solve QMSum quality under lexical proxy diagnostics. Its broad `STILL_TOO_SHORT` label did not distinguish missing evidence, wrong evidence focus, missing entities/numbers, wrong-negative answers, or genuinely acceptable concise answers. Task 76 splits those cases into a more useful evidence-error taxonomy.

## Inputs

| Input | Row count / status |
| --- | ---: |
| `results/phase_1_system_build_and_evaluation/early_experiments/task75_qmsum_balanced_policy_cases.jsonl` | 60 rows |
| `results/phase_1_system_build_and_evaluation/early_experiments/task75_qmsum_balanced_policy_summary.json` | present |
| `results/phase_1_system_build_and_evaluation/early_experiments/task75_qmsum_balanced_policy_table.csv` | present |
| `results/phase_1_system_build_and_evaluation/early_experiments/task75_qmsum_long_llmlingua_ar_r2_n30_mnt384_balanced.jsonl` | 30 rows |
| `results/phase_1_system_build_and_evaluation/early_experiments/task75_qmsum_long_cc_dflash_r2_n30_mnt384_balanced.jsonl` | 30 rows |
| `results/phase_1_system_build_and_evaluation/early_experiments/task73_qmsum_concise_policy_cases.jsonl` | 91 rows |
| `results/phase_1_system_build_and_evaluation/early_experiments/task71_qmsum_n30_failure_samples.jsonl` | 86 rows |
| `docs/reports/75-qmsum-balanced-policy-report.md` | present |

Primary taxonomy input was the 60-row Task 75 case file.

## Outputs

| Output | Row count / scope |
| --- | ---: |
| `results/phase_1_system_build_and_evaluation/early_experiments/task76_qmsum_evidence_error_summary.json` | 60 rows summarized |
| `results/phase_1_system_build_and_evaluation/early_experiments/task76_qmsum_evidence_error_table.csv` | 2 condition rows |
| `results/phase_1_system_build_and_evaluation/early_experiments/task76_qmsum_evidence_error_cases.jsonl` | 60 labeled cases |

## Old Task 75 Labels

| Task 75 label | Count |
| --- | ---: |
| `STILL_TOO_SHORT` | 49 |
| `UNCLEAR` | 7 |
| `ACCEPTABLE_BALANCED_ANSWER` | 2 |
| `PROXY_WEAKNESS` | 2 |

## New Evidence-Error Labels

Task 76-fix refined the committed Task 76 taxonomy after audit. The original committed counts were: `MISSING_ENTITY_OR_NUMBER`: 35, `EVIDENCE_MISSING_OR_MISFOCUSED`: 8, `WRONG_NEGATIVE`: 5, `ANSWER_TOO_GENERAL`: 5, `UNCLEAR`: 4, `PROXY_WEAKNESS`: 2, and `STILL_TOO_SHORT`: 1. The refined counts below remove noisy discourse words from missing-entity extraction and prioritize evidence-misfocus / wrong-negative labels before missing-entity labels where appropriate.

| Task 76 label | Count |
| --- | ---: |
| `EVIDENCE_MISSING_OR_MISFOCUSED` | 28 |
| `MISSING_ENTITY_OR_NUMBER` | 14 |
| `WRONG_NEGATIVE` | 7 |
| `ANSWER_TOO_GENERAL` | 4 |
| `UNCLEAR` | 4 |
| `PROXY_WEAKNESS` | 2 |
| `STILL_TOO_SHORT` | 1 |
| `ACCEPTABLE_EVIDENCE_FOCUSED_ANSWER` | 0 |
| `POSSIBLE_COMPRESSION_EVIDENCE_LOSS` | 0 |

The most important change is that the old broad `STILL_TOO_SHORT` bucket is mostly not merely short. After the Task 76-fix refinement, it mostly reflects evidence targeting / misfocus, missing concrete entities/numbers, and wrong-negative answers. The refinement also filters noisy sentence-initial discourse words such as `Plus`, `Although`, and `Therefore` from the missing-entity list while preserving real entities and numbers.

## Per-Condition Comparison

| Condition | Rows | Cap hits | Policy preservation | Avg overlap | Avg output tokens | Avg e2e latency s | Main labels |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| LLMLingua-AR-R2 | 30 | 0 | 1.00 | 0.261336 | 91.00 | 10.475600 | `EVIDENCE_MISSING_OR_MISFOCUSED`: 14, `MISSING_ENTITY_OR_NUMBER`: 7, `WRONG_NEGATIVE`: 3 |
| CC-DFlash-R2 | 30 | 0 | 1.00 | 0.259867 | 92.50 | 9.484380 | `EVIDENCE_MISSING_OR_MISFOCUSED`: 14, `MISSING_ENTITY_OR_NUMBER`: 7, `WRONG_NEGATIVE`: 4 |

Both compressed paths show similar evidence-error patterns. CC-DFlash-R2 remains faster in approximate e2e latency on this artifact set, but Task 76 is not a speed benchmark and does not make a final speedup claim.

## Shared-Failure Analysis

Prompt IDs where both compressed conditions received the same new label:

| Label | Shared prompt IDs |
| --- | --- |
| `EVIDENCE_MISSING_OR_MISFOCUSED` | 2, 4, 6, 7, 9, 11, 13, 16, 18, 19, 26, 27, 30 |
| `MISSING_ENTITY_OR_NUMBER` | 1, 8, 15, 17, 21, 24, 29 |
| `WRONG_NEGATIVE` | 14, 23, 28 |
| `ANSWER_TOO_GENERAL` | 5, 22 |
| `PROXY_WEAKNESS` | 10 |
| `UNCLEAR` | 3, 12 |

Most prompt IDs have the same label in both compressed conditions. Prompt 20 is intentionally split after refinement: CC-DFlash-R2 is `WRONG_NEGATIVE`, while LLMLingua-AR-R2 is `EVIDENCE_MISSING_OR_MISFOCUSED`. Prompt 25 is also split between `EVIDENCE_MISSING_OR_MISFOCUSED` and `STILL_TOO_SHORT`. The pattern suggests the issue is not isolated to one decoding path. It is more likely tied to compressed evidence targeting, output policy, and the lexical nature of the proxy.

Worst prompt IDs by evidence-error labels:

`2, 4, 5, 6, 7, 8, 9, 11, 13, 14, 15, 16, 17, 18, 19, 20, 21, 23, 24, 26, 27, 28, 29, 30`

Proxy-weakness prompt IDs:

`10`

Acceptable prompt IDs:

None under the stricter Task 76 evidence-focused taxonomy.

## Representative Examples

### ACCEPTABLE_EVIDENCE_FOCUSED_ANSWER

No cases were labeled `ACCEPTABLE_EVIDENCE_FOCUSED_ANSWER` under the stricter Task 76 taxonomy. The previous Task 75 `ACCEPTABLE_BALANCED_ANSWER` examples were reclassified because they still missed concrete evidence or entities under the new rules.

### PROXY_WEAKNESS

Prompt 10, both compressed conditions.

- Expected: the remote control should be original, trendy, easy to use, international, and not too expensive.
- Balanced answers discuss international, user-friendly, original remote-control design and price.
- Rationale: lexical overlap is imperfect, but the answer appears semantically close enough to keep as proxy weakness rather than clear failure.

### STILL_TOO_SHORT

LLMLingua-AR-R2 prompt 25.

- Expected: the industrial designer recommended mixing several functions in one button with a switch menu.
- Generated: discusses merging a Google system with remote-control design and balancing powerful functionality with ease of use.
- Rationale: the answer is on a related evidence path but remains too brief and does not supply enough expected detail.

### EVIDENCE_MISSING_OR_MISFOCUSED

Prompt 2, both compressed conditions.

- Expected: lapel microphones were too close and not representative; microphones captured breath and non-voice sounds.
- Generated: focuses on wireless headset suitability and microphone setup, including claims that shift the evidence target.
- Rationale: wrong part of the meeting evidence is emphasized.

Prompt 11, both compressed conditions.

- Expected: advocacy for aboriginals, students, indigenous/rural residents, Black Americans, and related pandemic impacts.
- Generated: focuses on first responders, healthcare workers, local businesses, pollinators, and killer whales.
- Rationale: clear evidence misfocus.

### WRONG_NEGATIVE

Prompt 14, both compressed conditions.

- Expected: PhD C explained 100 ms silence probability delay, 40 ms input delta delay, and 10 ms LDA filter delay.
- Generated: says specific latency details are not provided.
- Rationale: wrong-negative answer despite concrete expected evidence.

Prompt 23, both compressed conditions.

- Expected: oil and gas industry under severe strain; pressure from anti-oil/gas lobby groups; oil sands; and federal Liberal government response.
- Generated: says the stress faced by oil and gas is not directly addressed or shifts to unrelated government-support topics.
- Rationale: wrong-negative pattern despite concrete oil-and-gas evidence in the expected answer.

### MISSING_ENTITY_OR_NUMBER

Prompt 15, both compressed conditions.

- Expected: 25 Euro selling price, 50 million Euro profit aim, four million selling target, and 50 percent profit goal.
- Generated: includes some project-plan details but misses parts of the concrete numeric evidence.
- Rationale: on topic but missing important numbers.

Prompt 20, LLMLingua-AR-R2 is `EVIDENCE_MISSING_OR_MISFOCUSED`; CC-DFlash-R2 is `WRONG_NEGATIVE`.

- Expected: computational-resource concern, two 550 MHz IBM processors, and 800+ MB memory detail.
- Generated: shifts to neural-network generalization and language/task examples.
- Rationale: generated text is on the wrong evidence path; the CC-DFlash-R2 row additionally fits the wrong-negative pattern.

### ANSWER_TOO_GENERAL

Prompt 1, both compressed conditions.

- Expected: speech/gesture recognition, convenience when the controller is lost, reliability caveat, and differentiation motivation.
- Generated: broadly discusses an intelligent controller and innovation.
- Rationale: broadly on topic but lacking concrete support.

### UNCLEAR

Prompt 3 and prompt 12, both compressed conditions.

- Outputs are on topic and contain some relevant details, but snippets and lexical diagnostics do not support a stronger label without manual/semantic review.

## Decision

Task 76 decision:

- Do not run `max_new_tokens=512` next. Task 75 cap hits are already zero.
- Do not run QMSum n=100. Evidence targeting and answer completeness are not stable.
- Do not freeze the Task 75 balanced policy.
- Do not reject the protected-suffix mechanism. It still controls cap pressure and preserves the policy.
- Recommend Task 77: evidence-focused QMSum protected-suffix calibration.

Recommended Task 77 direction:

- Keep bounded compressed-only QMSum runs.
- Preserve the protected suffix mechanism.
- Add wording that explicitly requires the answer to include the key names, numbers, decisions, reasons, and evidence from the meeting.
- Explicitly discourage “not mentioned / not provided” unless the model is certain.
- Continue storing generated text and policy metadata.
- Consider manual or semantic review before using QMSum as a final quality signal.

If future analysis finds many `POSSIBLE_COMPRESSION_EVIDENCE_LOSS` rows with prompt/context evidence, then the next move should be compressed-prompt/context audit rather than more prompt wording. Task 76 did not assign that label from the available snippets.

## Understand-Anything

Understand-Anything refresh was skipped because `/understand` is not available in this environment.

## Validation

Validation was run after analyzer, output, report, and documentation changes. See final task response for command results.

## Limitations

- Taxonomy is heuristic and lexical/sample-level.
- It uses generated snippets and expected answers, not a semantic judge.
- Some entity extraction is approximate and may over-count sentence-initial words.
- This task analyzes only Task 75 compressed conditions.
- No benchmark was run.
