# Phase 3.5 High-Tier Feasibility and Backend Decision Design

## Summary

Phase 3.5 starts Track C after the low-tier diagnostic MVP and block-cycle benchmark-readiness dry run.

This phase evaluates the intended high-tier direction at the design level:

```text
verifier -> current Gemma E2B
target   -> future Gemma E4B
```

The main decision is to keep the current GGUF plus llama.cpp runtime as the protected low-tier MVP path, then define high-tier backend capability contracts before adding any experimental high-tier runtime.

Current conclusion:

```text
The current llama-cpp-python path supports controlled generation and logits-oriented options, but high-tier feature access remains blocked or unproven until a capability probe demonstrates stable hidden-state/intermediate activation access.
```

## Motivation

The project now has:

```text
Low-Tier Diagnostic MVP v0.1
role-based names
block-cycle low-tier trace path
benchmark-readiness scaffold
block-cycle dry-run artifacts
```

The next risk is trying to add high-tier work directly inside the stable low-tier path. High-tier work has different requirements: hidden-state or intermediate-feature access, target logits, per-step feature metadata, dual Gemma model loading, and backend isolation.

Phase 3.5 defines the backend decision boundary before implementation begins.

## Current Runtime Boundary

Current runtime:

```text
GGUF + llama.cpp / llama-cpp-python
```

Current roles:

```text
drafter  -> Qwen3-0.6B on CPU
verifier -> Gemma E2B on CUDA/GPU
target   -> Gemma E4B, optional/future
```

The current runtime is accepted for:

```text
low-tier diagnostic traces
target-baseline traces
controlled fallback traces
block-cycle low-tier traces
timing-readiness artifacts
```

The current runtime is not accepted yet for high-tier feature-level work.

Documentation reference notes:

```text
llama-cpp-python documents logits-related controls such as logits_all.
llama-cpp-python documents embedding-oriented controls.
llama-cpp-python documents prompt-lookup draft-model settings.
The reviewed high-level Python/server docs did not establish a stable high-level hidden-state API for this project.
```

References:

```text
https://llama-cpp-python.readthedocs.io/en/latest/api-reference/
https://llama-cpp-python.readthedocs.io/en/latest/server/
```

## Intended High-Tier Shape

The intended high-tier direction is feature-level and must remain isolated:

```text
Gemma E2B hidden states or intermediate features
  -> feature-level drafter or predictor
  -> Gemma E4B target verification
```

This is related to EAGLE-style research direction, but the project does not claim an EAGLE implementation.

The high-tier path must not alter the closed low-tier MVP path. It should live behind explicit capability contracts and separate readiness gates.

## Required Capabilities

High-tier work needs:

```text
1. Access to verifier hidden states or intermediate activations
2. Access to target model logits for verification
3. Consistent tokenizer and token boundary handling between Gemma E2B and Gemma E4B
4. Controlled deterministic settings for Gemma E2B and Gemma E4B
5. Per-step feature/logit metadata capture
6. Separated model load, generation, and verification timing
7. Hardware-safe dual-model execution without breaking low-tier workflow
```

The most important gating capability is hidden-state or intermediate activation access. Without it, feature-level high-tier work should remain blocked.

## Current Runtime Capability Matrix

| capability | needed_for_high_tier | current_llama_cpp_status | risk | decision |
| --- | --- | --- | --- | --- |
| hidden_state_access | feature provider input | blocked / unknown | current high-level wrapper docs do not establish a stable hidden-state API for this project | require capability probe before implementation |
| target_logits_access | target verification | partially_supported | logits controls exist, but target verification semantics still need per-step contract tests | design contract first |
| tokenizer_consistency | Gemma E2B to Gemma E4B boundary | not_tested | both roles are Gemma-family, but exact tokenizer and prompt-template compatibility must be verified | add tokenizer compatibility probe later |
| deterministic_decoding | reproducible high-tier traces | partially_supported | seed and temperature controls exist, but dual-model deterministic behavior must be tested | reuse generation settings policy |
| per-step_metadata | feature/logit traceability | unknown | current MVP traces record text-level metadata, not feature-level metadata | define metadata schema before backend |
| dual_model_loading | verifier plus target execution | not_tested | local VRAM may not support both Gemma E2B and Gemma E4B simultaneously | require memory-budget probe |
| memory_budget | local feasibility | unknown | target role is optional today and not part of low-tier acceptance | keep target optional |
| timing_instrumentation | Track B continuity | partially_supported | Phase 3.2/3.4 scaffolds can record boundaries, but high-tier-specific boundaries do not exist yet | extend timing schema only after contract |
| backend_isolation | protect low-tier MVP | supported by design | accidental coupling could regress stable low-tier diagnostics | use separate backend abstraction |

## Backend Options

### Option A: Stay on GGUF + llama.cpp only

What it enables:

```text
keeps one runtime family
preserves current GGUF model artifacts
minimizes dependency expansion
```

Risks:

```text
hidden-state access may remain blocked
feature-level traces may not be possible through the current wrapper
workarounds could become brittle
```

Implementation cost:

```text
low if capabilities already exist
high if the project must patch or bind lower-level internals
```

Hardware risk:

```text
unchanged for low-tier
unknown for dual Gemma high-tier
```

Compatibility with current MVP:

```text
high if kept as low-tier-only runtime
risky if high-tier work mutates low-tier backend paths
```

Recommendation:

```text
Keep for low-tier MVP. Do not assume it is enough for high-tier feature work.
```

### Option B: Add Transformers/PyTorch path for high-tier only

What it enables:

```text
native hidden-state access
easier feature capture
easier experimental feature-provider prototypes
```

Risks:

```text
larger dependencies
different quantization/runtime behavior
higher VRAM pressure
new reproducibility surface
```

Implementation cost:

```text
medium to high
```

Hardware risk:

```text
high for local dual Gemma runs unless carefully scoped
```

Compatibility with current MVP:

```text
good if isolated behind high-tier-only contracts
poor if it replaces low-tier runtime
```

Recommendation:

```text
Candidate experimental high-tier backend if hidden states are required and llama.cpp cannot expose them safely.
```

### Option C: Keep GGUF for low-tier, add separate high-tier backend abstraction

What it enables:

```text
protects Low-Tier Diagnostic MVP v0.1
lets high-tier choose a capability-fit backend
keeps runtime-specific assumptions behind interfaces
```

Risks:

```text
more architecture work before experiments
requires clear compatibility tests
```

Implementation cost:

```text
medium
```

Hardware risk:

```text
controlled by backend readiness gates
```

Compatibility with current MVP:

```text
high
```

Recommendation:

```text
Recommended direction.
```

### Option D: Defer high-tier implementation and write contracts only

What it enables:

```text
clarifies requirements before backend work
reduces risk of coupling to the wrong runtime
keeps current project stable
```

Risks:

```text
does not produce a high-tier prototype yet
may delay empirical feasibility findings
```

Implementation cost:

```text
low
```

Hardware risk:

```text
none in this phase
```

Compatibility with current MVP:

```text
high
```

Recommendation:

```text
Recommended next step before any backend implementation.
```

## Recommended Backend Direction

Recommended direction:

```text
1. Keep GGUF + llama.cpp as the low-tier MVP runtime.
2. Do not remove or weaken the existing GGUF path.
3. Define high-tier backend capability contracts first.
4. Add a capability probe phase before implementation.
5. If hidden states are required and the current llama-cpp-python path cannot expose them safely, add a separate experimental Transformers/PyTorch backend for high-tier only.
```

The decision is intentionally conservative. The low-tier MVP remains stable while high-tier work gets its own readiness gates.

## Proposed High-Tier Contracts

Future contracts should be design-first and backend-neutral.

```text
FeatureProvider:
  role:
    expose verifier-side hidden states or intermediate features
  required methods:
    prepare_context(...)
    step_features(...)
    feature_metadata(...)
  required guarantees:
    deterministic mode metadata
    token boundary metadata
    backend capability declaration
```

```text
TargetVerifier:
  role:
    run target-side verification over candidate feature/text/token paths
  required methods:
    prepare_target_context(...)
    step_logits(...)
    verification_metadata(...)
  required guarantees:
    target model identity
    tokenizer identity
    deterministic generation settings
```

```text
HighTierBackendCapabilities:
  fields:
    backend_name
    supports_hidden_states
    supports_target_logits
    supports_per_step_metadata
    supports_dual_model_loading
    supports_deterministic_settings
    tokenizer_identity_available
    timing_boundary_support
```

```text
HighTierReadinessStatus:
  fields:
    ready
    blocking_reasons
    warnings
    capability_matrix
    hardware_notes
    non_claims
```

These contracts should be introduced before any high-tier execution path.

## Risks

```text
GGUF/llama.cpp may not expose required hidden states through the current Python path.
Feature-level speculation may require PyTorch/Transformers access.
Dual Gemma model loading may exceed local VRAM.
Tokenizer compatibility may be easier than Qwen/Gemma low-tier because verifier/target are both Gemma, but this still must be verified.
High-tier implementation could accidentally break low-tier MVP if not isolated.
Timing numbers from Track B are readiness metadata only, not performance evidence.
```

Additional risk:

```text
Using logits-only access may be insufficient if the intended high-tier predictor depends on intermediate activations rather than final-token logits.
```

## Non-Claims

This is not high-tier implementation.

This is not EAGLE implementation.

No hidden-state speculation claim is made.

No feature-level verification claim is made.

No target-equivalence claim is made.

No correctness claim is made.

No lossless-generation claim is made.

No benchmark claim is made.

No speedup claim is made.

No performance-improvement claim is made.

No draft-acceptance metric is reported.

`bridge_valid_block_count` is not acceptance.

`cycle_fallback_count` is not correctness or performance evidence.

## Recommended Next Step

Proceed to:

```text
Phase 3.6: High-Tier Backend Capability Contract
```

Phase 3.6 should define contract dataclasses/protocols and tests only. It should not run high-tier inference.

Suggested scope:

```text
FeatureProvider protocol
TargetVerifier protocol
HighTierBackendCapabilities dataclass
HighTierReadinessStatus dataclass
backend capability matrix serializer
no high-tier execution
```

## Conclusion

The current GGUF plus llama.cpp runtime remains the right protected runtime for the low-tier MVP. It is not yet proven sufficient for high-tier feature-level work.

High-tier work should proceed behind isolated capability contracts and a later backend capability probe. If hidden-state access is required and unavailable through the current Python runtime path, a separate experimental high-tier backend should be considered without disturbing the low-tier MVP.

