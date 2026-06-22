# Task102F — QMSum Target-row Remediation Decision

## 1. Purpose

Task102F chooses the remediation path for the residual QMSum quality-risk rows found by Task102E.

This task is planning/audit/preparation only. It ran no benchmark, model inference, GPU job, QMSum rerun, QMSum `n=100`, full matrix, LLM judge, human semantic scoring, keep-rate tuning run, default runtime/config switch, model download, or cache/model mutation.

## 2. Inputs

Primary inputs:

- Task102 QMSum `n=30` artifact: `results/phase_2_system_optimization/final_reruns/task102_qmsum_light_gpu_n30_feasibility_run/runs/20260622_151200_cc_dflash_r2_light_gpu_qmsum_seed42_n30_mnt384.jsonl`
- Task102B semantic-risk/proxy artifacts: `results/phase_2_system_optimization/final_reruns/task102b_qmsum_output_semantic_risk_analysis/`
- Task102D proxy-improvement artifacts: `results/phase_2_system_optimization/final_reruns/task102d_qmsum_evaluator_proxy_improvement/`
- Task102E residual-risk artifacts: `results/phase_2_system_optimization/final_reruns/task102e_qmsum_hard_risk_and_residual_uncertainty_resolution/`
- Original QMSum evaluation dataset: `data/eval/qmsum_meeting_qa_100.jsonl`

Task102E left:

- unexplained deterministic uncertainty: `3/30`
- hard-risk rows: `3/30`
- confirmed quality failures: `3`
- still-unresolved rows: `3`

## 3. Decision

Decision: **PASS**.

Selected remediation direction: **Option B — target-row remediation rerun**.

Task102F does not run the remediation. It freezes the six target rows, creates a clean target-only dataset, defines the remediation policy, and prepares T102G.

## 4. Target Rows

| Fixture ID | Category | Task102E final resolution |
| --- | --- | --- |
| `qmsum_meeting_qa_test_0036` | unresolved without semantic judge | `still_unresolved_without_semantic_judge` |
| `qmsum_meeting_qa_test_0070` | confirmed evidence miss | `confirmed_evidence_miss` |
| `qmsum_meeting_qa_test_0055` | confirmed generic or under-specific | `confirmed_generic_or_under_specific` |
| `qmsum_meeting_qa_test_0078` | confirmed evidence miss | `confirmed_evidence_miss` |
| `qmsum_meeting_qa_test_0094` | unresolved without semantic judge | `still_unresolved_without_semantic_judge` |
| `qmsum_meeting_qa_test_0001` | unresolved without semantic judge | `still_unresolved_without_semantic_judge` |

Frozen target-row artifact:

- `results/phase_2_system_optimization/final_reruns/task102f_qmsum_target_row_remediation_decision/task102f_target_rows.json`

## 5. Remediation Policy

Policy name:

- `qmsum_targeted_evidence_repair_v1`

Prompt suffix selected for the remediation plan:

> Answer the question using only evidence from the meeting context. Be specific: include the relevant people, actions, decisions, or reasons when they are present. Avoid generic answers such as 'not discussed' unless the context clearly lacks the requested evidence. Keep the answer concise but complete in 2-5 sentences.

Policy requirements:

- answer the specific question directly
- use only meeting-context evidence
- include specific entities, actions, decisions, or reasons when available
- avoid generic `not discussed` unless the context clearly lacks evidence
- prefer complete answers over overly short answers
- avoid unsupported information
- if evidence is ambiguous, state the most supported answer and avoid overgeneralizing

Runner support note:

- `scripts/run_mvp.py` supports `--dataset-path`, but it does not currently expose a custom QMSum policy suffix flag.
- T102G should confirm or add a runtime-only policy override if the exact `qmsum_targeted_evidence_repair_v1` suffix must be applied.
- Without that hook, a target-only rerun would reuse the existing evidence-focused QMSum suffix.

## 6. Max New Tokens Decision

Selected `max_new_tokens`: **384**.

Rationale:

- Task102B found cap-limited/incomplete rows at `0/30`.
- The residual Task102E rows are evidence-targeting, genericness, or unresolved semantic-risk cases, not cap/tail-pressure cases.
- `384` preserves comparability with the canonical Task102 QMSum run.
- `512` is deferred unless T102G/T102H finds target-row truncation or new tail pressure.

## 7. Target Dataset / Filter Decision

Runner inspection found:

- no fixture-id filter exposed in `scripts/run_mvp.py`
- `--dataset-path` is supported

Therefore Task102F created a static target-only dataset:

- `data/eval/qmsum_meeting_qa_target_rows_task102f.jsonl`

Dataset manifest:

- `results/phase_2_system_optimization/final_reruns/task102f_qmsum_target_row_remediation_decision/task102f_target_dataset_manifest.json`

Leakage guard:

- only original QMSum source/question/reference rows were copied
- no Task102 generated outputs were copied into prompt inputs
- no `generated_text` field exists in the target dataset

## 8. T102G Run Plan

Prepared T102G scope:

- task: `T102G — QMSum Target-row Remediation Rerun`
- condition: `CC-DFlash-R2`
- dataset: `qmsum_meeting_qa_long`
- dataset path: `data/eval/qmsum_meeting_qa_target_rows_task102f.jsonl`
- compressor profile: `light`
- compressor device map: `cuda`
- seed: `42`
- n: `6`
- max_new_tokens: `384`
- target rows only
- no QMSum `n=100`
- no full matrix

Command template is stored in:

- `results/phase_2_system_optimization/final_reruns/task102f_qmsum_target_row_remediation_decision/task102f_rerun_plan.json`

Stop conditions:

- CUDA unavailable before run
- OOM/CUDA failure
- runner selects more than six target rows
- target dataset contains prior generated output as prompt input
- generated artifact is malformed or row count differs from `6`

## 9. Claim Status

QMSum remains:

- `SCOPED_WITH_CONFIRMED_FAILURES`

Blocked:

- QMSum semantic correctness is proven.
- QMSum quality risk has been eliminated.
- T103 speed-claim closure can proceed without acknowledging residual QMSum risk.
- DFlash-R1 is broken.

T103 remains blocked by default until T102G/T102H complete or the user explicitly accepts carrying the residual QMSum caveat.

## 10. Next Task

Next task: **T102G — QMSum Target-row Remediation Rerun**.

T102H is planned after T102G to analyze the target-row rerun and decide whether QMSum can move from confirmed residual risk to a remediated/scoped claim.

T102A remains conditional only if rerun infrastructure fails.

## 11. Artifacts

- `results/phase_2_system_optimization/final_reruns/task102f_qmsum_target_row_remediation_decision/task102f_target_rows.json`
- `results/phase_2_system_optimization/final_reruns/task102f_qmsum_target_row_remediation_decision/task102f_remediation_policy.json`
- `results/phase_2_system_optimization/final_reruns/task102f_qmsum_target_row_remediation_decision/task102f_rerun_plan.json`
- `results/phase_2_system_optimization/final_reruns/task102f_qmsum_target_row_remediation_decision/task102f_target_dataset_plan.json`
- `results/phase_2_system_optimization/final_reruns/task102f_qmsum_target_row_remediation_decision/task102f_claim_status_update.json`
- `results/phase_2_system_optimization/final_reruns/task102f_qmsum_target_row_remediation_decision/task102f_next_task_decision.json`
- `results/phase_2_system_optimization/final_reruns/task102f_qmsum_target_row_remediation_decision/task102f_target_dataset_manifest.json`
- `data/eval/qmsum_meeting_qa_target_rows_task102f.jsonl`

## 12. Scope Confirmation

Task102F did not run:

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

Task102F makes no QMSum semantic-correctness claim.
