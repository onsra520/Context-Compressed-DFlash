# Task105B — QMSum Controlled Runtime Matrix

## 1. Purpose

Task105B runs the controlled QMSum runtime/reference matrix requested after Task105A and Task104.

The goal is to compare the optimized `CC-DFlash-R2` Light GPU path against matched `Baseline-AR` and `DFlash-R1` references under the same local QMSum runtime setup:

- dataset: `qmsum_meeting_qa_long`
- seed: `42`
- n: `30`
- `max_new_tokens=384`
- stored generated text
- resume/no-overwrite JSONL artifacts
- same local RTX 4070 Laptop GPU shell

Task105B did not run QMSum n100, GSM8K, a full matrix, Large CPU, LLMLingua-AR-R2, query-aware compression, keep-rate tuning, model/config default changes, downloads, human scoring, or an LLM judge.

## 2. T105A/T104 Requirements Carried Into T105B

Task104 required speed/runtime claims to use matched references rather than incompatible historical comparisons. Task105A completed the GSM8K matched matrix and showed that optimized `CC-DFlash-R2` Light GPU was faster than `Baseline-AR` but not faster than `DFlash-R1`.

Task105B applies the same reference-alignment discipline to QMSum:

- compare only the matched QMSum n30/mnt384 artifacts from this task
- preserve the Task103D/T104 QMSum residual-risk caveat
- treat output completeness and lexical overlap as diagnostics only
- do not convert QMSum runtime evidence into semantic correctness proof

## 3. Runtime Matrix Setup

The three controlled artifacts are:

| Condition | Artifact |
| --- | --- |
| `Baseline-AR` | `results/phase_2_system_optimization/final_reruns/task105b_qmsum_controlled_runtime_matrix/runs/baseline_ar_qmsum_seed42_n30_mnt384.jsonl` |
| `DFlash-R1` | `results/phase_2_system_optimization/final_reruns/task105b_qmsum_controlled_runtime_matrix/runs/dflash_r1_qmsum_seed42_n30_mnt384.jsonl` |
| `CC-DFlash-R2` Light GPU | `results/phase_2_system_optimization/final_reruns/task105b_qmsum_controlled_runtime_matrix/runs/cc_dflash_r2_light_gpu_qmsum_seed42_n30_mnt384.jsonl` |

The optimized condition used:

- condition: `CC-DFlash-R2`
- compressor profile: `light`
- runtime compressor placement: `--compressor-device-map cuda`
- compressor default config unchanged
- local files only recorded by metadata
- average `R_actual=2.192619`

The reference conditions used no compressor:

- `Baseline-AR`
- `DFlash-R1`

## 4. Condition Completion / Resume Audit

All three controlled QMSum conditions completed `30/30` rows with matching metadata.

| Condition | Rows | Metadata OK | OOM/CUDA flags | Resume needed |
| --- | ---: | --- | --- | --- |
| `Baseline-AR` | `30/30` | yes | no | no |
| `DFlash-R1` | `30/30` | yes | no | no |
| `CC-DFlash-R2` Light GPU | `30/30` | yes | no | no |

No partial-condition substitution or historical reference substitution was used.

## 5. Output Completeness and Risk Diagnostics

Task105B uses deterministic output-shape and reference-overlap diagnostics only. These diagnostics do not establish semantic correctness.

| Condition | Empty/malformed | Cap-limited/incomplete | Low reference overlap | Avg reference unigram recall |
| --- | ---: | ---: | ---: | ---: |
| `Baseline-AR` | `0/30` | `0/30` | `15/30` | `0.195936` |
| `DFlash-R1` | `0/30` | `0/30` | `15/30` | `0.204572` |
| `CC-DFlash-R2` Light GPU | `0/30` | `0/30` | `14/30` | `0.210261` |

The optimized path did not introduce empty, malformed, cap-limited, or incomplete rows in this matched QMSum run. However, low lexical/reference overlap remains common across all three conditions, so the Task103D/T104 QMSum residual-risk caveat remains mandatory.

## 6. Runtime Metrics

| Condition | Avg e2e (s) | Avg generation (s) | Avg tok/s | Avg tau | Avg T_compress (ms) | Avg R_actual | Max VRAM reserved |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `Baseline-AR` | `3.770054` | `3.770054` | `25.593967` | `0.000000` | n/a | n/a | `4.308594 GiB` |
| `DFlash-R1` | `5.188113` | `5.188113` | `19.153680` | `2.421822` | n/a | n/a | `5.361328 GiB` |
| `CC-DFlash-R2` Light GPU | `5.235310` | `5.106272` | `20.914602` | `2.157238` | `129.038060` | `2.192619` | `5.414062 GiB` |

The optimized path completed with bounded local VRAM and no recorded OOM/CUDA failure, but it did not beat either matched QMSum reference on average e2e time.

## 7. Runtime Ranking

Task105B ranks conditions by average end-to-end time, lower is better:

1. `Baseline-AR`: `3.770054s`
2. `DFlash-R1`: `5.188113s`
3. `CC-DFlash-R2` Light GPU: `5.235310s`

The optimized Light GPU path was slower than `Baseline-AR` by `1.465256s` on average, or about `38.87%` higher average e2e time.

The optimized Light GPU path was slower than `DFlash-R1` by `0.047197s` on average, or about `0.91%` higher average e2e time.

Therefore Task105B does not support a controlled QMSum runtime claim that `CC-DFlash-R2` Light GPU is faster than `Baseline-AR`, `DFlash-R1`, or all matched QMSum references.

## 8. QMSum Caveat Carryforward

Task105B does not alter the Task103D/Task104 QMSum caveat:

> QMSum runtime feasibility is measured, but QMSum semantic correctness is not claimed; Task103D closed the deep-fix branch with persistent residual risk.

QMSum remains benchmark-scoped long-context runtime/reference evidence with confirmed residual semantic risk, not semantic-correctness proof.

## 9. Claim Update

Supported bounded claims:

- Task105B completed a controlled QMSum n30/mnt384 matrix over `Baseline-AR`, `DFlash-R1`, and `CC-DFlash-R2` Light GPU.
- Runtime comparisons are bounded to the local QMSum n30/mnt384 setup.
- `CC-DFlash-R2` Light GPU completed `30/30` rows with light compressor on CUDA, average `T_compress=129.038060ms`, average `R_actual=2.192619`, max reserved VRAM `5.414062 GiB`, and no recorded OOM/CUDA failure.
- All three QMSum conditions had `0/30` empty/malformed and `0/30` cap-limited/incomplete rows under this deterministic output-shape audit.

Blocked claims:

- final benchmark speedup
- faster than `Baseline-AR` on matched QMSum runtime
- faster than `DFlash-R1` on matched QMSum runtime
- faster than all matched QMSum references
- QMSum semantic correctness
- QMSum residual-risk elimination
- full benchmark speed claim closure
- universal 8GB deployment readiness
- default GPU switch
- `DFlash-R1` broken or invalid

## 10. Artifacts

Generated artifacts:

- `results/phase_2_system_optimization/final_reruns/task105b_qmsum_controlled_runtime_matrix/summary/task105b_matrix_summary.json`
- `results/phase_2_system_optimization/final_reruns/task105b_qmsum_controlled_runtime_matrix/summary/task105b_condition_metrics.json`
- `results/phase_2_system_optimization/final_reruns/task105b_qmsum_controlled_runtime_matrix/summary/task105b_runtime_ranking.json`
- `results/phase_2_system_optimization/final_reruns/task105b_qmsum_controlled_runtime_matrix/summary/task105b_output_completeness_summary.json`
- `results/phase_2_system_optimization/final_reruns/task105b_qmsum_controlled_runtime_matrix/summary/task105b_failure_or_resume_audit.json`
- `results/phase_2_system_optimization/final_reruns/task105b_qmsum_controlled_runtime_matrix/summary/task105b_qmsum_caveat_carryforward.json`
- `results/phase_2_system_optimization/final_reruns/task105b_qmsum_controlled_runtime_matrix/summary/task105b_claim_update.json`
- `results/phase_2_system_optimization/final_reruns/task105b_qmsum_controlled_runtime_matrix/summary/task105b_next_task_decision.json`
- `results/phase_2_system_optimization/final_reruns/task105b_qmsum_controlled_runtime_matrix/tables/task105b_qmsum_controlled_runtime_matrix.csv`

Analyzer:

- `scripts/phase_2_system_optimization/analysis/task105b_qmsum_controlled_runtime_matrix.py`

Tests:

- `tests/test_task105b_qmsum_controlled_runtime_matrix.py`

## 11. Decision

Decision: `PASS_WITH_CAVEAT`.

Rationale:

- all three controlled QMSum conditions completed `30/30`
- metadata matched the requested controlled setup
- no OOM/CUDA failure flags were recorded
- output-shape diagnostics found no empty/malformed or cap-limited/incomplete rows
- QMSum semantic correctness remains unclaimed
- optimized `CC-DFlash-R2` Light GPU did not beat `Baseline-AR` or `DFlash-R1` on average e2e time

## 12. Next Task

Next task: `T105C — Benchmark-Scope Claim Closure`.

T105C should close the benchmark-scope claim language across GSM8K and QMSum using Task105A and Task105B. Task105B does not authorize QMSum n100, GSM8K reruns, a full matrix, default GPU switch, or final speed/quality claim.
