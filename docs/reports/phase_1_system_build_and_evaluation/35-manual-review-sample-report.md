# Task 35: Manual Review Sample for NO_CONTAINMENT Rows

Date: 2026-06-04

## Result

PASS, preliminary.

This is a manual review of Task 31 no-containment rows only. It does not claim final correctness, final EM, or production readiness.

## Scope

Reviewed all Task 31 rows that the deterministic Task 32 scorer labeled `NO_CONTAINMENT`.

Artifacts inspected:

- `results/phase_1_system_build_and_evaluation/early_experiments/task31_dflash_r1_longctx_text_n6.jsonl`
- `results/phase_1_system_build_and_evaluation/early_experiments/task31_cc_llm_r2_longctx_text_n6.jsonl`
- `results/phase_1_system_build_and_evaluation/early_experiments/task31_cc_llm_r3_longctx_text_n6.jsonl`
- `results/phase_1_system_build_and_evaluation/early_experiments/task31_llmlingua_ar_r2_longctx_text_n6.jsonl`
- `results/phase_1_system_build_and_evaluation/early_experiments/task31_llmlingua_ar_r3_longctx_text_n6.jsonl`

Selection method:

- Use the deterministic Task 32 scorer output from `results/phase_1_system_build_and_evaluation/early_experiments/task32_answer_quality_summary.json`.
- Include every row with `score_category == NO_CONTAINMENT`.
- The sample was small enough to review exhaustively, so no sampling was needed.

## Reviewed Rows

| Source artifact | Condition | Prompt id | Expected answer | Generated output summary | Original label | Manual label | Rationale |
| --- | --- | ---: | --- | --- | --- | --- | --- |
| `results/phase_1_system_build_and_evaluation/early_experiments/task31_dflash_r1_longctx_text_n6.jsonl` | DFlash-R1 | 1 | 410 dollars | Begins with “The question asks…” and then steps through context; no amount appears. | NO_CONTAINMENT | TRUE_FAIL | The output does not give the paid amount, and the evidence clearly contains `410 dollars`. |
| `results/phase_1_system_build_and_evaluation/early_experiments/task31_dflash_r1_longctx_text_n6.jsonl` | DFlash-R1 | 3 | 37 cartons | Starts with “Let’s break down the information…” but never states the remaining cartons. | NO_CONTAINMENT | TRUE_FAIL | The expected arithmetic result is absent even though the evidence states `37 cartons`. |
| `results/phase_1_system_build_and_evaluation/early_experiments/task31_dflash_r1_longctx_text_n6.jsonl` | DFlash-R1 | 6 | 23 students | Lists `26 students` and `3 students` withdrawn, but the final roster count is not stated. | NO_CONTAINMENT | TRUE_FAIL | The output shows intermediate facts but never concludes with `23 students`. |
| `results/phase_1_system_build_and_evaluation/early_experiments/task31_cc_llm_r2_longctx_text_n6.jsonl` | CC-LLM-R2 | 1 | 410 dollars | Opens with a question restatement and extraction steps; no final payment amount is shown. | NO_CONTAINMENT | TRUE_FAIL | The answer is missing even though the evidence explicitly gives `410 dollars`. |
| `results/phase_1_system_build_and_evaluation/early_experiments/task31_cc_llm_r2_longctx_text_n6.jsonl` | CC-LLM-R2 | 2 | 20 items | Explains the tier lookup but stops before stating the borrow limit. | NO_CONTAINMENT | TRUE_FAIL | The evidence says `20 items`; the generation does not. |
| `results/phase_1_system_build_and_evaluation/early_experiments/task31_cc_llm_r2_longctx_text_n6.jsonl` | CC-LLM-R2 | 3 | 37 cartons | Describes the Bay 2 shipment calculation but does not state the result. | NO_CONTAINMENT | TRUE_FAIL | The final arithmetic answer is absent. |
| `results/phase_1_system_build_and_evaluation/early_experiments/task31_cc_llm_r2_longctx_text_n6.jsonl` | CC-LLM-R2 | 6 | 23 students | Walks through the roster logic and stops at “Given Information.” | NO_CONTAINMENT | TRUE_FAIL | The final roster count never appears, despite being explicit in the evidence. |
| `results/phase_1_system_build_and_evaluation/early_experiments/task31_cc_llm_r3_longctx_text_n6.jsonl` | CC-LLM-R3 | 1 | 410 dollars | Restates the invoice question and starts extracting details, but no amount appears. | NO_CONTAINMENT | TRUE_FAIL | The model never outputs `410 dollars`. |
| `results/phase_1_system_build_and_evaluation/early_experiments/task31_cc_llm_r3_longctx_text_n6.jsonl` | CC-LLM-R3 | 2 | 20 items | Identifies the Research tier and borrow policy context, but no limit is given. | NO_CONTAINMENT | TRUE_FAIL | The answer is not present in any form reviewed. |
| `results/phase_1_system_build_and_evaluation/early_experiments/task31_cc_llm_r3_longctx_text_n6.jsonl` | CC-LLM-R3 | 3 | 37 cartons | Restates the cartons problem and continues reasoning without a conclusion. | NO_CONTAINMENT | TRUE_FAIL | The expected count is missing. |
| `results/phase_1_system_build_and_evaluation/early_experiments/task31_cc_llm_r3_longctx_text_n6.jsonl` | CC-LLM-R3 | 5 | 5 years | Discusses retention policy context but does not state the retention length. | NO_CONTAINMENT | TRUE_FAIL | The explicit answer `5 years` is absent. |
| `results/phase_1_system_build_and_evaluation/early_experiments/task31_cc_llm_r3_longctx_text_n6.jsonl` | CC-LLM-R3 | 6 | 23 students | Explains the roster logic and stops while analyzing the input. | NO_CONTAINMENT | TRUE_FAIL | No final count is produced. |
| `results/phase_1_system_build_and_evaluation/early_experiments/task31_llmlingua_ar_r2_longctx_text_n6.jsonl` | LLMLingua-AR-R2 | 1 | 410 dollars | Same pattern as DFlash: question restated, then reasoning starts, but no amount. | NO_CONTAINMENT | TRUE_FAIL | The output does not answer the question. |
| `results/phase_1_system_build_and_evaluation/early_experiments/task31_llmlingua_ar_r2_longctx_text_n6.jsonl` | LLMLingua-AR-R2 | 3 | 37 cartons | Shows the setup for the Bay 2 subtraction, but not the final total. | NO_CONTAINMENT | TRUE_FAIL | The arithmetic result is missing. |
| `results/phase_1_system_build_and_evaluation/early_experiments/task31_llmlingua_ar_r2_longctx_text_n6.jsonl` | LLMLingua-AR-R2 | 6 | 23 students | Begins the roster count explanation and stops after introducing the facts. | NO_CONTAINMENT | TRUE_FAIL | The final roster count is absent. |
| `results/phase_1_system_build_and_evaluation/early_experiments/task31_llmlingua_ar_r3_longctx_text_n6.jsonl` | LLMLingua-AR-R3 | 1 | 410 dollars | Restates the payment question and extracts context, but no amount is returned. | NO_CONTAINMENT | TRUE_FAIL | The expected answer is not present. |
| `results/phase_1_system_build_and_evaluation/early_experiments/task31_llmlingua_ar_r3_longctx_text_n6.jsonl` | LLMLingua-AR-R3 | 2 | 20 items | Explains the Research tier lookup and does not conclude. | NO_CONTAINMENT | TRUE_FAIL | The borrow limit never appears. |
| `results/phase_1_system_build_and_evaluation/early_experiments/task31_llmlingua_ar_r3_longctx_text_n6.jsonl` | LLMLingua-AR-R3 | 3 | 37 cartons | Continues the carton subtraction setup without stating the result. | NO_CONTAINMENT | TRUE_FAIL | The final arithmetic answer is missing. |
| `results/phase_1_system_build_and_evaluation/early_experiments/task31_llmlingua_ar_r3_longctx_text_n6.jsonl` | LLMLingua-AR-R3 | 5 | 5 years | Discusses retention policy background and stops before the duration. | NO_CONTAINMENT | TRUE_FAIL | The expected duration is absent. |
| `results/phase_1_system_build_and_evaluation/early_experiments/task31_llmlingua_ar_r3_longctx_text_n6.jsonl` | LLMLingua-AR-R3 | 6 | 23 students | Analyzes the trip roster changes but never gives the final count. | NO_CONTAINMENT | TRUE_FAIL | The answer `23 students` is not present. |

## Summary

Reviewed rows: 20

Manual labels:

- `TRUE_FAIL`: 20
- `PARAPHRASE_OR_FORMAT_MISS`: 0
- `UNCLEAR`: 0

By condition:

- `DFlash-R1`: 3 reviewed rows
- `CC-LLM-R2`: 4 reviewed rows
- `CC-LLM-R3`: 5 reviewed rows
- `LLMLingua-AR-R2`: 3 reviewed rows
- `LLMLingua-AR-R3`: 5 reviewed rows

Risk notes:

- `CC-LLM-R3` and `LLMLingua-AR-R3` had the highest no-containment counts, so they are the most likely to merit follow-up.
- Even so, the manual review did not find paraphrase-only misses in this sample.
- The containment scorer appears mostly accurate here and may actually be a little conservative rather than too strict.

## Interpretation

`TRUE_FAIL` rows suggest the model stopped in reasoning mode or never produced a final answer, even when the ground-truth answer was explicit in the fixture evidence.

`PARAPHRASE_OR_FORMAT_MISS` would suggest the scorer is too strict and that a semantically correct answer was hidden by formatting, wording, or a different numeric presentation. This sample did not show that case.

`UNCLEAR` would indicate the output is too incomplete or ambiguous for a manual judgment. This sample did not require that label.

## Limitations

- Small sample, but exhaustive for the available no-containment rows.
- Synthetic fixture, not a live dataset.
- Containment is not semantic correctness.
- No final EM claim.
- No model rerun or benchmark rerun was performed.

## Recommendation For Task 36

Add a manual-review analyzer that can ingest row-level containment labels plus human labels, then summarize whether `NO_CONTAINMENT` is dominated by true failures or by paraphrase/format misses. That will make later correctness-vs-breakeven decisions easier to defend.
