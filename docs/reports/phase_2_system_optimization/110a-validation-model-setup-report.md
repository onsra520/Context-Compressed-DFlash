# Task 110A — Validation Model Setup and Config Wiring

**Date**: 2026-06-26
**Condition**: Local validation setup
**Environment**: RTX 4070 Laptop GPU (8GB VRAM), 64GB RAM, Core i9 13th gen

## 1. Purpose
Following the T108B QMSum targeted repair mixed signal (0 proxy-improved, 2 safer-but-uninformative, 4 unchanged), QMSum requires formal semantic validation. To preserve independence and ensure rigorous judgment, a stronger local validation model is configured. This task wires the `llama_cpp` engine and `config.yml` to support a local quantized judge model without modifying the target/draft generative models.

## 2. Environment Check
A preflight check confirmed `llama_cpp` is correctly installed and importable locally. The working branch is `main` and the workspace is clean.

## 3. Config Changes
A top-level `validation_model` block was added to `config.yml`. The validation judge is disabled by default (`enabled: false`) to strictly prevent unintended activation during unrelated runs. The block correctly configures the `llama_cpp` engine with the necessary runtime parameters and lists the exact target semantic dimension arrays (e.g., `evidence_support`, `completeness`, `reference_consistency`, `hallucination`) for future validation tasks.

## 4. Downloaded Validation Model
- **Repo**: `unsloth/Qwen3.5-9B-GGUF`
- **Filename**: `Qwen3.5-9B-UD-Q4_K_XL.gguf`
- **Path**: `models/validation/Qwen3.5-9B-GGUF/Qwen3.5-9B-UD-Q4_K_XL.gguf`
- **Size**: 5.5564 GiB
The model was successfully downloaded via `huggingface-cli` using symlinks disabled to drop it directly in the workspace.

## 5. Why Validation Model is Separate
The validation judge is deliberately separated from the `Qwen3-4B` and `Qwen3-4B-DFlash-b16` generative target/draft models. This isolation prevents the "grading its own homework" bias and provides higher-capacity reasoning (9B parameter model) for semantic nuance, while remaining within the constraints of an 8GB VRAM local GPU through 4-bit quantization.

## 6. Light Compressor GPU Config Update
The config for `compression.light_llmlingua.device_map` was successfully updated from `cpu` to `cuda`. This wires the optimized light compressor path to leverage the GPU during future inference.

## 7. Scope Confirmation
- **No benchmark or generation**: Setup only.
- **No default switch**: Disabled in config and analyzer.
- **Git Hygiene**: The validation model binaries are untracked and purposefully excluded from commits. 

## 8. Next Task
**T110B — QMSum Judge Protocol / Smoke Validation**
Proceed to test the judge prompt and output extraction format using the newly downloaded validation model.
