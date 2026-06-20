# Task 95D — Bounded mnt256 Confirmation

## 1. Purpose

Task95D runs a second bounded `max_new_tokens=256` confirmation sample after Task95C-R repaired the light compressor quality proxy gap on the original seed42 `n=10` sample.

The purpose is to check whether the Task95C-R result survives one alternate `gsm8k_short` sample before any `n=30` move.

## 2. Setup

The setup matched Task95C-R except for the seed:

- condition: `CC-DFlash-R2`
- prompt source: `dataset`
- dataset: `gsm8k_short`
- seed: `43`
- `n=10`
- warmup prompts: `0`
- `max_new_tokens=256`
- stored generated text: yes
- resume: yes
- compressor profiles: large and light

No compressor config, model loading code, keep-rate setting, or model artifact was modified. No `n=30`, `n=100`, full benchmark, or LLM judge was run.

## 3. Fixture/Sample Independence Check

Before running GPU jobs, the dataset selection path was inspected. `scripts/run_mvp.py` calls `select_eval_dataset_rows(...)`, which uses `random.Random(seed).sample(rows, n)`.

A no-model Python probe confirmed that seed43 selects a different fixture set from the Task95C-R seed42 artifacts:

- seed42 fixture count: `10`
- seed43 fixture count: `10`
- overlap count: `0`
- duplicate sample: no

Seed43 fixture IDs:

- `gsm8k_short_test_0005`
- `gsm8k_short_test_0037`
- `gsm8k_short_test_0090`
- `gsm8k_short_test_0098`
- `gsm8k_short_test_0019`
- `gsm8k_short_test_0060`
- `gsm8k_short_test_0048`
- `gsm8k_short_test_0086`
- `gsm8k_short_test_0013`
- `gsm8k_short_test_0059`

## 4. Artifacts

Task95D seed43 run artifacts:

- large seed43 mnt256: `results/phase_2_system_optimization/quality_and_latency_audits/task95d_bounded_mnt256_confirmation/runs/20260621_025852_cc_dflash_r2_large_seed43_n10_mnt256.jsonl`
- light seed43 mnt256: `results/phase_2_system_optimization/quality_and_latency_audits/task95d_bounded_mnt256_confirmation/runs/20260621_025954_cc_dflash_r2_light_seed43_n10_mnt256.jsonl`

Summary/table artifacts:

- `results/phase_2_system_optimization/quality_and_latency_audits/task95d_bounded_mnt256_confirmation/summary/task95d_bounded_confirmation_summary.json`
- `results/phase_2_system_optimization/quality_and_latency_audits/task95d_bounded_mnt256_confirmation/summary/task95d_recommendation.json`
- `results/phase_2_system_optimization/quality_and_latency_audits/task95d_bounded_mnt256_confirmation/summary/task95d_row_labels.jsonl`
- `results/phase_2_system_optimization/quality_and_latency_audits/task95d_bounded_mnt256_confirmation/tables/task95d_bounded_confirmation_table.csv`

Row-count audit:

- large seed43 mnt256: `10` rows
- light seed43 mnt256: `10` rows

## 5. Results

| Setting | rows | calibrated strict | cap-limited incomplete | final-answer markers | strict wrong numeric | `t_compress_ms` | `R_actual` | e2e time (s) | tok/s | `tau_mean` |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| seed42 large mnt256 | 10 | 8/10 | 1/10 | 9/10 | 1/10 | 1272.62 | 2.67 | 3.78 | 61.98 | 6.03 |
| seed42 light mnt256 | 10 | 8/10 | 1/10 | 9/10 | 1/10 | 412.97 | 2.00 | 3.09 | 61.23 | 5.88 |
| seed43 large mnt256 | 10 | 7/10 | 3/10 | 7/10 | 0/10 | 1159.84 | 2.67 | 4.20 | 56.81 | 5.31 |
| seed43 light mnt256 | 10 | 8/10 | 2/10 | 8/10 | 0/10 | 362.78 | 2.00 | 3.41 | 60.64 | 5.83 |

Seed43 light-vs-large deltas, light minus large:

- calibrated strict: `+1`
- cap-limited incomplete: `-1`
- final-answer markers: `+1`
- e2e time: `-0.79s`
- `t_compress_ms`: `-797.06ms`
- `R_actual`: `-0.67`
- tok/s: `+3.83`

Seed42 to seed43 stability:

- large strict: `8/10 -> 7/10`
- light strict: `8/10 -> 8/10`
- large cap-limited incomplete: `1/10 -> 3/10`
- light cap-limited incomplete: `1/10 -> 2/10`

## 6. Interpretation

Task95D confirms the main Task95C-R bounded finding on a different seed43 sample: at `max_new_tokens=256`, the light profile remains near large on calibrated strict correctness and keeps cap-limited rows comparatively low.

In this seed43 sample, light slightly outperforms large on calibrated strict correctness (`8/10` vs `7/10`) and has fewer cap-limited incomplete rows (`2/10` vs `3/10`). Light also remains lower in average e2e time and much lower in average compression time, though it still has lower `R_actual`.

This is still a bounded deterministic proxy confirmation only. It does not prove final quality, final speedup, QMSum semantic behavior, deployment readiness, or universal performance.

## 7. Decision

Decision: **PASS_WITH_CAVEAT**.

Reason:

- both seed43 mnt256 jobs completed with `10` rows
- seed43 has zero fixture overlap with seed42
- analyzer completed and wrote the required artifacts
- light remains near large on calibrated strict correctness
- cap-limited rows remain bounded in this confirmation sample
- no `n=30`, `n=100`, full benchmark, keep-rate tuning, model-loading change, or LLM judge was run

## 8. Recommendation

Recommendation: **T96 n=30 controlled mnt256 comparison**.

Task95C-R plus Task95D provide enough bounded evidence to justify a gated `n=30` controlled mnt256 comparison, using the same policy boundaries. This is not a final benchmark claim; it is the next controlled step.

If the `n=30` run regresses, return to light tail/keep-rate triage rather than making deployment or final-quality claims.

## 9. Claim Boundary

Task95D makes no:

- final speedup claim
- final quality claim
- deployment or 8GB claim
- QMSum semantic correctness claim
- full benchmark claim
