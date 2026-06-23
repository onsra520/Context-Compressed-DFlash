# Task103A - QMSum Evidence Selector before Answer

## 1. Purpose

Task103A starts the QMSum Deep Audit & Deep Fix track by testing whether the six residual QMSum target-row failures improve when the model receives deterministic, question-focused evidence snippets before answering.

The key question was:

- Can QMSum residual failures be reduced if the model receives selected evidence snippets instead of the full meeting context?

Task103A is a bounded six-row mini-check. It does not prove semantic correctness.

## 2. Why T103 Replaces Speed Alignment

After Task102H and Task102I, QMSum residual risk remained too important to ignore:

- Task102H targeted remediation resolved `0/6` rows.
- Task102H left `3` hard-risk rows and `2` unresolved rows.
- Task102I found Baseline-AR also failed or remained uncertain on `5/6` target rows.
- Task102I supported the interpretation that residual QMSum failures are consistent with target-model/QMSum grounding or proxy/reference limitations, not solely CC-DFlash compression.

Therefore T103 is redirected from speed-reference alignment into:

- T103 - QMSum Deep Audit & Deep Fix
- T103A - Evidence Retrieval / Evidence Selector before Answer
- T103B - Query-aware Compression
- T103C - Semantic Judge / Human Review Protocol
- T103D - QMSum Deep Fix Closure Decision

Speed-reference alignment moves to T104.

## 3. Selector Method

Selector script:

- `scripts/phase_2_system_optimization/analysis/task103a_qmsum_evidence_selector.py`

The selector:

- reads only the Task102F six-row target dataset
- splits meeting context into speaker/utterance-like windows
- scores windows by question keywords, speaker/person names, numbers, action terms, and content overlap
- selects top-ranked snippets under a bounded character budget
- writes selected evidence and selection rationale
- creates a target-only evidence-selected dataset

Evidence-selected dataset:

- `data/eval/qmsum_meeting_qa_target_rows_task103a_evidence_selected.jsonl`

Selector artifacts:

- `results/phase_2_system_optimization/final_reruns/task103a_qmsum_evidence_selector_before_answer/summary/task103a_selector_summary.json`
- `results/phase_2_system_optimization/final_reruns/task103a_qmsum_evidence_selector_before_answer/summary/task103a_selected_evidence.jsonl`

## 4. Leakage Guard

The selector does not use:

- reference answer text for retrieval
- previous Task102 generated answers
- Task102G generated answers
- Task102I generated answers
- LLM or human semantic scoring

Dataset validation confirmed:

- row count: `6`
- fixture IDs matched the six Task102F target rows
- no generated-output leakage fields were present
- selector metadata records `reference_used_for_retrieval=false`
- selector metadata records `prior_generated_outputs_used=false`

## 5. Runs and Artifacts

Baseline-AR evidence-selected run:

- `results/phase_2_system_optimization/final_reruns/task103a_qmsum_evidence_selector_before_answer/runs/20260623_120446_baseline_ar_qmsum_evidence_selected_n6_mnt384.jsonl`

CC-DFlash-R2 Light GPU evidence-selected run:

- `results/phase_2_system_optimization/final_reruns/task103a_qmsum_evidence_selector_before_answer/runs/20260623_120542_cc_dflash_r2_light_gpu_qmsum_evidence_selected_n6_mnt384.jsonl`

Analyzer script:

- `scripts/phase_2_system_optimization/analysis/task103a_qmsum_evidence_selector_before_answer.py`

Analyzer artifacts:

- `results/phase_2_system_optimization/final_reruns/task103a_qmsum_evidence_selector_before_answer/summary/task103a_run_metadata_audit.json`
- `results/phase_2_system_optimization/final_reruns/task103a_qmsum_evidence_selector_before_answer/summary/task103a_before_after_assessment.jsonl`
- `results/phase_2_system_optimization/final_reruns/task103a_qmsum_evidence_selector_before_answer/summary/task103a_claim_update.json`
- `results/phase_2_system_optimization/final_reruns/task103a_qmsum_evidence_selector_before_answer/summary/task103a_next_task_decision.json`
- `results/phase_2_system_optimization/final_reruns/task103a_qmsum_evidence_selector_before_answer/tables/task103a_evidence_selector_comparison.csv`

Runtime metadata audit:

| Run | Rows | Avg generation time | Avg tok/s | Avg `t_compress_ms` | Max reserved VRAM |
| --- | ---: | ---: | ---: | ---: | ---: |
| Baseline-AR evidence selected | `6/6` | `2.427376s` | `29.282540` | n/a | `3.023438GiB` |
| CC-DFlash-R2 Light GPU evidence selected | `6/6` | `3.481639s` | `22.602312` | `58.043429ms` | `4.646484GiB` |

Both runs completed without empty/malformed outputs or recorded OOM/CUDA failure flags.

## 6. Evidence-selected vs Previous Outputs

Deterministic row outcome counts:

| Path | Resolved | Improved | Unchanged | Worsened |
| --- | ---: | ---: | ---: | ---: |
| Baseline-AR evidence selected vs Baseline-AR full-context target rows | `0/6` | `0/6` | `4/6` | `2/6` |
| CC-DFlash-R2 evidence selected vs Task102G remediated CC-DFlash target rows | `0/6` | `1/6` | `3/6` | `2/6` |

Row-level summary:

| Fixture ID | Baseline evidence-selected outcome | CC-DFlash evidence-selected outcome |
| --- | --- | --- |
| `qmsum_meeting_qa_test_0036` | `unchanged` | `improved` |
| `qmsum_meeting_qa_test_0070` | `worsened` | `worsened` |
| `qmsum_meeting_qa_test_0055` | `unchanged` | `unchanged` |
| `qmsum_meeting_qa_test_0078` | `unchanged` | `unchanged` |
| `qmsum_meeting_qa_test_0094` | `worsened` | `unchanged` |
| `qmsum_meeting_qa_test_0001` | `unchanged` | `worsened` |

## 7. Interpretation

Interpretation:

- `GENERATION_OR_SEMANTIC_LIMITATION_REMAINS`

Evidence-selected Baseline-AR did not materially improve the six residual rows. Evidence-selected CC-DFlash-R2 improved only one row and worsened two under the deterministic proxy.

This supports the bounded conclusion that deterministic lexical evidence selection alone is not enough to close the QMSum residual-risk bucket. It does not prove the model is semantically wrong; it shows that the current deterministic selector plus deterministic proxy did not produce a reliable repair.

## 8. Claim Update

Claim status:

- `EVIDENCE_SELECTION_MINI_CHECK_COMPLETE`

Allowed wording:

- "Task103A tested deterministic question-focused evidence selection on the six residual QMSum rows."
- "Task103A supports bounded discussion of whether selected evidence helps target-model grounding."

Blocked wording:

- "QMSum semantic correctness is proven."
- "Evidence selection proves the root cause of QMSum residual failures."
- "The full QMSum matrix is complete."
- "Query-aware compression is validated by Task103A."

Remaining limitations:

- only six target rows were run
- evidence selection used deterministic lexical heuristics, not semantic retrieval
- no LLM judge or human semantic scoring was used
- QMSum remains benchmark-scoped risk/proxy evidence only

## 9. Next Task

Next task:

- **T103C - Semantic Judge / Human Review Protocol**

Reason:

- Evidence selection did not materially improve deterministic proxy outcomes.
- T103B remains a possible future query-aware-compression experiment, but Task103A does not justify it as the default next step.

## 10. Scope Confirmation

Task103A did not run:

- QMSum `n=100`
- full matrix
- DFlash-R1
- Large CPU
- GSM8K
- keep-rate tuning
- default config switch
- model or dataset download
- LLM judge
- human semantic scoring

Task103A ran only:

- one Baseline-AR six-row evidence-selected mini-check
- one CC-DFlash-R2 Light GPU six-row evidence-selected mini-check
