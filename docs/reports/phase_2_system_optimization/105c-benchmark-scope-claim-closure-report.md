# Task105C — Benchmark-Scope Claim Closure

## 1. Purpose

Task105C closes the benchmark-scope claim language across GSM8K and QMSum using the completed Task105A and Task105B controlled matrices.

This task is static closure/reporting only. It did not run a benchmark, model inference, QMSum rerun, QMSum n100, full dataset, Large CPU, LLMLingua-AR-R2, query-aware compression, keep-rate tuning, LLM judge, human scoring, default switch, or download.

## 2. Evidence Inputs From T105A and T105B

Task105C reads the committed summary artifacts from:

- Task105A — GSM8K Controlled Speed Matrix
- Task105B — QMSum Controlled Runtime Matrix
- Task104/T103D QMSum caveat carryforward

The closure inputs were complete:

| Input | Status |
| --- | --- |
| T105A GSM8K matrix | complete |
| T105B QMSum matrix | complete |
| T103D/T104 QMSum caveat | mandatory |

Decision: `PASS_WITH_CAVEAT`.

## 3. GSM8K Closure

Task105A completed the controlled GSM8K n100 matrix:

| Condition | Rows | Strict proxy | Avg e2e (s) |
| --- | ---: | ---: | ---: |
| `Baseline-AR` | `100/100` | `85/100` | `4.641074` |
| `DFlash-R1` | `100/100` | `84/100` | `2.650564` |
| `CC-DFlash-R2` Light GPU | `100/100` | `79/100` | `2.896622` |

Closure:

- `CC-DFlash-R2` Light GPU was faster than `Baseline-AR` on GSM8K average e2e time.
- `CC-DFlash-R2` Light GPU was slower than `DFlash-R1` on GSM8K average e2e time.
- `CC-DFlash-R2` Light GPU had lower strict proxy than both references.
- `CC-DFlash-R2` Light GPU had `15/100` cap-limited rows, compared with `8/100` for `Baseline-AR` and `9/100` for `DFlash-R1`.

Allowed GSM8K wording:

> In the controlled GSM8K n100 matrix, optimized CC-DFlash-R2 Light GPU was faster than Baseline-AR on average e2e time but slower than DFlash-R1.

Blocked GSM8K wording:

- faster than `DFlash-R1`
- faster than all references
- quality-preserved speed win
- final benchmark-wide speed win

## 4. QMSum Closure

Task105B completed the controlled QMSum n30/mnt384 runtime matrix:

| Condition | Rows | Avg e2e (s) | Empty/malformed | Cap-limited/incomplete |
| --- | ---: | ---: | ---: | ---: |
| `Baseline-AR` | `30/30` | `3.770054` | `0/30` | `0/30` |
| `DFlash-R1` | `30/30` | `5.188113` | `0/30` | `0/30` |
| `CC-DFlash-R2` Light GPU | `30/30` | `5.235310` | `0/30` | `0/30` |

The optimized QMSum condition also recorded:

- average `T_compress=129.038060ms`
- average `R_actual=2.192619`
- max reserved VRAM `5.414062 GiB`
- no recorded OOM/CUDA failure

Closure:

- `CC-DFlash-R2` Light GPU completed all QMSum rows.
- It did not produce empty/malformed or cap-limited/incomplete outputs in the deterministic output-shape audit.
- It was slower than both `Baseline-AR` and `DFlash-R1` on matched QMSum average e2e time.
- QMSum semantic correctness remains blocked by Task103D/T104.

Allowed QMSum wording:

> In the controlled QMSum n30 runtime matrix, optimized CC-DFlash-R2 Light GPU completed all rows but did not beat Baseline-AR or DFlash-R1 on average e2e time.

Mandatory QMSum caveat:

> QMSum runtime feasibility is measured, but QMSum semantic correctness is not claimed; T103D closed the deep-fix branch with persistent residual risk.

Human review labels remain:

- `0` correct-supported
- `2` partially correct/incomplete
- `1` unsupported/wrong
- `3` cannot-determine from available context

## 5. Cross-Dataset Claim Closure

Cross-dataset closure status:

- compressor-overhead reduction: supported
- local feasibility: supported
- final benchmark-wide speed win: blocked
- quality-preserved speed win: blocked
- default optimized switch: blocked until T106

Interpretation:

Phase 2 supports a benchmark-scoped candidate story, not a default-winner story. The optimized Light GPU path has useful bounded evidence, especially lower compressor overhead and GSM8K faster-than-Baseline behavior, but it does not beat `DFlash-R1` on GSM8K and does not beat either matched QMSum reference.

## 6. Supported Claims

Supported wording:

- Phase 2 reduced compressor overhead substantially with the light compressor and GPU placement.
- In the controlled GSM8K n100 matrix, optimized `CC-DFlash-R2` Light GPU was faster than `Baseline-AR` but slower than `DFlash-R1`.
- In the controlled QMSum n30 runtime matrix, optimized `CC-DFlash-R2` Light GPU completed all rows but did not beat `Baseline-AR` or `DFlash-R1` on average e2e time.
- QMSum remains runtime/feasibility and residual-risk evidence, not semantic-correctness proof.
- Final claims remain benchmark-scoped and condition-scoped.

## 7. Blocked Claims

Blocked wording:

- Optimized CC-DFlash wins the full benchmark.
- Optimized CC-DFlash is faster than all references.
- Optimized CC-DFlash preserves quality while improving speed across datasets.
- QMSum semantic correctness is proven.
- QMSum residual risk is eliminated.
- Universal 8GB deployment readiness is proven.
- The optimized Light GPU path should become the default.
- `DFlash-R1` is broken or invalid.

## 8. T106 Unblock Requirements

T105C unblocks T106 only as an optimized-default candidate decision. It does not authorize an automatic default switch.

T106 must preserve:

- GSM8K faster-than-Baseline only
- not faster-than-DFlash on GSM8K
- not faster-than-any-reference on QMSum
- QMSum semantic caveat
- no universal 8GB deployment readiness

Recommended T106 posture:

- candidate path for specific Baseline-AR comparison
- experimental optimized path
- not default winner
- defer default switch unless explicitly justified by a future decision

## 9. Roadmap Update

Roadmap status after Task105C:

- T105A remains `PASS_WITH_CAVEAT`.
- T105B remains `PASS_WITH_CAVEAT`.
- T105C is `PASS_WITH_CAVEAT`.
- Current next is `T106 — Optimized Default Candidate Decision`.
- T103B remains deferred/reserved.
- Final report integration remains deferred outside active Phase 2.

## 10. Artifacts

Generated artifacts:

- `results/phase_2_system_optimization/final_reruns/task105c_benchmark_scope_claim_closure/summary/task105c_closure_summary.json`
- `results/phase_2_system_optimization/final_reruns/task105c_benchmark_scope_claim_closure/summary/task105c_dataset_claim_matrix.json`
- `results/phase_2_system_optimization/final_reruns/task105c_benchmark_scope_claim_closure/summary/task105c_supported_claims.json`
- `results/phase_2_system_optimization/final_reruns/task105c_benchmark_scope_claim_closure/summary/task105c_blocked_claims.json`
- `results/phase_2_system_optimization/final_reruns/task105c_benchmark_scope_claim_closure/summary/task105c_cross_dataset_interpretation.json`
- `results/phase_2_system_optimization/final_reruns/task105c_benchmark_scope_claim_closure/summary/task105c_t106_unblock_requirements.json`
- `results/phase_2_system_optimization/final_reruns/task105c_benchmark_scope_claim_closure/summary/task105c_next_task_decision.json`
- `results/phase_2_system_optimization/final_reruns/task105c_benchmark_scope_claim_closure/tables/task105c_benchmark_scope_claim_table.csv`

Analyzer:

- `scripts/phase_2_system_optimization/analysis/task105c_benchmark_scope_claim_closure.py`

Tests:

- `tests/test_task105c_benchmark_scope_claim_closure.py`

## 11. Scope Confirmation

Task105C is static closure/reporting only.

No benchmark, model inference, QMSum rerun, QMSum n100, GSM8K rerun, full matrix, Large CPU, LLMLingua-AR-R2, query-aware compression, keep-rate tuning, LLM judge, human scoring, default switch, or download was run.
