# Phase 1.5 Controlled Rejection and Fallback Trace

## Summary

Phase 1.5 passed. The low-tier trace command now has an explicit `controlled-fallback` mode that injects deterministic Qwen draft outputs and verifies bridge rejection plus Gemma fallback accounting without depending on live Qwen output shape.

Default live trace behavior remains unchanged:

```bash
python scripts/run_low_tier_trace.py
```

Controlled fallback mode is explicit:

```bash
python scripts/run_low_tier_trace.py --mode controlled-fallback
```

## Controlled Cases

The controlled fallback trace covers four cases:

| Case | Injected Draft | Expected Bridge | Expected Fallback |
|---|---|---|---:|
| `valid_plain_draft` | `Speculative decoding drafts tokens before verification.` | valid | 0 |
| `empty_draft` | empty string | rejected | 1 |
| `unclosed_think` | `<think>I am reasoning` | rejected | 1 |
| `complete_think_then_empty` | `<think>hidden reasoning</think>` | rejected | 1 |

Latest controlled trace file:

- `logs/reports/20260524T135715Z-low-tier-trace.json`

## Trace Fields Verified

Controlled records include:

- `case_id`
- `prompt_id`
- `bridge_status`
- `rejection_reason`
- `fallback_count`
- `draft_valid_count`
- `draft_rejected_count`
- `qwen_expected_device`
- `gemma_expected_device`
- `qwen_device_status`
- `gemma_device_status`
- `qwen_n_gpu_layers`
- `gemma_n_gpu_layers`
- `gemma_fallback_used`

Short injected draft strings are included as controlled test data. Long raw model outputs are not stored by default.

## Fallback Accounting

Observed controlled fallback summary:

- `total_cases: 4`
- `valid_count: 1`
- `rejected_count: 3`
- `fallback_count: 3`

Per-case results:

| Case | Bridge | Rejection Reason | Fallback Count | Fallback Used |
|---|---|---|---:|---|
| `valid_plain_draft` | valid | None | 0 | false |
| `empty_draft` | rejected | `empty_after_normalization` | 1 | true |
| `unclosed_think` | rejected | `contains_unclosed_think` | 1 | true |
| `complete_think_then_empty` | rejected | `empty_after_normalization` | 1 | true |

## Rejection Reasons

The text bridge produced the expected rejection reasons:

- Empty draft: `empty_after_normalization`
- Unclosed thinking block: `contains_unclosed_think`
- Complete thinking block with no visible answer: `empty_after_normalization`

## Runtime Policy

Runtime policy remains unchanged and satisfied:

- Qwen3-0.6B: `expected_device = cpu`, `n_gpu_layers = 0`, `device_status = ok`
- Gemma E2B: `expected_device = cuda`, `n_gpu_layers = -1`, `device_status = ok`

Controlled mode injects Qwen draft text, so it does not depend on live Qwen output shape. Gemma E2B still runs through the normal fallback/continuation backend.

## Tests

Added tests for:

- Controlled fallback trace with injected Qwen drafts
- Empty draft rejection and fallback increment
- Unclosed `<think>` rejection and fallback increment
- Complete `<think>...</think>` empty-output rejection and fallback increment
- Valid draft without fallback
- Rejection reason recording
- Device policy metadata recording
- Default live trace behavior
- Controlled fallback CLI summary/report writing

Full test suite passed: 61 tests.

Forbidden-claim scan passed with no matches for unsupported benchmark, equivalence, speedup, or runtime-path claims.

## Remaining Issues

- Controlled fallback mode validates accounting and bridge behavior only; it is not a benchmark.
- Exact token-level speculation is still not implemented.
- High-tier feature speculation remains blocked until hidden-state-capable backend support exists.

## Conclusion

passed

## Next Step

Add a small trace-inspection utility or test fixture that compares live and controlled trace schemas, so future changes cannot accidentally drop required trace fields.
