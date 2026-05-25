# Phase 1.9 Low-Tier Baseline Comparison Design

## Summary

Phase 1.9 defines the comparison rules for the current low-tier and target-baseline trace artifacts.

This phase is design only. It does not add benchmark logic, output matching, token-level draft verification, or high-tier feature implementation.

The current comparison layer may summarize trace metadata, runtime placement, bridge accounting, and latency fields descriptively. It must not present those summaries as a benchmark claim or as proof of output parity.

## Current Trace Capabilities

The live low-tier trace currently measures the path:

```text
Qwen CPU -> text_bridge -> Gemma E2B CUDA
```

It records prompt identifiers, model files, expected devices, observed device statuses, configured GPU-layer policy, bridge status, rejection reason, fallback count, draft-valid count, draft-rejected count, latency fields, decode token/s fields when available, and compact output summaries.

The controlled fallback trace validates the fail-safe branch by injecting known draft strings. It confirms that empty drafts and malformed thinking sections are rejected and that fallback accounting increments predictably.

The target-baseline trace currently measures:

```text
prompt -> Gemma E2B CUDA
```

It records prompt identifiers, Gemma model file, expected device, observed device status, configured GPU-layer policy, latency fields, decode token/s fields when available, compact output summaries, and `trace_kind = target_baseline`.

The comparison report v0 validates schemas, compares record counts and prompt coverage, checks runtime metadata, summarizes low-tier bridge accounting, and reports latency fields descriptively.

## Safe Descriptive Comparisons

These fields are safe to compare now as trace metadata:

- Record counts
- Prompt ID overlap
- Missing and extra prompt IDs
- Schema status
- Gemma model file match
- Qwen and Gemma device status
- Configured `n_gpu_layers`
- Low-tier fallback count
- Low-tier draft-valid count
- Low-tier draft-rejected count
- Latency field summaries
- Decode token/s field summaries

Latency and token/s fields may be summarized as observed runtime fields. Acceptable wording includes:

- Descriptive latency summary
- Observed latency fields
- Runtime trace metadata
- Field-level comparison

These summaries are useful for sanity checks and future experiment design, but they are not yet benchmark evidence.

## Unsafe Claims

The project should not make these claims from the current trace artifacts:

- That the low-tier path is a benchmarked improvement over the target-baseline path
- That the low-tier output matches the target-baseline output
- That generation is exact relative to the target model
- That draft acceptance has been measured at the token level
- That quality, correctness, or safety is better in either path
- That high-tier feature speculation is implemented

The current low-tier path is a bridge/runtime trace:

```text
Qwen draft text -> bridge normalization or rejection -> Gemma continuation or fallback
```

It is not yet exact token-level speculative decoding.

## Evidence Required For Output Equality

Before output equality can be compared, a future phase must provide:

- The same prompt set for low-tier and target-baseline runs
- The same generation settings
- The same stop conditions
- The same maximum token budget
- The same prompt formatting policy
- Raw output capture in an explicit controlled mode
- A documented output normalization policy
- Captured model files, seeds, backend versions, and runtime settings
- Documented limitations for tokenizer, prompt-template, and stop-token behavior

Raw output capture should remain opt-in because it may produce long or sensitive logs.

## Evidence Required For Lossless Generation

Before making any exact target-generation claim, a future phase must provide:

- Exact token-level target verification
- Target-model greedy-equivalent generation
- Deterministic decoding settings
- Target-token comparison using the target tokenizer
- Strict fallback on any mismatch
- A broad enough test set to catch realistic bridge failures
- Repeatable run metadata
- Per-cycle trace records showing the target verifier decision

Text-level normalization alone is not sufficient for this claim.

## Evidence Required For Speedup Claims

Before making any runtime-improvement claim, a future phase must provide:

- Stable hardware placement
- A warmup policy
- Multiple runs
- Target-only baseline runs under the same settings
- Low-tier runs under the same settings
- Clear timing boundaries
- Model load time separated from generation time, or explicitly included in both paths
- Statistical summaries over multiple prompts and runs
- No unresolved CPU/GPU placement mismatch
- A documented environment snapshot

Single-run latency summaries are only descriptive observations.

## Evidence Required For Draft Acceptance Metrics

Before reporting draft acceptance metrics, a future phase must provide:

- Token-level candidate drafts
- Target verifier logits or exact target-token comparison
- Accepted token count
- Rejected token count
- Fallback token count
- A clear definition of the acceptance unit
- Per-cycle trace records
- Cross-tokenizer boundary handling
- Deterministic verifier settings

The current `bridge_status = valid` means the text bridge accepted the draft shape. It does not mean target-token acceptance.

## Recommended Next Implementation Step

The next safe implementation phase should be:

```text
Phase 2.0: Controlled Generation Settings and Output Capture Mode
```

That phase should prepare future equality analysis by centralizing:

- Prompt set selection
- Generation settings
- Stop conditions
- Maximum token budget
- Prompt formatting policy
- Optional raw output capture, disabled by default
- Schema extensions for controlled output comparison

Phase 2.0 should still avoid benchmark and exact-generation claims.

## Non-Goals

This phase does not:

- Implement benchmark logic
- Report runtime improvement
- Compare output equality
- Claim exact target generation
- Measure token-level draft acceptance
- Implement high-tier hidden-state logic
- Change runtime device policy
- Change fallback semantics

## Conclusion

passed

The project now has a clear design boundary for low-tier versus target-baseline comparison. Current reports may compare schema, prompt coverage, device metadata, bridge accounting, and latency fields descriptively. Stronger claims require controlled output capture, token-level verification, repeatable runtime methodology, and stricter evidence than the current trace layer provides.
