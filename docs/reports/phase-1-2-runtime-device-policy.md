# Phase 1.2 Runtime Device Policy

## Summary

Phase 1.2 partially passed.

The runtime device policy is now explicit in config and diagnostics:

- Qwen drafter is configured for CPU with `n_gpu_layers=0`.
- Gemma E2B is configured for CUDA with `n_gpu_layers=-1`.
- Gemma E4B is configured for CUDA with `n_gpu_layers=-1` and remains optional.

The policy is configured and visible in smoke output. It is not satisfied for
Gemma on this machine because the installed `llama-cpp-python` reports that GPU
offload is unavailable.

## Runtime Policy

```text
qwen_drafter:
  expected_device = cpu
  n_gpu_layers = 0

gemma_e2b:
  expected_device = cuda
  n_gpu_layers = -1

gemma_e4b:
  expected_device = cuda
  n_gpu_layers = -1
  optional = true
```

Allowed device status values now include:

- `ok`
- `functional_cpu_only`
- `device_policy_mismatch`
- `cuda_backend_unavailable`
- `unknown`
- `optional_missing`

## Config Changes

`configs/local.example.yaml` now has per-model runtime fields:

- `expected_device`
- `n_gpu_layers`
- `optional`

The global `runtime.n_gpu_layers` field was removed from the example config.
Directory-based GGUF discovery remains unchanged.

## Qwen Device Result

- Command: `.venv/bin/python scripts/smoke_qwen.py`
- Status: passed
- Model file: `models/qwen3-0.6b/Qwen3-0.6B-UD-Q8_K_XL.gguf`
- `expected_device`: `cpu`
- `n_gpu_layers`: `0`
- Observed llama.cpp logs: Qwen layers assigned to CPU
- Device policy result: `ok`
- Latency from captured run: `79.702568` seconds

## Gemma E2B Device Result

- Command: `.venv/bin/python scripts/smoke_gemma.py`
- Status: passed as debug smoke
- Model file: `models/gemma-4-e2b-it/gemma-4-E2B-it-UD-Q4_K_XL.gguf`
- `expected_device`: `cuda`
- `n_gpu_layers`: `-1`
- `device_status`: `cuda_backend_unavailable`
- Output warning: `Gemma expected CUDA but runtime appears CPU-only (cuda_backend_unavailable).`
- Observed llama.cpp logs: Gemma layers assigned to CPU
- Latency from captured run: `71.951701` seconds
- Generated text: `Hello, how are you?`

## Pair Smoke Device Result

- Command: `.venv/bin/python scripts/smoke_gguf_pair.py`
- Status: passed as debug smoke
- Qwen policy: `expected_device=cpu`, `n_gpu_layers=0`, `device_status=ok`
- Gemma policy: `expected_device=cuda`, `n_gpu_layers=-1`, `device_status=cuda_backend_unavailable`
- Output warning: `Gemma expected CUDA but runtime appears CPU-only (cuda_backend_unavailable).`
- `bridge_status`: `valid`
- `fallback_count`: `0`
- `latency_seconds`: `86.998679`
- `qwen_decode_tokens_per_second`: `0.8132914080641248`
- `gemma_decode_tokens_per_second`: `2.5282684695306936`

This remains a bridge/runtime smoke result only.

## CUDA / GPU Backend Status

- `llama_cpp` import status: ok
- `llama_cpp.llama_supports_gpu_offload()`: `False`
- Runtime classification: `functional_cpu_only`
- Gemma device policy status: `cuda_backend_unavailable`

No error report was generated because CUDA absence is now represented as
structured runtime status, not an unexpected exception.

## Tests

- `.venv/bin/pytest -v`: passed, `48 passed`
- Forbidden-claim/runtime-path scan across `pyproject.toml`, `src`, `tests`, `scripts`, `configs`, `README.md`, and `docs`: passed with no matches.

## Remaining Issues

- Gemma E2B is not using CUDA in the current environment.
- The installed `llama-cpp-python` appears to be CPU-only.
- Real benchmark runs should not proceed until Gemma CUDA offload is available
  and diagnostics report the policy as satisfied.
- Qwen still emits `<think>` content in chat-mode smoke output; this remains a
  text-bridge concern.

## Conclusion

```text
policy_configured = yes
policy_satisfied = no
reason = cuda_backend_unavailable
```

Phase 1.2 configured and verified the intended policy, but the current runtime
does not satisfy the Gemma CUDA requirement.

## Next Step

Reinstall or rebuild `llama-cpp-python` with CUDA/cuBLAS support in the WSL
environment, then rerun:

```bash
python scripts/check_env.py
python scripts/smoke_gemma.py
python scripts/smoke_gguf_pair.py
```

The target result is for Gemma E2B to report CUDA offload available and for the
Gemma device status to become `ok`.
