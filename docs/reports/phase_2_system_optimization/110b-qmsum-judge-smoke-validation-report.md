# Task 110B — QMSum Judge Protocol / Smoke Validation

**Date**: 2026-06-26
**Condition**: Local validation smoke run
**Environment**: RTX 4070 Laptop GPU (8GB VRAM)
**Validation Model**: `unsloth/Qwen3.5-9B-GGUF` (UD-Q4_K_XL), `llama_cpp` engine

## 1. Purpose
This task smoke-tests the local Qwen3.5-9B GGUF judge configured in T110A to ensure it can successfully evaluate QMSum summaries and emit perfectly formatted JSON without out-of-memory (OOM) crashes. This verifies the validation infrastructure before attempting a full calibration or label run.

## 2. Load Status & Runtime
The validation model loaded successfully via `llama_cpp` under conservative default settings:
- **Status**: Loaded
- **Context Window (`n_ctx`)**: 8192
- **GPU Layers (`n_gpu_layers`)**: -1 (All layers offloaded to GPU)

## 3. JSON Parsing & Protocol Smoke Test
A tiny sample size of exactly two targeted QMSum rows was provided to the judge model. Each was evaluated on strict dimensions (evidence support, completeness, reference consistency, hallucination).
- **Rows Judged**: 2
- **Valid JSON Generated**: 2
- **JSON Repair Fallback Triggered**: 0
The judge model followed the prompt perfectly, returning strictly bounded JSON outputs without conversational prefix/suffix noise. The parser extracted the labels successfully.

## 4. Constraint & Scope Compliance
- No benchmark iterations or model inferences using target/draft generator models were executed.
- QMSum semantic correctness **remains unclaimed**. This smoke test merely confirmed pipeline feasibility, not generation quality.
- The default pipeline switch remains strictly unauthorized.

## 5. Next Task
**T110C — QMSum Judge Calibration / Targeted Label Run**
With the judge pipeline validated (`SMOKE_READY`), the next step is to evaluate the full set of QMSum target rows to resolve residual semantic risks.
