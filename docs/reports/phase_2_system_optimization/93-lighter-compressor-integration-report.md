# Task 93 — Lighter Compressor Integration

## 1. Purpose

Task93 integrates the lighter LLMLingua-2 compressor profile into the real CC-DFlash runner after the Task92 local path/config audit.

This is an integration and smoke-comparison task, not a final benchmark. It verifies that the light profile can be selected by `scripts/run_mvp.py`, uses the intended local compressor folder, and records a tiny large-vs-light CC-DFlash-R2 smoke comparison.

## 2. Profiles

Large compressor:

- `models/llmlingua-2-xlm-roberta-large-meetingbank`
- `local_files_only: true`

Light compressor:

- `models/llmlingua-2-bert-base-multilingual-cased-meetingbank`
- `local_files_only: true`

No model downloads were performed.

## 3. Code/config changes

No runner or config change was needed. Task92 infrastructure already supported Task93:

- `--compressor-profile` supports `large`, `large_llmlingua`, `light`, and `light_llmlingua`.
- `config.yml` already defines local `compressor_path` values for both profiles.
- `scripts/run_mvp.py` already writes compressor metadata into output rows.

Task93 added focused static tests for profile aliases, local path resolution, and compression metadata propagation.

## 4. Validation

Validation completed:

- `python -m compileall src tests scripts`
- `PYTHONPATH=src .venv/bin/python -m pytest tests/test_task93_lighter_compressor_integration.py -q`
- `PYTHONPATH=src .venv/bin/python -m pytest tests/test_task92_local_model_config_loading.py -q`
- `PYTHONPATH=src .venv/bin/python -m pytest tests/test_compression.py -q`
- `PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --help`
- static profile resolution artifact
- GPU visibility check through `nvidia-smi` and `torch.cuda.is_available()`
- large-vs-light `n=3` CC-DFlash-R2 smoke comparison

GPU was visible in this shell:

- GPU: NVIDIA GeForce RTX 4070 Laptop GPU
- torch: `2.5.1+cu121`
- torch CUDA runtime: `12.1`

## 5. Smoke comparison

Smoke scope:

- condition: `CC-DFlash-R2`
- prompt source: `dataset`
- dataset: `gsm8k_short`
- seed: `42`
- rows per profile: `3`
- max new tokens: `128`
- warmup prompts: `0`

Artifacts:

- large: `results/phase_2_system_optimization/compressor_integration/task93_lighter_compressor_integration/smoke/20260620_162415_cc_dflash_r2_large_n3.jsonl`
- light: `results/phase_2_system_optimization/compressor_integration/task93_lighter_compressor_integration/smoke/20260620_162511_cc_dflash_r2_light_n3.jsonl`
- summary JSON: `results/phase_2_system_optimization/compressor_integration/task93_lighter_compressor_integration/comparison_summary/task93_large_vs_light_smoke_summary.json`
- summary CSV: `results/phase_2_system_optimization/compressor_integration/task93_lighter_compressor_integration/comparison_summary/task93_large_vs_light_smoke_table.csv`

Tiny-smoke averages:

| Profile | rows | avg `t_compress_ms` | avg `R_actual` | avg tok/s | avg e2e tok/s | avg `tau_mean` | avg `t_prefill_ms` |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| large | 3 | 1326.83 | 2.67 | 58.39 | 35.73 | 5.44 | 139.53 |
| light | 3 | 426.76 | 2.00 | 53.93 | 44.44 | 5.16 | 142.08 |

Metadata checks:

- large rows reported `compressor_profile = large`
- light rows reported `compressor_profile = light`
- light rows reported `compressor_path = models/llmlingua-2-bert-base-multilingual-cased-meetingbank`
- light rows reported the resolved local compressor path under this repository
- both profiles reported `local_files_only = true`
- no required compressor metadata fields were missing from the smoke rows

Generated text was present for both profiles. This task does not judge answer correctness.

## 6. Decision

Task93 status: PASS with caveat.

The light profile runs correctly through `scripts/run_mvp.py`, uses the intended local path, and records the expected metadata. In this tiny `n=3` smoke, the light profile reduced average `t_compress_ms` versus the large profile.

The caveat is that this is not a controlled benchmark. The light profile also produced a lower average `R_actual` in this smoke, so Task94 must compare quality, compression ratio, and end-to-end feasibility under a bounded controlled setup before any broader conclusion.

## 7. Task94 handoff

Task94 should run a controlled light-vs-large compressor comparison.

Suggested scope:

- start with `n=10`
- use the same dataset/settings for large and light
- compare `T_compress`, `R_actual`, end-to-end feasibility, and quality proxy stability
- run `n=30` only if `n=10` is stable

No final speedup claim should be made until controlled comparison evidence exists.

## 8. Claim boundary

- No final benchmark claim
- No final speedup claim
- No deployment or confirmed 8GB claim
- No QMSum semantic correctness claim
- Task93 is integration/smoke only
