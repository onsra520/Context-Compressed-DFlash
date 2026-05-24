# Phase 1.3 CUDA Runtime Verification

## Summary

Phase 1.3 passed. CUDA llama.cpp runtime is available, diagnostics now recognize CUDA backend evidence from `llama_print_system_info()`, and Gemma E2B reports `device_status: ok` when configured for CUDA with `n_gpu_layers: -1`.

## CUDA Build Evidence

Verified `llama-cpp-python` version: `0.3.23`.

Observed CUDA indicators:

- `ggml_cuda_init: found 1 CUDA devices`
- `Device 0: NVIDIA GeForce RTX 4070 Laptop GPU, compute capability 8.9`
- `CUDA : ARCHS = 890`
- Gemma load reported layers assigned to `CUDA0`.
- Gemma load reported `offloaded 36/36 layers to GPU`.
- Runtime logs reported `CUDA0 compute buffer`, `CUDA_Host compute buffer`, and CUDA graph reuse/warmup.

## Runtime Policy

- Qwen3-0.6B: `expected_device: cpu`, `n_gpu_layers: 0`
- Gemma E2B: `expected_device: cuda`, `n_gpu_layers: -1`
- Gemma E4B: `expected_device: cuda`, `n_gpu_layers: -1`, optional

## Qwen Device Result

Qwen remains configured for CPU:

- `qwen_expected_device: cpu`
- `qwen_n_gpu_layers: 0`
- `qwen_device_status: ok`

The pair smoke confirmed Qwen layers were assigned to CPU.

## Gemma E2B Device Result

Gemma E2B is configured for CUDA and now reports a satisfied device policy:

- `gemma_expected_device: cuda`
- `gemma_n_gpu_layers: -1`
- `gemma_device_status: ok`

The Gemma smoke generated non-empty text and reported `device_status: ok`.

## Pair Smoke Result

Pair smoke completed successfully:

- `bridge_status: valid`
- `fallback_count: 0`
- `draft_valid_count: 1`
- `draft_rejected_count: 0`
- `qwen_device_status: ok`
- `gemma_device_status: ok`

No speculative acceptance, equivalence, or benchmark speedup claims were made.

## Tests

Targeted diagnostics/config tests passed:

- `tests/test_runtime_diagnostics.py`
- `tests/test_config.py`

Full suite passed:

- `.venv/bin/pytest -v`

Forbidden-claim scan passed with no matches for benchmark, equivalence, or unsupported runtime-path claims.

`pyproject.toml` keeps main dependencies lightweight and does not include `llama-cpp-python` in the main dependency list. The CPU package remains isolated under the `gguf-cpu` optional extra.

## Remaining Issues

- Diagnostics still use conservative CUDA policy inference before model load. Deeper per-model layer-offload parsing can be added later if llama.cpp exposes structured placement data through Python.
- Gemma E4B remains optional and missing for the current low-tier smoke path.
- This phase verifies runtime placement only; it does not benchmark.

## Conclusion

- `policy_configured = yes`
- `policy_satisfied = yes`

Phase 1.3 is passed: CUDA runtime is available, Gemma CUDA policy is satisfied, and the previous `gemma_device_status: unknown` bug is fixed.

## Next Step

Run a small controlled low-tier runtime trace with Qwen on CPU and Gemma on CUDA, still without benchmark claims, to verify trace fields and fallback accounting under the intended device policy.
