# Phase 1.1 Prompt Formatting Fix

## Summary

Phase 1.1 passed.

The default Gemma smoke command now uses llama.cpp chat completion with the
model-provided GGUF chat template instead of sending a raw prompt string. The
default command produced non-empty text without a manually formatted prompt.
Qwen smoke also defaults to chat-style generation, while `--prompt-mode raw`
remains available for debugging.

## What Changed

- Added `LlamaCppBackend.generate_chat(...)` for llama.cpp chat-template based generation.
- Updated `smoke_gemma.py` to default to `--prompt-mode chat` with a user message.
- Updated `smoke_qwen.py` to default to `--prompt-mode chat`.
- Added `src/htfsd/tokenization/prompt_adapter.py` as a manual fallback formatter for `gemma`, `qwen`, and `raw`.
- Preserved `--prompt-mode raw` for debugging old raw-completion behavior.
- Reworded the Phase 1 report and tests so the forbidden-claim scan has no matches.

## Gemma Default Smoke Result

- Command: `.venv/bin/python scripts/smoke_gemma.py`
- Status: passed
- Prompt mode: `chat`
- Model file: `models/gemma-4-e2b-it/gemma-4-E2B-it-UD-Q4_K_XL.gguf`
- Latency: `6.620060` seconds
- llama.cpp prompt eval: `4.21` tokens/sec
- llama.cpp decode eval: `20.68` tokens/sec
- Output summary: generated `Hello, how are you?`

The prior empty default output was fixed without manually prepending `<bos>`.

## Qwen Smoke Result

- Command: `.venv/bin/python scripts/smoke_qwen.py`
- Status: passed
- Prompt mode: `chat`
- Model file: `models/qwen3-0.6b/Qwen3-0.6B-UD-Q8_K_XL.gguf`
- Latency: `2.100973` seconds
- llama.cpp prompt eval: `146.01` tokens/sec
- llama.cpp decode eval: `51.30` tokens/sec
- Output summary: Qwen generated non-empty draft text. The draft began with a `<think>` section, which remains important for text-bridge rejection/normalization policy.

## Pair Smoke Result

- Command: `.venv/bin/python scripts/smoke_gguf_pair.py`
- Status: passed
- `bridge_status`: `valid`
- `fallback_count`: `0`
- `rejection_reason`: `None`
- `draft_valid_count`: `1`
- `draft_rejected_count`: `0`
- `latency_seconds`: `4.651524`
- `qwen_decode_tokens_per_second`: `35.91058630523257`
- `gemma_decode_tokens_per_second`: `7.3189574350530995`

Pair smoke remains a bridge/runtime check only. It does not claim target-model
equivalence, draft acceptance metrics, or performance speedup.

## Runtime Warnings

- Runtime remains `functional_cpu_only`; llama.cpp assigned Qwen and Gemma layers to CPU.
- No duplicate leading `<bos>` warning appeared in the default Gemma smoke after switching to chat completion.
- llama.cpp still prints verbose model metadata and chat templates.
- Context windows remain configured at `n_ctx=2048`, below the training context for both models.

## Tests

- `.venv/bin/pytest -v`: passed, `43 passed`.
- Forbidden-claim scan across `pyproject.toml`, `src`, `tests`, `scripts`, `configs`, `README.md`, and `docs`: passed with no matches.

## Remaining Issues

- Qwen chat output can include `<think>` sections. This is expected for Qwen3-style behavior and should continue to be handled by `text_bridge`.
- The pair smoke path still uses raw generation internally. That is acceptable for the current bridge/runtime smoke scope, but a later phase may want a shared generation-mode policy.
- Runtime is CPU-only in this environment.

## Conclusion

Phase 1.1 passed. The default Gemma GGUF smoke command now produces non-empty
text through model-aware chat formatting, and the project remains within the
GGUF / llama.cpp runtime path.
