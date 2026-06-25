# Task108B — QMSum Targeted Repair Attempt

## 1. Purpose

Task108B attempts a narrow QMSum repair path before final Phase 2 closure. Unlike T108A, which found no simple mechanical reason to rerun QMSum, this task treats final project closure as requiring either a measured targeted repair attempt or an explicit final limitation decision.

This task ran only the six fixed QMSum residual-risk target rows. It did not run QMSum n100, a full matrix, Baseline-AR, DFlash-R1, Large CPU, LLMLingua-AR-R2, GSM8K, keep-rate tuning, query-aware compression, human scoring, or an LLM judge.

## 2. Why T108B Overrides The Earlier No-rerun Path

T108A recommended `NO_RERUN_KEEP_CAVEAT` because T105B had no mechanical QMSum output-shape issue: `0/30` empty/malformed rows and `0/30` cap-limited/incomplete rows. The user then updated the closure rule: do not close Phase 2 until QMSum has either a targeted repair attempt with measured outcome or an explicit final limitation decision after the attempt fails.

T108B therefore performs a small, gated repair attempt without changing defaults or expanding the benchmark matrix.

## 3. Target Row Selection

The run used the six T103D/T102F residual-risk rows from:

`data/eval/qmsum_meeting_qa_target_rows_task102f.jsonl`

Target fixture IDs:

| Fixture ID |
| --- |
| `qmsum_meeting_qa_test_0036` |
| `qmsum_meeting_qa_test_0070` |
| `qmsum_meeting_qa_test_0055` |
| `qmsum_meeting_qa_test_0078` |
| `qmsum_meeting_qa_test_0094` |
| `qmsum_meeting_qa_test_0001` |

The target dataset validation confirmed exactly six rows, no duplicate fixture IDs, required context/question/reference fields, and no prior generated outputs in prompt inputs.

## 4. Repair Policy

Policy name: `qmsum_evidence_grounded_concise_v1`

Runtime-only suffix:

> Answer using only information supported by the meeting transcript. First identify the most relevant evidence in the transcript mentally, then give a concise answer in 1-3 sentences. If the transcript does not contain enough evidence, say that the transcript does not provide enough information. Do not invent details.

The policy was supplied through the existing runtime-only QMSum policy override flags. Default QMSum behavior was not changed.

## 5. Runtime Setup

Command scope:

- condition: `CC-DFlash-R2`
- dataset: `qmsum_meeting_qa_long`
- dataset path: `data/eval/qmsum_meeting_qa_target_rows_task102f.jsonl`
- seed: `42`
- n: `6`
- `max_new_tokens=384`
- compressor profile: `light`
- compressor device map: `cuda`
- generated text stored
- resume enabled

Run artifact:

`results/phase_2_system_optimization/final_reruns/task108b_qmsum_targeted_repair_attempt/runs/cc_dflash_r2_light_gpu_qmsum_targeted_evidence_grounded.jsonl`

The run completed `6/6` rows. Metadata confirmed `light`, `cuda`, `local_files_only=true`, `requested_compressor_device_map=cuda`, and `qmsum_answer_policy_type=qmsum_evidence_grounded_concise_v1`.

## 6. Before/After Targeted Comparison

Comparison reference: T105B `CC-DFlash-R2` Light GPU outputs for the same six fixture IDs.

| Metric | Result |
| --- | ---: |
| Target rows | 6 |
| Proxy-improved rows | 0 |
| Unchanged/no-improvement rows | 4 |
| Safer-but-uninformative rows | 2 |
| Proxy-regressed rows | 0 |
| Average reference recall delta | +0.016819 |

Row outcomes:

| Fixture ID | Outcome | Recall delta |
| --- | --- | ---: |
| `qmsum_meeting_qa_test_0001` | unchanged_or_no_improvement | +0.040816 |
| `qmsum_meeting_qa_test_0036` | unchanged_or_no_improvement | +0.050000 |
| `qmsum_meeting_qa_test_0094` | unchanged_or_no_improvement | -0.045455 |
| `qmsum_meeting_qa_test_0055` | safer_but_uninformative | 0.000000 |
| `qmsum_meeting_qa_test_0070` | unchanged_or_no_improvement | +0.055555 |
| `qmsum_meeting_qa_test_0078` | safer_but_uninformative | 0.000000 |

The policy made some outputs more cautious, but the deterministic proxy did not show a clear repair. Two outputs moved into an insufficient-evidence/refusal style, which is safer but less informative and cannot be counted as semantic improvement.

## 7. Output-shape And Runtime Impact

| Metric | T108B |
| --- | ---: |
| Rows completed | 6 |
| Empty/malformed | 0 |
| Cap-limited/incomplete | 0 |
| Refusal/insufficient-evidence | 2 |
| Avg e2e time | 3.520058s |
| Avg generation time | 3.394266s |
| Avg `T_compress_ms` | 125.792571 |
| Avg `R_actual` | 2.162981 |
| Max reserved VRAM | 5.076172 GiB |
| OOM/CUDA failure flags | none |

The targeted repair did not cause a runtime or output-shape failure. It also did not provide enough deterministic proxy improvement to claim QMSum quality repair.

## 8. Residual-risk Impact

Decision: `MIXED_WITH_CAVEAT`

Interpretation: `mixed_targeted_repair_signal`

The repair attempt does not eliminate QMSum residual risk. It also does not prove that the repair generalizes beyond the six target rows. The result is useful because it shows that a stricter evidence-grounded policy can make some outputs safer, but in this run that safety mostly appears as non-answer/refusal behavior rather than corrected evidence-grounded answers.

## 9. T108C Validation Recommendation

T108C is justified, but it should be framed as validation/limitation closure rather than expansion.

Recommended next task:

`T108C — QMSum Targeted Repair Validation`

T108C should decide whether the mixed T108B signal is worth preserving as a scoped repair candidate or whether QMSum should close with a final limitation decision. It should not run QMSum n100, a full matrix, unrelated reference conditions, human scoring, or LLM judge unless explicitly approved.

## 10. Claim Update

Allowed:

- T108B attempted a targeted QMSum evidence-grounded repair.
- The repair produced `0/6` deterministic proxy-improved rows and `2/6` safer-but-uninformative rows.
- The run completed `6/6` target rows with metadata-confirmed light/cuda policy override and no recorded OOM/CUDA failure.
- QMSum semantic correctness still requires validation before being claimed.

Blocked:

- QMSum semantic correctness is proven.
- QMSum residual risk is eliminated.
- CC-DFlash wins QMSum.
- The repair generalizes to all QMSum rows.
- Default switch is authorized.
- Phase 2 is closed.

## 11. Roadmap Update

T108B should be marked `MIXED_WITH_CAVEAT`. T108C becomes the current next task. Phase 2 closure packaging moves to T110 or later and remains blocked until the targeted repair branch closes.

## 12. Scope Confirmation

No QMSum n100, full matrix, Baseline-AR, DFlash-R1, Large CPU, LLMLingua-AR-R2, GSM8K, keep-rate tuning, query-aware compression, default switch, human scoring, LLM judge, model download, or dataset download was run.
