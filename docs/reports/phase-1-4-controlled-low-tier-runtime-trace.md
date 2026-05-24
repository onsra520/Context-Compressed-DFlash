# Phase 1.4 Controlled Low-Tier Runtime Trace

## Summary

Phase 1.4 passed. A controlled low-tier trace ran three fixed prompts through the existing Qwen-to-Gemma pair smoke path with Qwen on CPU and Gemma E2B on CUDA. The trace records compact metadata, bridge status, fallback accounting, runtime policy fields, and latency fields without storing long raw prompt or output text.

## Runtime Policy

- Qwen3-0.6B: `expected_device = cpu`, `n_gpu_layers = 0`, `device_status = ok`
- Gemma E2B: `expected_device = cuda`, `n_gpu_layers = -1`, `device_status = ok`
- Gemma E4B remains optional for the current low-tier path.

## Prompt Set

The default controlled trace uses three short validation prompts:

1. Explain speculative decoding in one short sentence.
2. Write a five word greeting.
3. List two benefits of GPU inference.

## Trace Fields Verified

The trace records:

- `prompt_id`
- `prompt_hash`
- `prompt_summary`
- `qwen_model_file`
- `gemma_model_file`
- `qwen_expected_device`
- `gemma_expected_device`
- `qwen_device_status`
- `gemma_device_status`
- `qwen_n_gpu_layers`
- `gemma_n_gpu_layers`
- `bridge_status`
- `rejection_reason`
- `fallback_count`
- `draft_valid_count`
- `draft_rejected_count`
- `latency_seconds`
- `qwen_decode_tokens_per_second`
- `gemma_decode_tokens_per_second`
- `qwen_output_summary`
- `gemma_output_summary`

Long raw output fields are not included by default.

## Trace Results

Trace file:

- `logs/reports/20260524T130312Z-low-tier-trace.json`

Observed records:

| Prompt | Bridge | Fallbacks | Rejection Reason | Qwen Device | Gemma Device | Latency Seconds |
|---|---|---:|---|---|---|---:|
| `trace-001` | valid | 0 | None | ok | ok | 5.311 |
| `trace-002` | valid | 0 | None | ok | ok | 1.687 |
| `trace-003` | valid | 0 | None | ok | ok | 1.547 |

## Fallback Accounting

- Total trace records: 3
- Total fallback count: 0
- Draft valid count: 3
- Draft rejected count: 0

Fallback accounting fields were present in every record.

## Runtime Notes

The trace reuses the existing pair smoke path rather than adding a new decoding pipeline. CUDA runtime evidence remained visible during Gemma execution, including CUDA device detection, CUDA compute buffers, and CUDA graph reuse. Qwen remained CPU-bound by policy.

## Tests

Added focused tests for controlled low-tier tracing:

- Multiple prompt execution with fake backends
- Bridge status recording
- Fallback count recording
- Qwen CPU policy recording
- Gemma CUDA policy recording
- Compact output summaries without raw long text
- CLI JSON report writing
- No unsupported benchmark-style claims in trace records

Full test suite passed after implementation: 57 tests.

## Remaining Issues

- This trace validates metadata and accounting only; it is not a benchmark.
- The current trace path still uses text-level bridge validation, not exact token-level speculation.
- High-tier feature speculation remains blocked until a backend with hidden-state access is added.

## Conclusion

passed

## Next Step

Add a deliberately rejected controlled trace case using a fake or test-only backend path, so fallback reporting is exercised predictably without relying on live Qwen output shape.
