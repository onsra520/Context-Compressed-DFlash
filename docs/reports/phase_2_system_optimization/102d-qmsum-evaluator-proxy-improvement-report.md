# Task102D — QMSum Evaluator/Proxy Improvement Attempt

## 1. Purpose

Task102D attempts to improve the deterministic QMSum evaluator/proxy after Task102C found a high proxy-uncertainty rate.

This task is analysis/evaluator-only. It reused existing Task102, Task102B, and Task102C artifacts. It ran no benchmark, model inference, GPU job, QMSum rerun, QMSum `n=100`, full matrix, LLM judge, keep-rate tuning, default runtime/config switch, model download, or cache/model mutation.

## 2. Inputs

Primary inputs:

- Task102 QMSum `n=30` artifact: `results/phase_2_system_optimization/final_reruns/task102_qmsum_light_gpu_n30_feasibility_run/runs/20260622_151200_cc_dflash_r2_light_gpu_qmsum_seed42_n30_mnt384.jsonl`
- Task102B row labels: `results/phase_2_system_optimization/final_reruns/task102b_qmsum_output_semantic_risk_analysis/task102b_qmsum_row_labels.jsonl`
- Task102C uncertainty triage: `results/phase_2_system_optimization/final_reruns/task102c_qmsum_proxy_uncertainty_triage/task102c_uncertain_row_triage.jsonl`

Output folder:

- `results/phase_2_system_optimization/final_reruns/task102d_qmsum_evaluator_proxy_improvement/`

## 3. Improved Proxy Method

Task102D keeps the deterministic-only boundary but improves the proxy by separating multiple signals:

- normalized content-term reference overlap after case, punctuation, stopword, and simple suffix normalization
- source-grounding overlap from available prompt/source previews
- question-focus overlap
- entity/number reference overlap
- output length and genericness

The reassessment creates confidence bands:

- `strong_proxy_support`
- `moderate_proxy_support`
- `source_grounded_reference_mismatch`
- `generic_or_under_specific`
- `hard_quality_risk`
- `unresolved_deterministic_limitation`

Rows marked `source_grounded_reference_mismatch` are not treated as semantically correct. They are only better explained as deterministic reference/proxy limitations rather than unexplained failures.

## 4. Before / After Comparison

Task102B and Task102C baseline:

- proxy-uncertain / low-overlap rows before: `18/30`
- Task102C hard-risk rows: `3/30`
- Task102C unresolved deterministic-proxy limitations: `4/18`
- Task102C claim status: `SCOPED_WITH_TRIAGED_RISK`

Task102D result:

| Metric | Count |
| --- | ---: |
| Rows reassessed | `18` |
| Remaining unexplained deterministic uncertainty | `3` |
| Explained proxy/reference limitation rows | `10` |
| Reduced uncertainty rows with stronger proxy support | `2` |
| Hard-risk rows | `3` |

Confidence-band counts:

| Band | Count |
| --- | ---: |
| `source_grounded_reference_mismatch` | `10` |
| `strong_proxy_support` | `1` |
| `moderate_proxy_support` | `1` |
| `hard_quality_risk` | `2` |
| `generic_or_under_specific` | `1` |
| `unresolved_deterministic_limitation` | `3` |

Unexplained uncertainty is reduced from `18/30` to `3/30`, an absolute reduction of `15` rows. Hard-risk rows remain `3/30`, so the improvement does not hide the existing quality-risk bucket.

## 5. Interpretation

Task102D materially improves the deterministic explanation of QMSum proxy uncertainty:

- Most uncertain rows are now better described as source-grounded/reference-mismatch cases.
- Two rows gain stronger deterministic proxy support.
- Three rows remain unexplained deterministic limitations.
- Three rows remain hard-risk rows.

This improves the claim from broad `SCOPED_WITH_TRIAGED_RISK` to `SCOPED_WITH_IMPROVED_PROXY_CAVEAT`.

However, this is still not semantic correctness proof. The improved proxy is deterministic, lexical/evidence-oriented, and limited by available previews and reference wording.

## 6. Claim Update

Claim update artifact:

- `results/phase_2_system_optimization/final_reruns/task102d_qmsum_evaluator_proxy_improvement/task102d_claim_update.json`

QMSum status:

- `SCOPED_WITH_IMPROVED_PROXY_CAVEAT`

Allowed wording:

- "QMSum Light GPU n30 now has an improved deterministic proxy reassessment that separates reference overlap, source grounding, output genericness, and remaining unresolved proxy limits."
- "The reassessment supports benchmark-scoped QMSum proxy-risk reporting, not semantic correctness proof."

Blocked wording:

- "QMSum semantic correctness is proven."
- "The improved proxy is equivalent to human semantic scoring."
- "QMSum quality is fully solved."
- "A QMSum n100 or full matrix result was run."

## 7. Decision

Decision: **PASS_WITH_CAVEAT**.

Reason:

- The evaluator materially reduced unexplained uncertainty from `18/30` to `3/30`.
- Hard-risk rows remain bounded at `3/30` and were not relabeled as acceptable.
- No semantic correctness claim is made.
- No benchmark/model run was performed.

## 8. Next Task

Next task: **T103 — Reference Alignment for Speed Claim**.

T102E is not needed by the Task102D decision rule because uncertainty is no longer near `18/30`, unresolved rows are reduced to `3`, and hard-risk rows did not increase materially.

## 9. Scope Confirmation

Task102D did not run:

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

Task102D makes no QMSum semantic-correctness claim.
