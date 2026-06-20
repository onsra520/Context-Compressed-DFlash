# Task 96 — n=30 Controlled mnt256 Comparison

## 1. Purpose

Task96 runs the gated `n=30` controlled comparison recommended by Task95D.

The purpose is to check whether the bounded `max_new_tokens=256` light-compressor behavior still holds when the original Task95C-R seed42 sample is expanded from `n=10` to `n=30`.

## 2. Setup

The setup was intentionally narrow:

- condition: `CC-DFlash-R2`
- prompt source: `dataset`
- dataset: `gsm8k_short`
- seed: `42`
- `n=30`
- warmup prompts: `0`
- `max_new_tokens=256`
- stored generated text: yes
- resume: yes
- compressor profiles: large and light

No compressor config, model-loading code, keep-rate setting, or model artifact was modified. No `n=100`, full benchmark, Baseline-AR, DFlash-R1, QMSum, keep-rate tuning, model download, or LLM judge was run.

## 3. Artifacts

Task96 run artifacts:

- large seed42 n30 mnt256: `results/phase_2_system_optimization/compressor_comparison/task96_n30_controlled_mnt256_comparison/runs/20260621_032109_cc_dflash_r2_large_seed42_n30_mnt256.jsonl`
- light seed42 n30 mnt256: `results/phase_2_system_optimization/compressor_comparison/task96_n30_controlled_mnt256_comparison/runs/20260621_032329_cc_dflash_r2_light_seed42_n30_mnt256.jsonl`

Summary/table artifacts:

- `results/phase_2_system_optimization/compressor_comparison/task96_n30_controlled_mnt256_comparison/summary/task96_n30_controlled_summary.json`
- `results/phase_2_system_optimization/compressor_comparison/task96_n30_controlled_mnt256_comparison/summary/task96_recommendation.json`
- `results/phase_2_system_optimization/compressor_comparison/task96_n30_controlled_mnt256_comparison/summary/task96_row_labels.jsonl`
- `results/phase_2_system_optimization/compressor_comparison/task96_n30_controlled_mnt256_comparison/tables/task96_n30_controlled_table.csv`

Row-count audit:

- large seed42 n30 mnt256: `30` rows
- light seed42 n30 mnt256: `30` rows

## 4. Analyzer

Task96 added:

- `scripts/phase_2_system_optimization/analysis/task96_n30_controlled_mnt256_comparison.py`
- `tests/test_task96_n30_controlled_mnt256_comparison.py`

The analyzer reuses the Task95B calibrated deterministic quality proxy. It does not import model-loading or CUDA code.

The analyzer writes:

- profile-level metrics and metadata sanity checks
- calibrated row labels
- light-minus-large comparison deltas
- a bounded recommendation

## 5. Results

| Setting | rows | calibrated strict | cap-limited incomplete | final-answer markers | strict wrong numeric | exact containment | `t_compress_ms` | `R_actual` | e2e time (s) | tok/s | `tau_mean` |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| seed42 large n30 mnt256 | 30 | 22/30 | 5/30 | 25/30 | 3/30 | 24/30 | 1201.58 | 2.67 | 3.97 | 58.29 | 5.46 |
| seed42 light n30 mnt256 | 30 | 22/30 | 5/30 | 25/30 | 3/30 | 23/30 | 363.46 | 2.00 | 3.23 | 59.76 | 5.57 |

Light-vs-large deltas, light minus large:

- calibrated strict: `0`
- cap-limited incomplete: `0`
- final-answer markers: `0`
- strict wrong numeric: `0`
- exact containment: `-1`
- e2e time: `-0.74s`
- `t_compress_ms`: `-838.12ms`
- `R_actual`: `-0.67`
- tok/s: `+1.46`
- `tau_mean`: `+0.11`

## 6. Interpretation

Task96 confirms the bounded Task95C-R/Task95D finding at `n=30`: the light profile matches large on calibrated strict correctness (`22/30` vs `22/30`) and cap-limited incomplete rows (`5/30` vs `5/30`) while preserving a clear compression-time advantage.

Light is lower in average e2e time by about `0.74s` and lower in average compression time by about `838ms`. Light also has lower `R_actual` (`2.00` vs `2.67`), so the tradeoff remains a lighter/faster compressor with less aggressive compression rather than a final system speedup claim.

This remains bounded deterministic proxy evidence only. It does not prove final quality, final speedup, QMSum semantic behavior, deployment readiness, or universal performance.

## 7. Decision

Decision: **PASS_WITH_CAVEAT**.

Reason:

- both Task96 mnt256 jobs completed with `30` rows
- analyzer completed and wrote the required artifacts
- light stayed within the bounded quality envelope
- light had no calibrated strict regression relative to large
- light had no cap-limited incomplete increase relative to large
- light preserved a clear `t_compress_ms` advantage
- no `n=100`, full benchmark, Baseline-AR, DFlash-R1, QMSum, keep-rate tuning, model-loading change, model download, or LLM judge was run

Bounded confirmation holds at `n=30`: **yes**.

## 8. Recommendation

Recommendation: **T97 packaging controlled evidence summary**.

Task96 does not automatically authorize an `n=100` or full benchmark. The next bounded step should package the controlled Phase 2 evidence, document the light-vs-large tradeoff, and decide explicitly whether any further scaling is justified.

If a future larger run is proposed, it should stay gated and preserve the same claim boundaries unless additional evidence supports relaxing them.

## 9. Claim Boundary

Task96 makes no:

- final speedup claim
- final quality claim
- deployment or 8GB claim
- QMSum semantic correctness claim
- full benchmark claim
- n100 recommendation
