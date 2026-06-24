# Task104 — Reference Alignment for Speed Claim

## 1. Purpose

Task104 aligns Phase 2 speed/runtime claims against valid reference points after Task103D closed the QMSum deep-fix branch with persistent residual risk.

This task is static audit/report work only. It did not run a benchmark, model inference, QMSum rerun, QMSum n100, full matrix, DFlash-R1 rerun, Large CPU rerun, GSM8K rerun, LLM judge, query-aware compression, keep-rate tuning, default switch, or download.

## 2. Why T104 Is Needed After T103D

Task103D allows T104 only with a mandatory QMSum caveat:

- QMSum deep-fix status: `CLOSED_WITH_PERSISTENT_RESIDUAL_RISK`
- QMSum semantic correctness: `NOT_CLAIMED`
- QMSum quality risk eliminated: `NO`
- Human-review labels: `0` correct-supported, `2` partially correct/incomplete, `1` unsupported/wrong, and `3` cannot-determine

Therefore speed wording must not imply QMSum semantic quality is solved. T104 separates runtime evidence from final speedup and final quality claims.

## 3. Evidence Inventory

| Evidence source | Scope | Key runtime evidence | Claim role |
| --- | --- | --- | --- |
| T96 | GSM8K `n=30`, `max_new_tokens=256`, CC-DFlash-R2 large CPU vs light CPU | Large CPU: strict `22/30`, `t_compress_ms=1201.58`, e2e `3.97s`, `R_actual=2.67`; Light CPU: strict `22/30`, `t_compress_ms=363.46`, e2e `3.23s`, `R_actual=2.00` | Controlled compressor-profile comparison |
| T99-R | GSM8K Light GPU `n=10` feasibility | strict `8/10`, `t_compress_ms=25.57`, e2e `2.67s`, max VRAM reserved about `4.36GiB` | Small gated GPU-placement observation |
| T100B | GSM8K Light GPU `n=100` optimized observation | strict `79/100`, cap-limited `15/100`, `t_compress_ms=17.35`, e2e `2.88s`, tok/s `59.83`, max VRAM reserved about `4.43GiB` | Single-condition optimized GSM8K runtime observation |
| T102 | QMSum Light GPU `n=30`, `max_new_tokens=384` | completed `30/30`, `t_compress_ms=125.26`, e2e `5.00s`, tok/s `21.34`, `R_actual=2.19`, max VRAM reserved about `5.41GiB` | Single-condition long-context runtime feasibility observation |
| T103D | QMSum closure | persistent residual semantic risk | Mandatory caveat for any QMSum-adjacent speed wording |

## 4. Comparator Map

| Comparison | Class | Interpretation |
| --- | --- | --- |
| T96 large CPU vs light CPU GSM8K n30 | `controlled_comparison` | Valid controlled comparison for light-vs-large compressor overhead and deterministic numeric proxy equality. |
| T99-R Light GPU GSM8K n10 | `single_condition_observation` | Useful small feasibility observation, not a full matrix. |
| T100B Light GPU GSM8K n100 | `single_condition_observation` | Optimized Light GPU observation; not synchronized against Baseline-AR/DFlash-R1. |
| T102 QMSum Light GPU n30 | `single_condition_observation` | Runtime-feasible local long-context observation with mandatory semantic-risk caveat. |
| Older Baseline/DFlash matrix results | `historical_reference_only` | Useful context only unless settings match exactly. |
| Baseline/DFlash results with different settings | `not_comparable` | Do not present as apples-to-apples speed evidence. |
| Final Baseline-AR/DFlash-R1/CC-DFlash speed ranking | `requires_t105_matrix` | Requires the controlled T105 matrix. |

## 5. Supported Speed Claims

Task104 supports the following bounded wording:

- Light compressor reduced `T_compress` versus the large compressor in the controlled GSM8K n30 comparison.
- Light GPU placement reduced compressor overhead to tens of milliseconds in the local optimized GSM8K n100 run.
- QMSum Light GPU completed the n30 long-context runtime feasibility run.
- Speed claims remain benchmark-scoped and configuration-scoped.

## 6. Blocked Speed Claims

Task104 blocks the following wording:

- CC-DFlash is finally faster than Baseline-AR.
- CC-DFlash is finally faster than DFlash-R1.
- The optimized path wins the full benchmark matrix.
- QMSum semantic correctness is proven.
- QMSum residual risk is eliminated.
- Universal 8GB deployment readiness is proven.

## 7. QMSum Caveat Carryforward

T104 must carry the T103D QMSum caveat into T105 and any later report/demo wording:

> QMSum runtime feasibility is measured, but QMSum semantic correctness is not claimed; T103D closed the deep-fix branch with persistent residual risk.

The six-row human review does not prove general QMSum quality. It instead supports bounded caveat language.

## 8. T105 Unblock Requirements

T104 unblocks T105, not final speed claims.

Minimum controlled matrix requirements for T105:

- same dataset
- same `n`
- same `max_new_tokens`
- same model/config
- same hardware
- same timing fields
- same resume/no-overwrite policy
- conditions at least: Baseline-AR, DFlash-R1, optimized CC-DFlash-R2 Light GPU
- QMSum caveat must be carried even if runtime improves

## 9. Roadmap Update

Roadmap status after Task104:

- T103D remains `PASS_WITH_CAVEAT`.
- T104 is `PASS_WITH_CAVEAT`.
- Current next is T105 — Controlled Full Matrix / Benchmark-Scope Claim Closure.
- T103B remains deferred/reserved, not default next.
- Final report integration remains deferred outside active Phase 2.

## 10. Scope Confirmation

Task104 produced only static artifacts and documentation. It did not run benchmark/model inference or alter runtime configuration.

Artifacts:

- `results/phase_2_system_optimization/final_reruns/task104_reference_alignment_for_speed_claim/task104_speed_reference_summary.json`
- `results/phase_2_system_optimization/final_reruns/task104_reference_alignment_for_speed_claim/task104_comparator_map.json`
- `results/phase_2_system_optimization/final_reruns/task104_reference_alignment_for_speed_claim/task104_supported_speed_claims.json`
- `results/phase_2_system_optimization/final_reruns/task104_reference_alignment_for_speed_claim/task104_blocked_speed_claims.json`
- `results/phase_2_system_optimization/final_reruns/task104_reference_alignment_for_speed_claim/task104_qmsum_caveat_carryforward.json`
- `results/phase_2_system_optimization/final_reruns/task104_reference_alignment_for_speed_claim/task104_t105_unblock_requirements.json`
- `results/phase_2_system_optimization/final_reruns/task104_reference_alignment_for_speed_claim/task104_next_task_decision.json`
- `results/phase_2_system_optimization/final_reruns/task104_reference_alignment_for_speed_claim/tables/task104_speed_reference_alignment_table.csv`

Decision: `PASS_WITH_CAVEAT`.
