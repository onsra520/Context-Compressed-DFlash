# Task99 — Light Compressor GPU Placement Feasibility

## 1. Purpose

Task99 tested whether the validated Phase 2 light LLMLingua compressor could be placed on GPU in the real `CC-DFlash-R2` path without changing the default CPU configuration.

This task intentionally skipped automatic `n=100` expansion. After Task96 and Task97, the project already had enough bounded CPU-path evidence to redirect the next optimization question toward GPU-placement feasibility instead of scaling sample count.

Task99 scope remained bounded:

- no `n=30`
- no `n=100`
- no full benchmark
- no QMSum run
- no keep-rate tuning
- no permanent config default switch

## 2. Setup

### 2.1 Hardware / GPU gate

Task99 required a positive CUDA gate before any smoke benchmark:

- `nvidia-smi`
- `torch.cuda.is_available()`

Observed in this exact agent shell:

- `nvidia-smi` failed to communicate with the NVIDIA driver
- `torch 2.5.1+cu121`
- `torch.cuda.is_available() == False`
- no visible CUDA device

Per task rules, the benchmark path stopped immediately after this failure. No CPU fallback was used.

### 2.2 Runtime override support

The repo did not previously expose a runtime-only compressor placement override. Task99 added the smallest safe control surface:

- `scripts/run_mvp.py --compressor-device-map`
- `LLMLinguaCompressor.from_config(..., device_map_override=...)`

This override is runtime-only:

- `config.yml` default remains CPU for both `large_llmlingua` and `light_llmlingua`
- GPU is not the default
- no permanent config switch was made

### 2.3 Metadata coverage

Task99 also extended emitted metadata so result rows can record:

- `compressor_device_map`
- `requested_compressor_device_map`
- existing compressor profile/path/local-files-only fields
- existing VRAM-related fields, when runtime rows exist

## 3. Artifacts

### 3.1 Static audit and normalized references

- `results/phase_2_system_optimization/compressor_comparison/task99_light_compressor_gpu_placement_feasibility/static_audit/task99_static_device_audit.json`
- `results/phase_2_system_optimization/compressor_comparison/task99_light_compressor_gpu_placement_feasibility/static_audit/task99_task96_light_cpu_reference.json`
- `results/phase_2_system_optimization/compressor_comparison/task99_light_compressor_gpu_placement_feasibility/static_audit/task99_task96_large_cpu_reference.json`
- `results/phase_2_system_optimization/compressor_comparison/task99_light_compressor_gpu_placement_feasibility/static_audit/task99_task88_dflash_r1_historical_reference.json`

### 3.2 Blocked smoke artifact

- `results/phase_2_system_optimization/compressor_comparison/task99_light_compressor_gpu_placement_feasibility/smoke/20260621_task99_light_gpu_seed42_n3_mnt256_blocked.jsonl`

This is a blocked-run record, not a benchmark result. It exists to preserve the exact gate failure and the intended runtime metadata.

### 3.3 Analyzer outputs

- `results/phase_2_system_optimization/compressor_comparison/task99_light_compressor_gpu_placement_feasibility/summary/task99_gpu_placement_summary.json`
- `results/phase_2_system_optimization/compressor_comparison/task99_light_compressor_gpu_placement_feasibility/summary/task99_reference_comparison.json`
- `results/phase_2_system_optimization/compressor_comparison/task99_light_compressor_gpu_placement_feasibility/summary/task99_recommendation.json`
- `results/phase_2_system_optimization/compressor_comparison/task99_light_compressor_gpu_placement_feasibility/tables/task99_gpu_placement_table.csv`

## 4. Results

### 4.1 Task99 light GPU result

Runtime feasibility was blocked before smoke execution.

Observed Task99 result state:

- decision: `PARTIAL`
- requested compressor profile: `light`
- requested compressor device map: `cuda`
- resolved runtime benchmark rows: none
- smoke pass: no
- `n=10` run: not executed

### 4.2 Comparison to Task96 light CPU reference

Task96 light CPU remains the best controlled CPU-path reference:

- strict: `22/30`
- cap-limited incomplete: `5/30`
- `t_compress_ms`: `363.46`
- e2e: `3.23s`
- `R_actual`: `2.00`

Task99 produced no measured GPU runtime rows, so this comparison is packaging-only. No valid timing or quality delta was measured.

### 4.3 Comparison to Task96 large CPU reference

Task96 large CPU remains the closest controlled large-profile comparator:

- strict: `22/30`
- cap-limited incomplete: `5/30`
- `t_compress_ms`: `1201.58`
- e2e: `3.97s`
- `R_actual`: `2.67`

Again, Task99 produced no measured GPU runtime rows, so no valid light-GPU versus large-CPU delta was measured.

### 4.4 Comparison to DFlash-R1 historical reference

Task99 mapped the historical reference to the canonical repo condition `DFlash-R1`.

The current best historical reference is Task88:

- artifact family: `results/phase_1_system_build_and_evaluation/final_reruns/task88_*`
- condition: `DFlash-R1`
- dataset: `gsm8k_short`
- `n=30`
- `max_new_tokens=512`

This is historical-only and not apples-to-apples with Task99/Task96 because the benchmark framing and `max_new_tokens` policy differ.

## 5. Interpretation

Task99 answered the static engineering question, but not the runtime performance question.

Supported from this task:

- the light compressor now has a runtime-only GPU placement override
- the default CPU config remains unchanged
- emitted metadata is sufficient to audit requested/resolved compressor placement
- Task96 light CPU and large CPU remain the active controlled references
- Task88 DFlash-R1 can be packaged as a historical-only reference

Not supported from this task:

- GPU placement is feasible on the current 8GB RTX 4070 Laptop GPU
- GPU placement improves `t_compress_ms`
- GPU placement improves e2e latency
- GPU placement avoids VRAM pressure or OOM under real runtime load

Those claims remain unproven because this shell never passed the CUDA gate.

## 6. Decision

`PARTIAL`

Reason:

- static audit completed
- runtime-only override was added safely
- analyzer and reference packaging completed
- CUDA was unavailable in this agent shell, so smoke execution never started

## 7. Recommendation

- keep the Task96 light CPU path as the supported controlled Phase 2 result
- treat GPU placement as experimental / unproven
- do not switch the compressor to GPU by default
- do not auto-authorize `n=100`
- if GPU feasibility remains a priority, rerun Task99 from a shell where `nvidia-smi` works and `torch.cuda.is_available()` is `True`, starting again at bounded smoke scale only
- otherwise continue to `T100 — Phase 2 Optimization Summary`

## 8. Claim Boundary

Still blocked after Task99:

- no final speedup claim
- no final quality claim
- no deployment / 8GB readiness claim
- no QMSum semantic correctness claim
- no full benchmark claim
- no claim that GPU placement is better unless a valid Task99 runtime measurement is collected

## 9. Validation

Task99 validation covered:

- targeted runtime-override tests
- targeted analyzer tests
- compile sanity
- HTML parse sanity

No model inference benchmark was run during validation.
