# Reverted and Rejected Changes

## Reverted/replaced

- `REC2-R002-I1`: applying the one-ULP selection band to every verifier row. It reached 50/50 parity, but was replaced before acceptance by correction-row-only handling because accepted proposal rows did not require it. No checkpoint was created.

## Rejected without source mutation

- Wholesale REC-2 source restore: rejected because runtime source and config were already byte-identical, except for the valid current quality wording extension.
- Target prefill, position, cache-position, attention-mask, KV-cache, stopping, and logit-offset rewrites: rejected after the full trace proved their logical contracts correct.
- Current-best bulk port: rejected because its runtime bytes were already present.
- Token-specific handling, prompt/seed/workload changes, Baseline token forcing, target replay, sequential verification fallback, oracle paths, and dependency/backend changes: prohibited and not attempted.
