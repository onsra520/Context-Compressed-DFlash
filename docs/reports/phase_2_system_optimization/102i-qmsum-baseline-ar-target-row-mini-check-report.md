# Task102I - QMSum Baseline-AR Target-row Mini-check

## 1. Purpose

Task102I ran a small Baseline-AR mini-check on the same six QMSum residual-risk target rows used in Task102G and reassessed in Task102H.

The purpose was to distinguish whether the persistent QMSum residual failures are more consistent with local target-model / QMSum evidence-grounding difficulty and deterministic proxy/reference limitations, or whether they look specific to the compressed CC-DFlash Light GPU path.

This task ran only the six target rows. It did not run QMSum `n=100`, a full matrix, DFlash-R1, Large CPU, GSM8K, CC-DFlash again, an LLM judge, human semantic scoring, keep-rate tuning, a default config switch, or model/dataset download.

## 2. Inputs

Target dataset:

- `data/eval/qmsum_meeting_qa_target_rows_task102f.jsonl`

Frozen fixture IDs:

- `qmsum_meeting_qa_test_0036`
- `qmsum_meeting_qa_test_0070`
- `qmsum_meeting_qa_test_0055`
- `qmsum_meeting_qa_test_0078`
- `qmsum_meeting_qa_test_0094`
- `qmsum_meeting_qa_test_0001`

Reference artifacts:

- Original Task102 CC-DFlash Light GPU QMSum run: `results/phase_2_system_optimization/final_reruns/task102_qmsum_light_gpu_n30_feasibility_run/runs/20260622_151200_cc_dflash_r2_light_gpu_qmsum_seed42_n30_mnt384.jsonl`
- Task102G remediated CC-DFlash Light GPU target-row run: `results/phase_2_system_optimization/final_reruns/task102g_qmsum_target_row_remediation_rerun/runs/20260622_235012_cc_dflash_r2_light_gpu_qmsum_target_rows_n6_mnt384.jsonl`
- Task102H before/after reassessment: `results/phase_2_system_optimization/final_reruns/task102h_qmsum_remediation_reassessment/task102h_before_after_row_assessment.jsonl`

## 3. Setup

Run configuration:

- condition: `Baseline-AR`
- dataset: `qmsum_meeting_qa_long`
- dataset path: `data/eval/qmsum_meeting_qa_target_rows_task102f.jsonl`
- seed: `42`
- n: `6`
- warmup prompts: `0`
- max new tokens: `384`
- generated text stored: yes
- resume enabled: yes
- compression: none
- DFlash / CC-DFlash / draft model: not used

Policy:

- name: `qmsum_targeted_evidence_repair_v1`
- suffix: `Answer the question using only evidence from the meeting context. Be specific: include the relevant people, actions, decisions, or reasons when they are present. Avoid generic answers such as 'not discussed' unless the context clearly lacks the requested evidence. Keep the answer concise but complete in 2-5 sentences.`

## 4. Runtime Policy Hook

Task102G added the runtime-only QMSum policy flags:

- `--qmsum-policy-name`
- `--qmsum-policy-suffix`

Task102I tightened the prompt-selection path so the override is applied to the selected QMSum prompt text even for uncompressed Baseline-AR runs. Default behavior remains unchanged when the override is not supplied.

The dry-run prompt check confirmed the selected six prompts used the targeted suffix. The result metadata confirmed:

- `qmsum_policy_suffix_override=true`
- `qmsum_answer_policy_type=qmsum_targeted_evidence_repair_v1`
- `qmsum_answer_policy_preserved=true`

## 5. Run Artifact

Run artifact:

- `results/phase_2_system_optimization/final_reruns/task102i_qmsum_baseline_ar_target_row_mini_check/runs/20260623_003802_baseline_ar_qmsum_target_rows_n6_mnt384.jsonl`

Row count:

- `6/6`

Analyzer artifacts:

- `results/phase_2_system_optimization/final_reruns/task102i_qmsum_baseline_ar_target_row_mini_check/summary/task102i_baseline_ar_mini_check_summary.json`
- `results/phase_2_system_optimization/final_reruns/task102i_qmsum_baseline_ar_target_row_mini_check/summary/task102i_baseline_vs_cc_row_assessment.jsonl`
- `results/phase_2_system_optimization/final_reruns/task102i_qmsum_baseline_ar_target_row_mini_check/summary/task102i_baseline_ar_row_labels.jsonl`
- `results/phase_2_system_optimization/final_reruns/task102i_qmsum_baseline_ar_target_row_mini_check/summary/task102i_claim_interpretation.json`
- `results/phase_2_system_optimization/final_reruns/task102i_qmsum_baseline_ar_target_row_mini_check/summary/task102i_next_task_decision.json`
- `results/phase_2_system_optimization/final_reruns/task102i_qmsum_baseline_ar_target_row_mini_check/tables/task102i_baseline_vs_cc_table.csv`

## 6. Metadata / Runtime Audit

Result audit:

- row count: `6`
- fixture ID set matched the six Task102F target rows
- condition metadata: `Baseline-AR`
- compression metadata: `none`
- draft used: `false`
- targeted QMSum policy override: confirmed
- empty or malformed outputs: `0`
- OOM/CUDA failure flags: none recorded

Runtime metrics:

| Metric | Value |
| --- | ---: |
| average generation time | `3.365837s` |
| min generation time | `2.841078s` |
| max generation time | `3.930561s` |
| average tok/s | `25.647104` |
| min tok/s | `23.934573` |
| max tok/s | `27.108084` |
| average output tokens | `86.666667` |
| max VRAM allocated | `2.492005GiB` |
| max VRAM reserved | `3.681641GiB` |

## 7. Baseline vs CC-DFlash Row Comparison

Deterministic row categories:

| Category | Count |
| --- | ---: |
| `baseline_also_fails_or_uncertain` | `5/6` |
| `proxy_or_reference_limitation_persists` | `1/6` |
| `baseline_clearly_better_but_not_resolved` | `0/6` |
| `baseline_resolves_proxy_supported` | `0/6` |
| `compression_path_specific_risk` | `0/6` |

Six-row summary:

| Fixture ID | Category | Notes |
| --- | --- | --- |
| `qmsum_meeting_qa_test_0036` | `proxy_or_reference_limitation_persists` | Baseline-AR improved some grounding/focus signal but did not reach deterministic resolution. |
| `qmsum_meeting_qa_test_0070` | `baseline_also_fails_or_uncertain` | Baseline-AR remained weak against the reference answer, similar to CC-DFlash. |
| `qmsum_meeting_qa_test_0055` | `baseline_also_fails_or_uncertain` | Baseline-AR also produced a generic/not-discussed style answer. |
| `qmsum_meeting_qa_test_0078` | `baseline_also_fails_or_uncertain` | Baseline-AR also stated spectral subtraction was not discussed. |
| `qmsum_meeting_qa_test_0094` | `baseline_also_fails_or_uncertain` | Baseline-AR stayed low-overlap against the storage-space reference. |
| `qmsum_meeting_qa_test_0001` | `baseline_also_fails_or_uncertain` | Baseline-AR did not improve over the remediated CC-DFlash answer by deterministic proxy. |

## 8. Interpretation

Interpretation:

- `TARGET_MODEL_OR_QMSUM_GROUNDING_LIMITATION_SUPPORTED`

Meaning:

- Baseline-AR also fails or remains uncertain on most target rows.
- The residual QMSum failures are therefore consistent with local target-model evidence locating / grounding limitations and/or QMSum source-reference/proxy limitations.
- This mini-check does not support a strong claim that the six residual failures are compression-path-specific to CC-DFlash.

This is still deterministic proxy evidence only. It does not prove semantic correctness and does not prove the exact causal source of each failure.

## 9. Claim Impact

Allowed wording:

- "Baseline-AR was checked on the same six QMSum residual-risk target rows with the same targeted policy."
- "The mini-check is consistent with residual QMSum risk being at least partly target-model/QMSum-grounding or proxy/reference-limitation driven, not solely compression-path-specific."
- "QMSum remains benchmark-scoped deterministic proxy/risk evidence."

Blocked wording:

- "QMSum semantic correctness is proven."
- "Baseline-AR mini-check completes the full matrix."
- "Residual QMSum risk is conclusively caused by one factor."
- "CC-DFlash compression has no QMSum quality risk."

## 10. Decision

Decision: **PASS_WITH_CAVEAT**.

Rationale:

- exactly six target rows ran
- target dataset validation passed
- metadata confirmed Baseline-AR, no compression, and the targeted policy override
- no empty/malformed output, OOM flag, or CUDA failure was recorded
- deterministic comparison supports a bounded target-model/QMSum-grounding or proxy-limitation interpretation
- no semantic judge or human semantic scoring was used

## 11. Next Task

Next task: **T102J - QMSum Residual Risk Stop-or-Judge Decision**.

Recommended path:

- accept the residual QMSum caveat and unblock T103 if the user agrees

Reason:

- Baseline-AR also fails or remains uncertain on most target rows, which supports carrying the residual caveat rather than escalating by default to a larger runtime matrix.

## 12. Scope Confirmation

Task102I did not run:

- QMSum `n=100`
- full matrix
- DFlash-R1
- Large CPU
- GSM8K
- CC-DFlash again
- LLM judge
- human semantic scoring
- keep-rate tuning
- default config switch
- model or dataset download

Task102I makes no QMSum semantic-correctness claim.
