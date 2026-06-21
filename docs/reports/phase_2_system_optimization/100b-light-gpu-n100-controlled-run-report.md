# Task100B - Light GPU n100 Controlled Run

## 1. Purpose

Task100B scales the promising Task99-R Light GPU candidate to a bounded `n=100` GSM8K mnt256 run.

This is a candidate scale-up validation only. It is not a full benchmark, not a final speedup claim, not a final quality claim, and not a default GPU switch.

Task100B ran no:

- large CPU `n=100`
- Baseline-AR
- DFlash-R1 runtime job
- full matrix
- QMSum run
- keep-rate tuning
- default config change
- model download
- LLM judge

## 2. Setup

Run scope:

- condition: `CC-DFlash-R2`
- prompt source: `dataset`
- dataset: `gsm8k_short`
- seed: `42`
- `n`: `100`
- warmup prompts: `0`
- `max_new_tokens`: `256`
- generated text stored: yes
- resume mode: yes
- compressor profile: `light`
- compressor placement: runtime-only `--compressor-device-map cuda`

The default config remains CPU for the light compressor. GPU placement was requested only by runtime override.

Command shape:

```bash
PYTHONPATH=src .venv/bin/python scripts/run_mvp.py \
  --condition CC-DFlash-R2 \
  --prompt-source dataset \
  --dataset gsm8k_short \
  --seed 42 \
  --n 100 \
  --warmup-prompts 0 \
  --max-new-tokens 256 \
  --store-generated-text \
  --resume \
  --compressor-profile light \
  --compressor-device-map cuda \
  --output results/phase_2_system_optimization/final_reruns/task100b_light_gpu_n100_controlled_run/runs/20260621_1555_cc_dflash_r2_light_gpu_seed42_n100_mnt256.jsonl
```

## 3. GPU Gate

CUDA was verified in the agent shell before the run:

- `nvidia-smi`: PASS
- NVIDIA driver: `595.71.05`
- CUDA from `nvidia-smi`: `13.2`
- `CUDA_VISIBLE_DEVICES`: `None`
- torch: `2.5.1+cu121`
- torch CUDA: `12.1`
- `torch.cuda.is_available()`: `True`
- GPU: `NVIDIA GeForce RTX 4070 Laptop GPU`
- initial torch allocated/reserved: `0.0 MiB` / `0.0 MiB`

No CPU fallback was used.

## 4. Artifacts

Run artifact:

- `results/phase_2_system_optimization/final_reruns/task100b_light_gpu_n100_controlled_run/runs/20260621_1555_cc_dflash_r2_light_gpu_seed42_n100_mnt256.jsonl`

Analyzer artifacts:

- `results/phase_2_system_optimization/final_reruns/task100b_light_gpu_n100_controlled_run/summary/task100b_light_gpu_n100_summary.json`
- `results/phase_2_system_optimization/final_reruns/task100b_light_gpu_n100_controlled_run/summary/task100b_recommendation.json`
- `results/phase_2_system_optimization/final_reruns/task100b_light_gpu_n100_controlled_run/summary/task100b_row_labels.jsonl`
- `results/phase_2_system_optimization/final_reruns/task100b_light_gpu_n100_controlled_run/summary/task100b_reference_comparison.json`
- `results/phase_2_system_optimization/final_reruns/task100b_light_gpu_n100_controlled_run/tables/task100b_light_gpu_n100_table.csv`

Analyzer script and tests:

- `scripts/phase_2_system_optimization/analysis/task100b_light_gpu_n100_controlled_run.py`
- `tests/test_task100b_light_gpu_n100_controlled_run.py`

## 5. Results

Task100B Light GPU n100:

- row count: `100/100`
- calibrated strict: `79/100`
- cap-limited incomplete: `15/100`
- final-answer marker present: `85/100`
- strict wrong numeric: `6/100`
- answer missing: `0/100`
- proxy uncertain: `0/100`
- exact containment diagnostic count: `83/100`
- average `t_compress_ms`: `17.35`
- average e2e time: `2.88s`
- average tokens/sec: `59.83`
- average `tau_mean`: `5.63`
- average `R_actual`: `2.00`
- max VRAM allocated: `4.16GiB`
- max VRAM reserved: `4.43GiB`
- OOM/CUDA failure flags: none recorded

Metadata confirmed:

- `compressor_profile`: `light`
- `compressor_device_map`: `cuda`
- `requested_compressor_device_map`: `cuda`
- `local_files_only`: `true`

## 6. Reference Comparisons

### Versus Task99-R Light GPU n10

Task99-R Light GPU n10:

- strict: `8/10`
- cap-limited incomplete: `1/10`
- average `t_compress_ms`: `25.57`
- average e2e: `2.67s`
- average tok/s: `62.74`
- max reserved VRAM: about `4.37GiB`

Task100B Light GPU n100:

- strict: `79/100`
- cap-limited incomplete: `15/100`
- average `t_compress_ms`: `17.35`
- average e2e: `2.88s`
- average tok/s: `59.83`
- max reserved VRAM: `4.43GiB`

This is a bounded scale-up comparison because `n=10` and `n=100` differ. Relative to Task99-R, Task100B had strict-rate delta `-0.01`, cap-limited-rate delta `+0.05`, `t_compress_ms` delta `-8.22ms`, e2e delta `+0.21s`, and tok/s delta `-2.91`.

### Versus Task96 Light CPU n30

Task96 Light CPU n30:

- strict: `22/30`
- cap-limited incomplete: `5/30`
- average `t_compress_ms`: `363.46`
- average e2e: `3.23s`
- average tok/s: `59.76`
- average `R_actual`: `2.00`

Task100B Light GPU n100:

- strict: `79/100`
- cap-limited incomplete: `15/100`
- average `t_compress_ms`: `17.35`
- average e2e: `2.88s`
- average tok/s: `59.83`
- average `R_actual`: `2.00`

This is a bounded reference comparison because sample size differs. Rate deltas versus Task96 Light CPU were strict `+0.0567` and cap-limited `-0.0167`. Runtime deltas were `t_compress_ms -346.11ms`, e2e `-0.35s`, and tok/s `+0.07`.

### Versus Task96 Large CPU n30

Task96 Large CPU n30:

- strict: `22/30`
- cap-limited incomplete: `5/30`
- average `t_compress_ms`: `1201.58`
- average e2e: `3.97s`
- average tok/s: `58.29`
- average `R_actual`: `2.67`

Task100B Light GPU n100 was lower on average compression time by `1184.23ms`, lower e2e by `1.09s`, and slightly higher tok/s by `1.53`, with the same sample-size caveat.

### Versus Task88 DFlash-R1 Historical Reference

Task88 DFlash-R1 remains historical-only:

- Task88 used `n=30`
- Task88 used `max_new_tokens=512`
- Task100B used `n=100`
- Task100B used `max_new_tokens=256`

Do not treat this as an apples-to-apples comparison.

## 7. Interpretation

Task100B supports the bounded claim that the Light GPU placement candidate scaled from Task99-R `n=10` to `n=100` in this CUDA-visible shell without observed OOM/CUDA failure fields.

The result is favorable for the next optimization question:

- compression overhead stayed very low compared with Task96 Light CPU
- e2e remained lower than the Task96 Light CPU reference
- VRAM remained bounded in the observed run, with max reserved VRAM `4.43GiB`
- calibrated strict and cap-limited rates stayed within the bounded caveat thresholds used by the analyzer

The result still does not finish the full benchmark story:

- Task100B is one condition only
- Task96 CPU references are `n=30`, not equal-setting `n=100`
- DFlash-R1 is historical-only here
- no QMSum run was performed
- no full matrix was performed
- no final speedup, correctness, deployment, or 8GB readiness claim is supported

## 8. Decision

Decision: **PASS_WITH_CAVEAT**.

Reason:

- CUDA gate passed
- the single authorized Light GPU `n=100` run completed `100/100` rows
- metadata confirmed light compressor CUDA placement
- no OOM/CUDA failure fields were recorded
- calibrated strict proxy was `79/100`
- cap-limited incomplete was `15/100`
- average compression overhead remained far below Task96 Light CPU
- average e2e remained favorable relative to Task96 Light CPU
- claim boundaries were preserved

## 9. Recommendation

Proceed to **T100C - Optimization Gap Analysis**.

T100C should inspect:

- cap-limited rows
- strict wrong numeric rows
- slowest rows
- VRAM headroom and prompt-shape sensitivity
- whether Light GPU remains a candidate under bounded constraints

Do not automatically:

- switch GPU placement on by default
- run a full matrix
- run QMSum
- run large CPU `n=100`
- claim final speedup, final quality, deployment readiness, or 8GB readiness

## 10. Claim Boundary

Supported bounded claims:

- Light GPU placement completed one controlled `n=100` GSM8K mnt256 run in this CUDA-visible shell.
- The run used `CC-DFlash-R2`, the light compressor, and runtime `--compressor-device-map cuda`.
- The run completed `100/100` rows without recorded OOM/CUDA failure fields.
- The run had lower average `t_compress_ms` than the Task96 Light CPU and Large CPU references.
- The run had favorable bounded e2e compared with Task96 Light CPU and Large CPU references.

Blocked claims:

- no final speedup claim
- no final quality claim
- no deployment or 8GB readiness claim
- no QMSum semantic correctness claim
- no full benchmark claim
- no default GPU switch
- no claim that DFlash-R1 is broken
- no claim that Task96 references are apples-to-apples `n=100` comparisons
