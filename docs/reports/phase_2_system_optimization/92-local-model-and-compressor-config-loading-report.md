# Task 92 — Local Model and Compressor Config Loading Audit

## 1. Purpose

Task92 was inserted before lighter-compressor integration because the project has shifted from relying on Hugging Face model IDs and ambient cache state to using explicit local model folders under `models/`.

This creates a real risk: a compressor profile can still look correct in config while the loader silently resolves through Hugging Face cache or network instead of the intended local project folder. Task92 hardens config and loading behavior so that later Phase 2 work measures the intended local assets.

Task92 is a config and loading audit, not a benchmark task.

## 2. Config changes

The `compression` profiles in `config.yml` were updated so both large and light LLMLingua profiles now carry explicit local-path metadata:

- `large_llmlingua.compressor_path = models/llmlingua-2-xlm-roberta-large-meetingbank`
- `light_llmlingua.compressor_path = models/llmlingua-2-bert-base-multilingual-cased-meetingbank`
- `large_llmlingua.local_files_only = true`
- `light_llmlingua.local_files_only = true`

Device defaults were also aligned with the one-GPU local runtime constraint:

- `large_llmlingua.device_map = cpu`
- `light_llmlingua.device_map = cpu`

Keeping both compressor profiles on CPU for Task92 preserves the target + draft GPU budget while the project audits path resolution. Task93 can later evaluate whether alternative compressor placement is worth testing.

## 3. Loader behavior

Task92 adds a dedicated compressor-source resolver and uses it in the LLMLingua config path.

The resulting behavior is:

- `compressor_path` is preferred when present.
- `model_name` is retained as metadata and as a backward-compatible fallback when no explicit local path is configured.
- If `compressor_path` is configured but the folder does not exist, loading fails with a clear error instead of silently drifting toward cache or network resolution.
- `local_files_only` is carried into the resolved compressor metadata and into tokenizer loading.
- Backward compatibility is preserved for configs that still provide only `model_name`.

In addition, compressed-condition row metadata now records resolved source details where available, including compressor profile, configured path, resolved local path, source kind, and local-only behavior.

## 4. Validation

Task92 validation remained static and lightweight by design:

- Static config audit of target, draft, tokenizer, and compressor paths
- Focused unit tests for local compressor source resolution
- `compileall` over `src`, `tests`, and `scripts`
- No model download
- No benchmark expansion
- No `n=30` or `n=100` run
- No speedup claim

Validated environment assumptions carried forward from Task91B:

- Python `3.12.13`
- `torch 2.5.1+cu121`
- Torch CUDA runtime `12.1`
- `transformers 4.57.3`
- `huggingface_hub 0.36.2`
- GPU: `NVIDIA GeForce RTX 4070 Laptop GPU`

Dependency correction preserved in Task92:

- `torch==2.9.1+cu121` was not the validated local setup because that wheel was not available from the CUDA 12.1 index used here.
- The validated torch version remains `2.5.1+cu121`.
- `huggingface_hub` remains pinned effectively to `0.36.2` because newer `1.x` releases conflict with `transformers 4.57.3`.

## 5. Artifacts

Task92 writes static config-audit artifacts to:

- `results/phase_2_system_optimization/runtime_config_audit/task92_local_model_and_compressor_config_loading/config_resolved_paths.json`
- `results/phase_2_system_optimization/runtime_config_audit/task92_local_model_and_compressor_config_loading/compressor_profile_resolution.json`
- `results/phase_2_system_optimization/runtime_config_audit/task92_local_model_and_compressor_config_loading/task92_validation_summary.json`

These artifacts are small and safe to commit because they contain only config-resolution and validation-summary data, not benchmark outputs.

## 6. Task93 handoff

Task93 should now perform the actual lighter-compressor integration and evaluation step using:

- Candidate lighter compressor: `microsoft/llmlingua-2-bert-base-multilingual-cased-meetingbank`
- Local path: `models/llmlingua-2-bert-base-multilingual-cased-meetingbank`

Task93 should compare that profile against the current large compressor:

- `models/llmlingua-2-xlm-roberta-large-meetingbank`

Task93 goals:

- Reduce `T_compress`
- Preserve enough compression to stay useful
- Keep the quality proxy near Baseline-AR
- Improve end-to-end feasibility without making final benchmark claims

## 7. Claim boundary

- No final benchmark claim
- No final speedup claim
- No deployment or confirmed 8GB claim
- No QMSum semantic correctness claim
- Task92 verifies config and loading behavior only

## 8. Understand-Anything refresh

`.understand-anything/meta.json` was read before the task. Understand-Anything refresh was skipped because `/understand` is not available in this environment, and `/understand-diff` was also not available. `.understand-anything/meta.json` was not modified by Task92.
