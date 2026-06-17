# Task 46 — Pareto Analysis Report

Date: 2026-06-06

## Result

PASS for Task 46 Pareto analysis/report.

This report analyzes the audited Task 45 final artifacts. It distinguishes decode-only throughput from end-to-end latency that includes CPU compression cost.

No deployment readiness, confirmed 8 GB deployment, final semantic correctness, or proven end-to-end compression benefit is claimed.

## Artifact Sources

Inputs:

- `results/phase_1_system_build_and_evaluation/early_experiments/task45_final_artifact_audit_summary.json`
- `results/phase_1_system_build_and_evaluation/early_experiments/task45_final_baseline_ar_n100.jsonl`
- `results/phase_1_system_build_and_evaluation/early_experiments/task45_final_dflash_r1_n100.jsonl`
- `results/phase_1_system_build_and_evaluation/early_experiments/task45_final_llmlingua_ar_r2_n100.jsonl`
- `results/phase_1_system_build_and_evaluation/early_experiments/task45_final_cc_llm_r2_n100.jsonl`

Outputs:

- `results/phase_1_system_build_and_evaluation/early_experiments/task46_pareto_summary.json`
- `results/phase_1_system_build_and_evaluation/early_experiments/task46_pareto_table.csv`

Analyzer:

- `scripts/phase_1_system_build_and_evaluation/analysis/t46_pareto.py`

Command:

```bash
PYTHONPATH=src .venv/bin/python scripts/phase_1_system_build_and_evaluation/analysis/t46_pareto.py --audit results/phase_1_system_build_and_evaluation/early_experiments/task45_final_artifact_audit_summary.json --output results/phase_1_system_build_and_evaluation/early_experiments/task46_pareto_summary.json
```

## Method

Per row:

- `decode_latency_s = generation_time_s`
- `compression_latency_s = t_compress_ms / 1000` when compression exists, otherwise `0`
- `e2e_latency_s = generation_time_s + t_compress_ms / 1000`
- `e2e_output_tokens_per_second = sum(output_tokens) / sum(e2e_latency_s)`

Pareto dimensions:

- Decode-only view:
  - higher `avg_tokens_per_second` is better
  - higher diagnostic normalized containment rate is better
  - lower max VRAM reserved is better
- E2E-with-compression-cost view:
  - higher `e2e_output_tokens_per_second` is better
  - higher diagnostic normalized containment rate is better
  - lower max VRAM reserved is better

Quality is diagnostic only. It is not a final semantic correctness benchmark.

## Metric Table

| Condition | Rows | Avg decode tok/s | Median decode tok/s | Avg gen s | Median gen s | Avg e2e s | Median e2e s | E2E tok/s | Avg input tok | Avg output tok | Avg tau | Median tau | Avg prefill ms | Avg compress ms | Avg R | Max VRAM reserved GiB |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Baseline-AR | 100 | 16.91 | 17.26 | 7.62 | 7.40 | 7.62 | 7.40 | 16.73 | 1471.22 | 127.46 | 0.00 | 0.00 | 1323.82 | n/a | n/a | 6.51 |
| DFlash-R1 | 100 | 42.87 | 42.24 | 3.06 | 3.02 | 3.06 | 3.02 | 41.64 | 1471.22 | 127.49 | 5.27 | 5.12 | 492.37 | n/a | n/a | 7.53 |
| LLMLingua-AR-R2 | 100 | 16.89 | 17.41 | 7.62 | 7.35 | 11.67 | 11.56 | 10.95 | 778.92 | 127.77 | 0.00 | 0.00 | 276.68 | 4057.67 | 2.06 | 3.20 |
| CC-LLM-R2 | 100 | 48.26 | 47.99 | 2.72 | 2.67 | 6.90 | 6.81 | 18.51 | 778.92 | 127.74 | 5.06 | 4.94 | 277.75 | 4179.75 | 2.06 | 4.22 |

## Decode-Only Ranking

| Rank | Condition | Avg decode tok/s |
| ---: | --- | ---: |
| 1 | CC-LLM-R2 | 48.26 |
| 2 | DFlash-R1 | 42.87 |
| 3 | Baseline-AR | 16.91 |
| 4 | LLMLingua-AR-R2 | 16.89 |

Decode-only observation:

- DFlash-R1 is much faster than Baseline-AR in decode-only throughput.
- CC-LLM-R2 is the highest decode-only throughput condition.
- LLMLingua-AR-R2 reduces input length but does not improve decode-only throughput over Baseline-AR.

## E2E-With-Compression Ranking

| Rank | Condition | Avg e2e latency s | E2E tok/s |
| ---: | --- | ---: | ---: |
| 1 | DFlash-R1 | 3.06 | 41.64 |
| 2 | CC-LLM-R2 | 6.90 | 18.51 |
| 3 | Baseline-AR | 7.62 | 16.73 |
| 4 | LLMLingua-AR-R2 | 11.67 | 10.95 |

E2E observation:

- DFlash-R1 is the strongest end-to-end latency condition because it avoids CPU compression cost.
- CC-LLM-R2 remains faster than Baseline-AR in this measured e2e approximation, but its margin is much smaller than its decode-only margin.
- LLMLingua-AR-R2 is slower than Baseline-AR end-to-end because CPU compression cost dominates.

## Relative Comparisons

| Comparison | Decode tok/s ratio | E2E tok/s ratio | E2E latency ratio | Input token ratio | Tau delta | VRAM reserved delta GiB | Quality normalized delta | Compression cost delta ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| DFlash-R1 vs Baseline-AR | 2.54 | 2.49 | 0.40 | 1.00 | +5.27 | +1.02 | -0.01 | 0.00 |
| LLMLingua-AR-R2 vs Baseline-AR | 1.00 | 0.65 | 1.53 | 0.53 | +0.00 | -3.31 | -0.08 | +4057.67 |
| CC-LLM-R2 vs LLMLingua-AR-R2 | 2.86 | 1.69 | 0.59 | 1.00 | +5.06 | +1.02 | +0.02 | +122.07 |
| CC-LLM-R2 vs DFlash-R1 | 1.13 | 0.44 | 2.25 | 0.53 | -0.21 | -3.30 | -0.05 | +4179.75 |
| CC-LLM-R2 vs Baseline-AR | 2.85 | 1.11 | 0.91 | 0.53 | +5.06 | -2.29 | -0.06 | +4179.75 |

## Quality Diagnostic Table

| Condition | Generated text rows | Exact containment | Normalized containment total | Extracted numeric matches | No containment | Diagnostic normalized rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Baseline-AR | 100 | 24 | 25 | 10 | 75 | 0.25 |
| DFlash-R1 | 100 | 23 | 24 | 10 | 76 | 0.24 |
| LLMLingua-AR-R2 | 100 | 16 | 17 | 5 | 83 | 0.17 |
| CC-LLM-R2 | 100 | 18 | 19 | 6 | 81 | 0.19 |

Interpretation:

- Diagnostic quality is low across all conditions.
- Compressed conditions have lower diagnostic containment and extracted numeric match counts than the no-compression controls.
- This prevents a strong claim that CC-LLM-R2 is globally dominant.

## Pareto Front Discussion

Decode-only Pareto front:

- Baseline-AR
- DFlash-R1
- LLMLingua-AR-R2
- CC-LLM-R2

E2E-with-compression-cost Pareto front:

- Baseline-AR
- DFlash-R1
- LLMLingua-AR-R2
- CC-LLM-R2

Why all four remain on the conservative front:

- Baseline-AR has the highest diagnostic normalized containment rate.
- DFlash-R1 has the best e2e throughput/latency and strong diagnostic quality among the non-compressed controls.
- LLMLingua-AR-R2 has the lowest VRAM reserved and reduced input tokens, but poor e2e cost and lower diagnostic quality.
- CC-LLM-R2 has the highest decode-only throughput and reduced input tokens, but CPU compression overhead and lower diagnostic quality keep it from dominating DFlash-R1.

Conservative conclusion:

- DFlash-R1 is the strongest current default baseline.
- CC-LLM-R2 is promising for decode-only throughput and input reduction, but not globally dominant once CPU compression and diagnostic quality are included.
- LLMLingua-AR-R2 is useful as the low-VRAM attribution baseline, not as a speed winner.
- Compression remains a research path, but CPU compression cost is the main bottleneck in this run.

## Caveats

- Quality is diagnostic containment/extraction, not final semantic correctness.
- `flash_attn` is not installed; current backend uses torch SDPA fallback.
- Compression runs on CPU and adds roughly four seconds per prompt in these artifacts.
- Pareto classification depends on chosen dimensions; the report uses conservative dimensions to avoid overclaiming.
- No deployment readiness or confirmed 8 GB fit is claimed.

## Recommended Next Tasks

Task 47 should focus on quality evaluation refinement and final presentation packaging:

- inspect low-containment rows by condition,
- decide whether answer extraction/scoring should be improved before paper figures,
- prepare figures/tables that show both decode-only and e2e-with-compression views,
- keep CC-LLM-R2 as a watchlist condition rather than a claimed winner.

Task 48 can then produce paper-ready figures if Task 47 resolves the quality presentation policy.

## Validation

Commands:

```bash
PYTHONPATH=src .venv/bin/python scripts/phase_1_system_build_and_evaluation/analysis/t46_pareto.py --audit results/phase_1_system_build_and_evaluation/early_experiments/task45_final_artifact_audit_summary.json --output results/phase_1_system_build_and_evaluation/early_experiments/task46_pareto_summary.json
python3 -m json.tool results/phase_1_system_build_and_evaluation/early_experiments/task46_pareto_summary.json >/tmp/task46_pareto_summary.check.json
python3 -m compileall src tests scripts 2>&1 | tail -20
PYTHONPATH=src .venv/bin/python -m pytest tests/ -x -q 2>&1 | tail -30
```

Results are recorded in the final response.

## Understand-Anything Status

Understand-Anything refresh was skipped because `/understand` is not available in this environment.

No graph/dashboard refresh is claimed.

