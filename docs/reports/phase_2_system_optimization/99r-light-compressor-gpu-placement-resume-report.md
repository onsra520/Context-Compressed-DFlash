# Task99-R — Light Compressor GPU Placement Resume

## 1. Purpose

Task99-R resumed only the missing runtime portion of Task99 after CUDA recovered in the agent shell.

Scope remained bounded:

- no `n=30`
- no `n=100`
- no full benchmark
- no QMSum run
- no keep-rate tuning
- no default config change
- no model download
- no LLM judge

## 2. GPU Gate

The CUDA gate passed before any benchmark command:

- `nvidia-smi`: PASS
- NVIDIA driver: `595.71.05`
- CUDA from `nvidia-smi`: `13.2`
- torch: `2.5.1+cu121`
- torch CUDA: `12.1`
- `torch.cuda.is_available()`: `True`
- GPU: `NVIDIA GeForce RTX 4070 Laptop GPU`
- initial torch allocated/reserved: `0.0 MiB` / `0.0 MiB`

No CPU fallback was used.

## 3. Setup

Both resume jobs used:

- condition: `CC-DFlash-R2`
- prompt source: `dataset`
- dataset: `gsm8k_short`
- seed: `42`
- warmup prompts: `0`
- `max_new_tokens`: `256`
- stored generated text: yes
- resume mode: yes
- compressor profile: `light`
- runtime compressor override: `--compressor-device-map cuda`

The default config remains CPU. GPU placement was requested only through the runtime override.

## 4. Artifacts

Smoke:

- `results/phase_2_system_optimization/compressor_comparison/task99_light_compressor_gpu_placement_feasibility/resume_gpu/smoke/20260621_133601_cc_dflash_r2_light_gpu_seed42_n3_mnt256.jsonl`

`n=10`:

- `results/phase_2_system_optimization/compressor_comparison/task99_light_compressor_gpu_placement_feasibility/resume_gpu/n10/20260621_133708_cc_dflash_r2_light_gpu_seed42_n10_mnt256.jsonl`

Summary/table:

- `results/phase_2_system_optimization/compressor_comparison/task99_light_compressor_gpu_placement_feasibility/resume_gpu/summary/task99r_gpu_placement_summary.json`
- `results/phase_2_system_optimization/compressor_comparison/task99_light_compressor_gpu_placement_feasibility/resume_gpu/summary/task99r_reference_comparison.json`
- `results/phase_2_system_optimization/compressor_comparison/task99_light_compressor_gpu_placement_feasibility/resume_gpu/summary/task99r_recommendation.json`
- `results/phase_2_system_optimization/compressor_comparison/task99_light_compressor_gpu_placement_feasibility/resume_gpu/tables/task99r_gpu_placement_table.csv`

## 5. Results

Smoke result:

- rows: `3/3`
- status: PASS
- average `t_compress_ms`: `56.98`
- average e2e: `3.20s`
- average tok/s: `54.51`
- average `tau_mean`: `5.20`
- max VRAM allocated/reserved: `4.16GiB` / `4.36GiB`

`n=10` result:

- rows: `10/10`
- status: PASS
- calibrated strict: `8/10`
- cap-limited incomplete: `1/10`
- final-answer marker present: `9/10`
- strict wrong numeric: `1/10`
- average `t_compress_ms`: `25.57`
- average e2e: `2.67s`
- average tok/s: `62.74`
- average `tau_mean`: `5.88`
- average `R_actual`: `2.00`
- average VRAM allocated/reserved: `4.16GiB` / `4.36GiB`

Metadata confirmed:

- `compressor_profile`: `light`
- `compressor_device_map`: `cuda`
- `requested_compressor_device_map`: `cuda`
- `local_files_only`: `true`
- no recorded OOM/CUDA failure fields

## 6. Comparisons

### Light GPU n10 vs Task96 light CPU n30

Task96 light CPU reference:

- strict: `22/30`
- cap-limited incomplete: `5/30`
- average `t_compress_ms`: `363.46`
- average e2e: `3.23s`
- average tok/s: `59.76`

Task99-R light GPU:

- strict: `8/10`
- cap-limited incomplete: `1/10`
- average `t_compress_ms`: `25.57`
- average e2e: `2.67s`
- average tok/s: `62.74`

Because Task99-R is `n=10` while Task96 is `n=30`, this is a bounded reference comparison, not a final equal-setting claim. Rate deltas were favorable in the bounded comparison: strict rate `+0.0667`, cap-limited rate `-0.0667`, `t_compress_ms -337.89ms`, and e2e `-0.56s`.

### Light GPU n10 vs Task96 large CPU n30

Task96 large CPU reference:

- strict: `22/30`
- cap-limited incomplete: `5/30`
- average `t_compress_ms`: `1201.58`
- average e2e: `3.97s`

Task99-R light GPU was lower in compression time by about `1176.01ms` and lower in e2e by about `1.30s`, with the same bounded sample-size caveat.

### Light GPU n10 vs DFlash-R1 historical

The DFlash reference is canonical `DFlash-R1` from Task88 and remains historical-only:

- Task88 used `n=30`
- Task88 used `max_new_tokens=512`
- Task99-R used `n=10`
- Task99-R used `max_new_tokens=256`

The comparison is not apples-to-apples and should not be used as a final system claim.

## 7. Interpretation

Task99-R shows that light-compressor GPU placement is feasible at bounded smoke and `n=10` scale in this CUDA-visible shell. The run did not show OOM or repeated CUDA instability, and it recorded materially lower compression overhead than the Task96 CPU references.

The result is still bounded:

- Task99-R is `n=10`, not `n=30`
- Task96 CPU evidence remains the stronger controlled quality baseline
- no default GPU switch is justified
- no deployment or 8GB readiness claim is justified

## 8. Decision

Decision: **PASS_WITH_CAVEAT**.

Reason:

- CUDA gate passed
- `n=3` smoke passed
- `n=10` passed
- metadata confirmed light compressor CUDA placement
- no OOM/CUDA failure fields were recorded
- bounded quality proxy stayed favorable relative to Task96 rates
- compression overhead improved strongly in the bounded comparison

## 9. Recommendation

- continue to `T100 — Phase 2 Optimization Summary`
- keep Task96 light CPU as the supported controlled baseline
- treat light GPU placement as a promising bounded candidate
- do not switch GPU placement on by default
- do not auto-authorize `n=100`
- any future GPU follow-up should remain explicitly gated

## 10. Claim Boundary

Still not claimed:

- no final speedup claim
- no final quality claim
- no deployment or 8GB readiness claim
- no QMSum semantic correctness claim
- no full benchmark claim
- no automatic `n=100` authorization
