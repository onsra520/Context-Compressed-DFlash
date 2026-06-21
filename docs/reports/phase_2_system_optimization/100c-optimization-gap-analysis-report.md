# Task100C - Optimization Gap Analysis

## 1. Purpose

Task100C analyzes remaining optimization gaps after Task100B.

This task is analysis-only. It ran no benchmark, model inference, GPU job, `n=100` rerun, `n=30`, QMSum run, full matrix, keep-rate tuning, model/config change, model download, or LLM judge.

## 2. Inputs

Primary Task100B artifact:

- `results/phase_2_system_optimization/final_reruns/task100b_light_gpu_n100_controlled_run/runs/20260621_1555_cc_dflash_r2_light_gpu_seed42_n100_mnt256.jsonl`

Task100B summary:

- `results/phase_2_system_optimization/final_reruns/task100b_light_gpu_n100_controlled_run/summary/task100b_light_gpu_n100_summary.json`

Reference context:

- Task99-R Light GPU `n=10` bounded reference
- Task96 Light CPU `n=30` bounded reference
- Task96 Large CPU `n=30` bounded reference
- Task88 DFlash-R1 historical-only reference when mentioned

Analyzer:

- `scripts/phase_2_system_optimization/analysis/task100c_optimization_gap_analysis.py`

## 3. Quality Gap Analysis

Task100B Light GPU `n=100` calibrated quality summary:

- row count: `100`
- calibrated strict: `79/100`
- cap-limited incomplete: `15/100`
- strict wrong numeric: `6/100`
- answer missing: `0/100`
- proxy uncertain: `0/100`
- format or extraction sensitive: `0/100`
- final-answer marker: `85/100`
- exact containment diagnostic: `83/100`
- non-strict rows: `21/100`

Failure categories:

- `cap_limited_incomplete`: `15`
- `strict_wrong_numeric`: `6`
- `answer_missing`: `0`
- `proxy_uncertain`: `0`
- `format_or_extraction_sensitive`: `0`

Interpretation:

- The dominant remaining quality gap is output cap / incomplete tail pressure.
- The second remaining quality gap is completed but wrong numeric reasoning.
- No missing-answer or proxy-uncertain rows appeared under the calibrated deterministic proxy.
- Exact containment remains diagnostic only; short numeric answers can appear as intermediate values.

Row-level failure records were written to:

- `results/phase_2_system_optimization/final_reruns/task100c_optimization_gap_analysis/task100c_failure_rows.jsonl`

## 4. Runtime Bottleneck Analysis

Task100C runtime summary:

| Metric | avg | min | max | p95 |
| --- | ---: | ---: | ---: | ---: |
| `t_compress_ms` | `17.35` | `13.81` | `156.06` | `17.84` |
| e2e time | `2.88s` | `1.10s` | `6.70s` | `4.70s` |
| tokens/sec | `59.83` | `34.72` | `84.88` | `81.10` |
| `tau_mean` | `5.63` | `3.26` | `8.33` | `7.48` |
| `t_prefill_ms` | `95.95` | `86.44` | `212.20` | `106.02` |

Slowest rows were emitted to:

- `results/phase_2_system_optimization/final_reruns/task100c_optimization_gap_analysis/task100c_slowest_rows.jsonl`

Observed pattern:

- Failure rows had higher average e2e time (`3.89s`) than strict-correct rows (`2.61s`).
- `5/10` slowest rows were failure rows.
- The single largest `t_compress_ms` row was row 1, but p95 compression time stayed low at `17.84ms`, so the average compression story is not driven by broad compressor overhead.

## 5. Compression and GPU Stability

Compression behavior:

- average `R_actual`: `2.00`
- min `R_actual`: `2.00`
- max `R_actual`: `2.00`
- p95 `R_actual`: `2.00`
- failure-row `R_actual`: `2.00`
- `R_actual` was stable around `2.00`
- compression overhead stayed consistently low by p95

GPU/VRAM behavior:

- average VRAM allocated: `4.16GiB`
- max VRAM allocated: `4.16GiB`
- average VRAM reserved: `4.38GiB`
- max VRAM reserved: `4.43GiB`
- OOM/CUDA failure flags: none
- VRAM appears bounded in this run

Claim boundary:

- This does not prove deployment readiness.
- This does not prove confirmed 8GB readiness.
- This does not justify a default GPU switch.

## 6. Reference Comparison Notes

Task99-R Light GPU `n=10`:

- useful as a bounded scale-up reference only
- sample size differs from Task100B `n=100`

Task96 Light CPU `n=30`:

- useful as a bounded CPU-path reference
- sample size differs from Task100B

Task96 Large CPU `n=30`:

- useful as a bounded historical/control CPU reference
- sample size differs from Task100B

Task88 DFlash-R1:

- historical-only if mentioned
- settings differ, including prior `max_new_tokens=512`
- not an apples-to-apples Task100B comparison

## 7. Claim Risks

Task100C wrote a claim-risk register to:

- `results/phase_2_system_optimization/final_reruns/task100c_optimization_gap_analysis/task100c_claim_risk_register.json`

Registered risks:

- final speedup not proven because no full matrix or Baseline/DFlash-normalized final benchmark was run
- final quality not proven because Task100B uses deterministic GSM8K numeric proxy only
- QMSum semantic correctness not tested
- deployment and 8GB readiness not proven
- full benchmark not run
- DFlash-R1 not proven broken
- GPU default switch not justified
- remaining cap-limited rows: `15/100`
- remaining strict wrong numeric rows: `6/100`
- Task96 references are `n=30`, not equal-setting `n=100` references

## 8. Decision

Decision: **PASS**.

Reason:

- Task100B artifacts were complete and readable
- row-level quality gaps were classified
- failure rows and slowest rows were emitted
- bottleneck summary was generated
- compression and GPU/VRAM stability were summarized
- claim risks were registered
- recommendation was generated
- no benchmark/model run was performed

## 9. Recommendation

Proceed to **T101 - Final Claim Boundary Audit**.

Do not automatically:

- run another benchmark
- run QMSum
- run a full matrix
- tune keep rate
- switch GPU placement on by default

Task100C finds remaining risks that should be handled as claim-boundary issues before final report/demo integration, not as default triggers for another benchmark.

## 10. Artifacts

- `results/phase_2_system_optimization/final_reruns/task100c_optimization_gap_analysis/task100c_gap_summary.json`
- `results/phase_2_system_optimization/final_reruns/task100c_optimization_gap_analysis/task100c_failure_rows.jsonl`
- `results/phase_2_system_optimization/final_reruns/task100c_optimization_gap_analysis/task100c_slowest_rows.jsonl`
- `results/phase_2_system_optimization/final_reruns/task100c_optimization_gap_analysis/task100c_bottleneck_table.csv`
- `results/phase_2_system_optimization/final_reruns/task100c_optimization_gap_analysis/task100c_recommendation.json`
- `results/phase_2_system_optimization/final_reruns/task100c_optimization_gap_analysis/task100c_claim_risk_register.json`
