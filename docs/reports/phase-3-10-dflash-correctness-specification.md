# Phase 3.10 D-Flash Correctness Specification

## Status

Specification phase.

Phase 3.10 defines correctness semantics only. It does not implement or validate correctness.

## What Changed

Created the main specification:

```text
docs/specs/phase-3-10-dflash-correctness-specification.md
```

Added lightweight documentation tests to verify that the specification preserves the required boundaries.

No runtime verifier, strict accept/reject logic, benchmark code, or high-tier path was added.

## Current Roadmap

The corrected roadmap is:

```text
Phase 3.8  = Runtime log/output cleanliness
Phase 3.9  = Low-tier generation pipeline closure
Phase 3.10 = D-Flash correctness specification
Phase 3.11 = Token-level verifier design
Phase 3.12 = Strict acceptance/rejection prototype
Phase 3.13 = Correctness/equivalence validation harness
Phase 3.14 = Benchmark protocol/spec
Phase 3.15 = Benchmark runner implementation
Phase 3.16 = Low-tier benchmark dry run
Phase 3.17 = Low-tier benchmark report / Low-Tier D-Flash MVP closure
Phase 4.0+ = High-tier preparation / feature-level speculative decoding
```

Phase 3.10 stayed within specification scope.

## Specification Summary

The specification defines a staged correctness path:

```text
Option A first: text-prefix verification
Option B later: Gemma target-token verification
Option C possible intermediate: strict block-level exact continuation
```

The recommended first path is Option A.

## Candidate Unit

Initial candidate unit:

```text
draft_text_chunk
```

It is drafter-produced text, bounded by drafter-side generation settings and text bridge validation.

It is not a Gemma-token block.

## Verification Unit

Initial verification unit:

```text
normalized text prefix
```

The verifier asks whether normalized candidate text is a prefix of normalized verifier continuation text under deterministic settings.

This is text-level only.

## Tokenizer Mismatch

The spec explicitly records that:

```text
draft_block_size = 8
```

means:

```text
Qwen-side draft max tokens = 8
```

It does not mean Gemma target tokens.

## Deterministic Settings

Future validation requires:

```text
temperature = 0.0
fixed seed where supported
greedy decoding
stable prompt mode
same effective prompt
same context update rule
same stop handling
same continuation bound where applicable
same comparison normalization rule
model identity and model file recorded
runtime version recorded where available
```

## Acceptance Semantics

Initial text-level acceptance requires:

```text
bridge-valid candidate
deterministic verifier continuation
normalized candidate text is a prefix of normalized verifier continuation text
accepted span recorded as text span / character span
```

The accepted span is not a target-token count.

## Rejection Semantics

A candidate is rejected when bridge validation fails, comparison fails, verifier continuation cannot be generated, comparison is ambiguous, or constraints are violated.

Bridge rejection is not target-token rejection.

## Fallback Semantics

Fallback is a recovery mechanism.

Rejected candidates are not appended as accepted output. Context should advance only with verified text or fallback text under the active correctness profile.

## Context Update Semantics

Strict future context update rule:

```text
next context = previous context + accepted candidate text
```

or:

```text
next context = previous context + verifier fallback text
```

Rejected or unverified drafter text must not update context in strict correctness mode.

## Baseline Equivalence Target

Future low-tier validation target:

```text
Gemma E2B greedy baseline
```

This belongs to Phase 3.13 validation.

No equivalence claim is made in Phase 3.10.

## Correctness Trace Requirements

Future traces should include:

```text
cycle_index
candidate_text
candidate_normalized_text
candidate_bridge_status
verifier_continuation_text
verifier_normalized_continuation_text
verification_result
rejection_reason
fallback_reason
accepted_text_span
rejected_text_span
context_update_source
deterministic_settings
baseline_reference_id
comparison_profile
```

Future token-level fields are reserved in the spec but must not be emitted by Phase 3.10 runtime.

## Metrics Naming Rules

Current metrics remain structural:

```text
bridge_valid_block_count
bridge_rejected_block_count
cycle_fallback_count
```

They are not acceptance metrics.

## Verification

```text
spec tests: 5 passed
full suite: 210 passed
forbidden-claim scan: clean
git diff --check: clean
```

## Remaining Limitations

Phase 3.10 does not implement:

```text
token-level verifier
strict accept/reject runtime behavior
correctness validation
baseline equivalence harness
benchmark code
high-tier behavior
```

## Interpretation Guards

bridge_valid_block_count is structural bridge metadata only.

It is not accepted block count.

It is not accepted token count.

It is not acceptance-rate evidence.

It is not target-equivalence evidence.

cycle_fallback_count is fallback event metadata only.

It is not correctness evidence.

It is not performance evidence.

It is not benchmark evidence.

It is not a quality score.

## Non-Claims

This is not a benchmark report.

This is not a performance comparison.

This is not D-Flash correctness validation.

No speedup claim is made.

No performance-improvement claim is made.

No output parity claim is made.

No target-equivalence claim is made.

No correctness claim is made.

No lossless-generation claim is made.

No draft-acceptance metric is reported.

No high-tier implementation claim is made.

The closed v0.2 path is the `low-tier block-cycle generation pipeline`.

Phase 3.10 is a correctness specification phase.

This is not yet a D-Flash/speculative decoding correctness implementation.

## Error Reports

The initial spec tests failed because the Phase 3.10 spec and report were intentionally absent. The failure was resolved by adding the specification and report.

## Commit

Pending final commit.

## Next Step

Recommended next phase:

```text
Phase 3.11: Token-Level Verifier Design
```
