# Task 68 — Freeze Final GSM8K Settings and n=100 Gate Plan

Date: 2026-06-13

Status: PASS, read-only synthesis

## Scope

Task 68 synthesized the compressed GSM8K calibration path from Tasks 53–67 and froze the next GSM8K settings. This task did not run benchmarks, did not load models, did not load compressors, did not use CUDA, did not run QMSum, and did not modify old artifacts.

Task 67 commit:

- `55890d4 test: triage persistent gsm8k mnt384 failures`

Inputs:

- `results/phase_1_system_build_and_evaluation/early_experiments/task60_mnt256_calibration_summary.json`
- `results/phase_1_system_build_and_evaluation/early_experiments/task63_n30_stability_summary.json`
- `results/phase_1_system_build_and_evaluation/early_experiments/task66_mnt384_rerun_reproducibility_summary.json`
- `results/phase_1_system_build_and_evaluation/early_experiments/task67_persistent_mnt384_failure_summary.json`
- `results/phase_1_system_build_and_evaluation/early_experiments/task61b_keep_rate67_calibration_summary.json`
- `results/phase_1_system_build_and_evaluation/early_experiments/task62_changed_outcome_triage_summary.json`
- `docs/reports/60-gsm8k-compressed-mnt256-calibration-report.md`
- `docs/reports/63-gsm8k-n30-stability-report.md`
- `docs/reports/66-gsm8k-mnt384-rerun-reproducibility-report.md`
- `docs/reports/67-gsm8k-persistent-mnt384-failure-triage-report.md`

Outputs:

- `scripts/phase_1_system_build_and_evaluation/analysis/t68_gsm8k_final_settings.py`
- `tests/test_task68_gsm8k_final_settings.py`
- `results/phase_1_system_build_and_evaluation/early_experiments/task68_gsm8k_final_settings_summary.json`
- `results/phase_1_system_build_and_evaluation/early_experiments/task68_gsm8k_final_settings_table.csv`

## GSM8K Recovery Path

The compressed GSM8K path recovered in stages:

- Task 53/54: compressed GSM8K quality remained weak before prompt/suffix and metadata fixes.
- Task 58: moved the final-answer instruction outside compression as a protected suffix.
- Task 60: `max_new_tokens=256` improved compressed numeric extraction and reduced cap hits in n=10 calibration.
- Task 63: default-R2 mnt256 remained stable at n=30, but cap hits remained visible.
- Task 66: mnt384 reproduced 24/30 numeric matches for both compressed conditions and showed Task 65 latency was noisy.
- Task 67: remaining mnt384 failures split evenly between remaining truncation and completed wrong-answer reasoning.

## Frozen GSM8K Settings

| Setting | keep_rate | max_new_tokens | Protected suffix | Purpose |
| --- | ---: | ---: | --- | --- |
| Speed-oriented | 0.50 | 256 | yes | speed / throughput tradeoff for compressed GSM8K |
| Quality-oriented | 0.50 | 384 | yes | quality upper-bound / quality calibration |

Summary evidence:

| Setting | Condition | Rows | Numeric matches | Numeric rate | Cap hits |
| --- | --- | ---: | ---: | ---: | ---: |
| Speed-oriented | LLMLingua-AR-R2 | 30 | 22 | 0.733333 | 5 |
| Speed-oriented | CC-DFlash-R2 | 30 | 23 | 0.766667 | 5 |
| Quality-oriented | LLMLingua-AR-R2 | 30 | 24 | 0.800000 | 3 |
| Quality-oriented | CC-DFlash-R2 | 30 | 24 | 0.800000 | 3 |

These are preliminary calibration numbers, not final correctness or speedup claims.

## Rejections and Deferrals

`keep_rate=0.67` is rejected as the default for now. Task 61B did not improve net numeric accuracy and introduced pass-to-fail instability in both compressed conditions.

`keep_rate=0.75` and `keep_rate=0.80` are deferred. Task 62 found no direct evidence that k67 repaired compression loss and explicitly did not recommend k80 next.

`max_new_tokens=512` is deferred. Task 67 failures were not dominated by truncation; they split evenly between remaining truncation and completed wrong-answer reasoning. A larger token budget is therefore not the next automatic move.

## n=100 Gate Decision

n=100 is not justified as the next real run.

Selected next-run option: Option C — n=30 full GSM8K matrix with comparable settings before n=100.

Reason: current n=30 evidence is compressed-only. Before expanding to n=100, Baseline-AR and DFlash-R1 should be compared under comparable GSM8K settings with the compressed conditions.

Recommended next task:

- Task 69: n=30 full GSM8K matrix using frozen settings, starting with quality-oriented `max_new_tokens=384` and unique resume-safe artifacts.

If Task 69 is accepted, the matrix should include:

- Baseline-AR
- DFlash-R1
- LLMLingua-AR-R2
- CC-DFlash-R2

Use `--resume`, `--store-generated-text`, unique `results/phase_1_system_build_and_evaluation/early_experiments/task69_*` output paths, and no `--overwrite`.

## Conservative Interpretation

CC-DFlash GSM8K evidence remains preliminary. Use:

- mnt256 as the speed-oriented compressed GSM8K setting.
- mnt384 as the quality-oriented compressed GSM8K setting.

Do not claim final correctness, final speedup, deployment readiness, confirmed 8 GB deployment, or proven end-to-end compression benefit.

## Verification

Commands run:

- `PYTHONPATH=src .venv/bin/python -m pytest tests/test_task68_gsm8k_final_settings.py -q`
- `PYTHONPATH=src .venv/bin/python scripts/phase_1_system_build_and_evaluation/analysis/t68_gsm8k_final_settings.py`
- `python3 -m compileall src tests scripts 2>&1 | tail -20`
- `PYTHONPATH=src .venv/bin/python -m pytest tests/ -x -q 2>&1 | tail -30`
- `python3 -m json.tool results/phase_1_system_build_and_evaluation/early_experiments/task68_gsm8k_final_settings_summary.json >/dev/null`
- HTML sanity checks for `<!DOCTYPE html>` and `</html>`
- Markdown fence balance checks for `instruction.md` and this report

Result: validation passed.
