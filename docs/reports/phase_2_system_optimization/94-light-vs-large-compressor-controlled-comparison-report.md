# Task 94 — Light vs Large Compressor Controlled Comparison

## 1. Purpose

Task94 runs the bounded controlled comparison requested after Task93.

Scope was intentionally limited:

- condition: `CC-DFlash-R2`
- dataset: `gsm8k_short`
- seed: `42`
- `n=10`
- `max_new_tokens=128`
- same runner/settings for both profiles

This is not a full benchmark and does not justify `n=30` yet.

## 2. Preflight and gates

Preflight completed on branch `main` with a clean tracked worktree:

- `git branch --show-current` → `main`
- `git status --short` → clean
- `git diff --stat` → clean

Mandatory config/runner checks passed:

- large profile resolves to `models/llmlingua-2-xlm-roberta-large-meetingbank`
- light profile resolves to `models/llmlingua-2-bert-base-multilingual-cased-meetingbank`
- both profiles use `local_files_only: true`
- both profiles are selectable through `--compressor-profile`
- output rows include compressor metadata including profile, configured path, resolved path, and local-only flag

GPU visibility gate passed in this shell:

- `nvidia-smi` detected `NVIDIA GeForce RTX 4070 Laptop GPU`
- `torch 2.5.1+cu121`
- `torch.cuda.is_available()` → `True`
- torch CUDA runtime → `12.1`

## 3. Controlled runs

Artifacts:

- large run: `results/phase_2_system_optimization/compressor_comparison/task94_light_vs_large_compressor_controlled_comparison/runs/20260620_192758_cc_dflash_r2_large_n10.jsonl`
- light run: `results/phase_2_system_optimization/compressor_comparison/task94_light_vs_large_compressor_controlled_comparison/runs/20260620_192904_cc_dflash_r2_light_n10.jsonl`

Row-count check:

- large rows: `10`
- light rows: `10`

No overwrite path was used. Both runs used unique filenames plus `--resume`.

## 4. Results

Summary table artifact:

- `results/phase_2_system_optimization/compressor_comparison/task94_light_vs_large_compressor_controlled_comparison/tables/task94_large_vs_light_table.csv`

Structured summary artifact:

- `results/phase_2_system_optimization/compressor_comparison/task94_light_vs_large_compressor_controlled_comparison/summary/task94_large_vs_light_summary.json`

Quality-proxy artifact:

- `results/phase_2_system_optimization/compressor_comparison/task94_light_vs_large_compressor_controlled_comparison/summary/task94_quality_proxy_analysis.json`

Controlled `n=10` averages:

| Profile | rows | avg `t_compress_ms` | avg `R_actual` | avg e2e time (s) | avg tok/s | avg `tau_mean` | numeric extraction |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| large | 10 | 1190.11 | 2.67 | 3.10 | 64.46 | 6.06 | 6/10 |
| light | 10 | 406.39 | 2.00 | 2.46 | 63.28 | 5.88 | 2/10 |

Observed deltas, `light - large`:

- avg `t_compress_ms`: `-783.72`
- avg `R_actual`: `-0.67`
- avg e2e time: `-0.64 s`
- avg tok/s: `-1.18`
- avg `tau_mean`: `-0.18`
- numeric extraction match rate: `-0.40`
- exact containment rate: `-0.20`

Metadata checks stayed clean for both profiles:

- `local_files_only = true` on every row
- `compressor_path` present on every row
- `resolved_compressor_path` present on every row
- protected suffix preserved on every row

## 5. Interpretation

The light compressor clearly reduced compression overhead in this bounded comparison. Average `t_compress_ms` was about `2.93x` lower than the large profile, and average end-to-end time was also lower.

However, the light profile also compressed less (`R_actual 2.00` vs `2.67`) and performed worse on the bounded GSM8K numeric proxy (`2/10` vs `6/10`). So Task94 does not support adopting the light profile as a drop-in replacement based on this evidence alone.

This task therefore supports a narrower conclusion only:

- light improves compression-time feasibility in this controlled `n=10` setup
- large preserved stronger compression ratio and a better GSM8K numeric proxy in the same setup
- `n=30` is not justified yet from Task94 alone

## 6. Validation

Validation completed:

- required preflight commands from the task brief
- config/profile grep audit
- `nvidia-smi`
- Python CUDA visibility check
- `PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --help`
- row-count audit for both `n=10` JSONL artifacts
- `PYTHONPATH=.:src .venv/bin/python scripts/phase_1_system_build_and_evaluation/analysis/t31_answer_quality.py ...`
- `PYTHONPATH=.:src .venv/bin/python scripts/phase_2_system_optimization/analysis/task94_light_vs_large_compressor_controlled_comparison.py ...`
- `PYTHONPATH=.:src .venv/bin/python -m pytest tests/test_task94_light_vs_large_compressor_controlled_comparison.py -q`

## 7. Decision

Task94 status: PASS_WITH_CAVEAT.

Reason:

- the required controlled `n=10` comparison was completed successfully
- both artifacts are valid and bounded
- the light profile improved `t_compress_ms`
- the light profile also reduced `R_actual` and underperformed on the GSM8K numeric proxy

## 8. Next task handoff

Task95 should focus on quality-proxy calibration / interpretation before any `n=30` move.

Suggested direction:

- inspect the light-profile failure rows versus the large-profile successes
- determine whether the drop is mostly compression-loss, prompt-tail sensitivity, or ordinary sample noise
- do not claim final speedup, deployment readiness, or QMSum semantic correctness
- do not run `n=30` unless a later task explicitly justifies it
