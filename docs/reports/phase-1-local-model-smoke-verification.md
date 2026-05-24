# Phase 1 Local Model Smoke Verification

## Summary

Phase 1 is partially passed.

Real local GGUF model files were downloaded, discovered, loaded, and exercised
with `llama-cpp-python`. Qwen generated draft text successfully. Gemma E2B
loaded successfully, and a supplemental chat-formatted prompt produced text.
The required default `smoke_gemma.py` command exited successfully, but its raw
default prompt produced an empty continuation, so the Gemma smoke path should be
tightened before treating it as a complete generation proof.

The Qwen -> Gemma E2B pair smoke path passed with `bridge_status: valid` and no
fallback. This is only a bridge/runtime smoke result, not speculative decoding
acceptance.

## Environment

- Project path: `/home/seggss/HTFS-Decoding`
- Python: `3.12.3`
- Python executable: `/home/seggss/HTFS-Decoding/.venv/bin/python`
- OS: WSL2 Linux, `Linux-6.6.114.1-microsoft-standard-WSL2-x86_64-with-glibc2.39`
- Backend: `llama_cpp`
- `llama_cpp` import status: ok
- `llama-cpp-python`: `0.3.23`
- `uv`: not available on PATH during this phase
- Runtime mode observed: `functional_cpu_only`

The llama.cpp logs showed all Qwen and Gemma layers assigned to CPU. No CUDA or
GPU backend was observed.

## Model Files

- Qwen drafter folder: `models/qwen3-0.6b`
- Qwen selected GGUF: `models/qwen3-0.6b/Qwen3-0.6B-UD-Q8_K_XL.gguf`
- Qwen source: `unsloth/Qwen3-0.6B-GGUF`
- Qwen file size on disk: `844288704` bytes
- Qwen llama.cpp file type: `Q8_0`

- Gemma E2B folder: `models/gemma-4-e2b-it`
- Gemma E2B selected GGUF: `models/gemma-4-e2b-it/gemma-4-E2B-it-UD-Q4_K_XL.gguf`
- Gemma E2B source: `unsloth/gemma-4-E2B-it-GGUF`
- Gemma E2B file size on disk: `3184494720` bytes
- Gemma E2B llama.cpp file type: `Q4_K - Medium`

- Gemma E4B folder: `models/gemma-4-e4b-it`
- Gemma E4B selected file: none
- Gemma E4B status: optional missing for this phase

No `configs/local.example.yaml` model filename override was needed because each
required model folder contains exactly one `.gguf` file.

## Commands Run

- `find ~/HTFS-Decoding -type f -name "*.gguf" -print`: passed; initially found no local GGUF files.
- `curl -L --fail --continue-at - --output models/qwen3-0.6b/Qwen3-0.6B-UD-Q8_K_XL.gguf https://huggingface.co/unsloth/Qwen3-0.6B-GGUF/resolve/main/Qwen3-0.6B-UD-Q8_K_XL.gguf`: passed.
- `curl -L --fail --continue-at - --output models/gemma-4-e2b-it/gemma-4-E2B-it-UD-Q4_K_XL.gguf https://huggingface.co/unsloth/gemma-4-E2B-it-GGUF/resolve/main/gemma-4-E2B-it-UD-Q4_K_XL.gguf`: passed.
- `.venv/bin/python scripts/check_env.py`: passed.
- `.venv/bin/python scripts/smoke_qwen.py`: passed.
- `.venv/bin/python scripts/smoke_gemma.py`: passed with empty generated text.
- `.venv/bin/python scripts/smoke_gemma.py --prompt '<bos><|turn>user\nWrite a five word greeting.<turn|>\n<|turn>model\n'`: passed and generated text.
- `.venv/bin/python scripts/smoke_gguf_pair.py`: passed.
- `.venv/bin/pytest -v`: passed, `38 passed`.

Captured command logs were written under `logs/reports/` and are intentionally
not committed.

## Qwen Smoke Result

- Command: `.venv/bin/python scripts/smoke_qwen.py`
- Status: passed
- Model file: `models/qwen3-0.6b/Qwen3-0.6B-UD-Q8_K_XL.gguf`
- Latency: `4.756125` seconds
- llama.cpp prompt eval: `3.60` tokens/sec
- llama.cpp decode eval: `32.51` tokens/sec
- Output summary: Qwen generated a multi-sentence draft about speculative decoding.

## Gemma E2B Smoke Result

- Command: `.venv/bin/python scripts/smoke_gemma.py`
- Status: command passed, generation proof incomplete
- Model file: `models/gemma-4-e2b-it/gemma-4-E2B-it-UD-Q4_K_XL.gguf`
- Latency: `7.939687` seconds
- llama.cpp prompt eval: `1.35` tokens/sec
- llama.cpp decode eval: one immediate run with empty text
- Output summary: default raw prompt produced an empty continuation.

Supplemental check:

- Command: `.venv/bin/python scripts/smoke_gemma.py --prompt '<bos><|turn>user\nWrite a five word greeting.<turn|>\n<|turn>model\n'`
- Status: passed
- Latency: `8.698199` seconds
- llama.cpp prompt eval: `2.51` tokens/sec
- llama.cpp decode eval: `16.08` tokens/sec
- Output summary: generated `Hello, how are you?`

This suggests the Gemma model/runtime is functional, but the smoke command
should use the model chat template or a better default prompt.

## Pair Smoke Result

- Command: `.venv/bin/python scripts/smoke_gguf_pair.py`
- Status: passed
- `bridge_status`: `valid`
- `fallback_count`: `0`
- `rejection_reason`: `None`
- `draft_valid_count`: `1`
- `draft_rejected_count`: `0`
- `latency_seconds`: `13.409611`
- `qwen_decode_tokens_per_second`: `11.849356094388371`
- `gemma_decode_tokens_per_second`: `2.622228078754627`
- Output summary: Qwen produced draft text, the text bridge marked it valid, and Gemma E2B generated a continuation from the combined prompt.

No speculative acceptance rate, target-model equivalence, or speedup claim was
measured or reported.

## Runtime Warnings

- Qwen and Gemma layers were assigned to CPU. Runtime is therefore
  `functional_cpu_only`.
- Qwen context log: `n_ctx_seq (2048) < n_ctx_train (40960) -- the full capacity of the model will not be utilized`.
- Gemma context log: `n_ctx_seq (2048) < n_ctx_train (131072) -- the full capacity of the model will not be utilized`.
- Supplemental Gemma chat prompt emitted a duplicate leading `<bos>` runtime warning. The next smoke-command iteration should avoid manually adding `<bos>` and instead use llama.cpp chat formatting or a prompt adapter.
- llama.cpp printed verbose model metadata and chat templates. These are not failures, but they make terminal output noisy.

## Error Reports

No markdown runtime error reports were generated under `logs/errors/` during
this phase.

## Conclusion

Phase 1 is partially passed.

The local model restoration, discovery, model loading, Qwen smoke, and pair
smoke goals passed. Gemma E2B model loading passed, and a supplemental
chat-formatted prompt verified text generation. The only blocker to calling the
phase fully passed is that the required default `smoke_gemma.py` command
produced an empty continuation with its raw prompt.

## Next Recommended Step

Update the smoke-generation path to use model-aware prompt formatting for Gemma
and Qwen. The smallest useful next step is to add a runtime prompt adapter or
chat-completion path so `python scripts/smoke_gemma.py` produces non-empty text
without requiring a manually formatted prompt.
