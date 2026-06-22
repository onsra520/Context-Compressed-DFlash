# Task102E — QMSum Hard-risk and Residual Uncertainty Resolution

## 1. Purpose

Task102E deeply inspects the remaining QMSum rows that Task102D still marked as hard-risk or unresolved. The goal was to reduce the residual quality-risk bucket to zero if deterministic evidence supported doing so.

This task is analysis/evaluator/reporting only. It reused existing Task102, Task102B, Task102C, and Task102D artifacts. It ran no benchmark, model inference, GPU job, QMSum rerun, QMSum `n=100`, full matrix, LLM judge, human semantic scoring, keep-rate tuning, default runtime/config switch, model download, or cache/model mutation.

## 2. Inputs

Primary inputs:

- Task102 QMSum `n=30` artifact: `results/phase_2_system_optimization/final_reruns/task102_qmsum_light_gpu_n30_feasibility_run/runs/20260622_151200_cc_dflash_r2_light_gpu_qmsum_seed42_n30_mnt384.jsonl`
- Task102B artifacts: `results/phase_2_system_optimization/final_reruns/task102b_qmsum_output_semantic_risk_analysis/`
- Task102C artifacts: `results/phase_2_system_optimization/final_reruns/task102c_qmsum_proxy_uncertainty_triage/`
- Task102D artifacts: `results/phase_2_system_optimization/final_reruns/task102d_qmsum_evaluator_proxy_improvement/`

Output folder:

- `results/phase_2_system_optimization/final_reruns/task102e_qmsum_hard_risk_and_residual_uncertainty_resolution/`

## 3. Target Rows

Task102E inspected every row from Task102D whose improved confidence band or outcome was one of:

- `hard_quality_risk`
- `generic_or_under_specific`
- `unresolved_deterministic_limitation`
- `hard_risk`
- `remaining_unexplained_uncertain`

This produced six target rows:

| Row | Prior Task102D band | Final Task102E resolution | Final status |
| --- | --- | --- | --- |
| `qmsum_meeting_qa_test_0036` | `unresolved_deterministic_limitation` | `still_unresolved_without_semantic_judge` | `still_unresolved` |
| `qmsum_meeting_qa_test_0070` | `hard_quality_risk` | `confirmed_evidence_miss` | `confirmed_quality_failure` |
| `qmsum_meeting_qa_test_0055` | `generic_or_under_specific` | `confirmed_generic_or_under_specific` | `confirmed_quality_failure` |
| `qmsum_meeting_qa_test_0078` | `hard_quality_risk` | `confirmed_evidence_miss` | `confirmed_quality_failure` |
| `qmsum_meeting_qa_test_0094` | `unresolved_deterministic_limitation` | `still_unresolved_without_semantic_judge` | `still_unresolved` |
| `qmsum_meeting_qa_test_0001` | `unresolved_deterministic_limitation` | `still_unresolved_without_semantic_judge` | `still_unresolved` |

## 4. Method

For each target row, Task102E recorded:

- row id
- prior Task102B/Task102C/Task102D labels
- question
- reference-answer preview
- generated output
- source/prompt preview when available
- reference overlap
- source-grounding overlap
- question-focus overlap
- entity/number overlap
- output length / genericness signal

Task102E used only deterministic text/proxy evidence. A row was resolved only when the deterministic signals supported the new label. Fluent text was not sufficient for acceptance.

## 5. Before / After Counts

| Metric | Before T102E | After T102E |
| --- | ---: | ---: |
| Unexplained deterministic uncertainty | `3/30` | `3/30` |
| Hard-risk rows | `3/30` | `3/30` |
| Resolved rows | n/a | `0` |
| Confirmed quality-failure rows | n/a | `3` |
| Still unresolved rows | n/a | `3` |

Resolution counts:

- `confirmed_evidence_miss`: `2`
- `confirmed_generic_or_under_specific`: `1`
- `still_unresolved_without_semantic_judge`: `3`

## 6. Interpretation

Task102E could not honestly reduce the residual QMSum quality-risk bucket to zero.

Confirmed quality failures:

- `qmsum_meeting_qa_test_0070`: evidence-miss risk remains supported by weak reference/source signals.
- `qmsum_meeting_qa_test_0078`: evidence-miss risk remains supported; the generated answer is off the requested spectral-subtraction evidence.
- `qmsum_meeting_qa_test_0055`: the output states the information is not discussed despite a specific reference answer, so the row remains generic/under-specific.

Still unresolved without semantic judge:

- `qmsum_meeting_qa_test_0036`
- `qmsum_meeting_qa_test_0094`
- `qmsum_meeting_qa_test_0001`

These rows have mixed deterministic signals. Resolving them further would require human semantic review, an LLM judge, or another explicit remediation path.

## 7. Claim Update

Claim update artifact:

- `results/phase_2_system_optimization/final_reruns/task102e_qmsum_hard_risk_and_residual_uncertainty_resolution/task102e_claim_update.json`

QMSum claim status:

- `SCOPED_WITH_CONFIRMED_FAILURES`

Allowed wording:

- "QMSum Light GPU n30 has deterministic proxy/evidence analysis through residual hard-risk resolution."
- "Remaining QMSum quality concerns are explicitly bounded by confirmed failure and unresolved rows."

Blocked wording:

- "QMSum semantic correctness is proven."
- "QMSum quality risk has been eliminated."
- "T103 speed-claim closure can proceed without acknowledging QMSum residual quality risk."

## 8. Decision

Decision: **NEEDS_REMEDIATION_TASK**.

Reason:

- unexplained deterministic uncertainty remains `3/30`
- hard-risk remains `3/30`
- confirmed quality failures remain `3/30`
- still-unresolved rows remain `3/30`

Task102E therefore does not authorize T103 by default.

## 9. Next Task

Recommended next task: **T102F — QMSum Target-row Remediation Decision**.

Recommended options:

- prompt/evidence policy improvement
- small controlled rerun on only target rows
- human review
- LLM judge
- keep caveat and stop QMSum quality expansion

T103 should wait unless the user explicitly accepts carrying the residual QMSum quality caveat into speed-reference alignment.

## 10. Scope Confirmation

Task102E did not run:

- benchmark execution
- model inference
- GPU job
- QMSum rerun
- QMSum `n=100`
- full matrix
- LLM judge
- human semantic scoring
- keep-rate tuning
- default runtime/config switch
- model or dataset download

Task102E makes no QMSum semantic-correctness claim.
