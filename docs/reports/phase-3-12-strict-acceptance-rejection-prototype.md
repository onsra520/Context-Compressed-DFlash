# Phase 3.12 Strict Acceptance/Rejection Prototype

## Status

Prototype phase. Core pure algorithm implemented and tested.

Phase 3.12 does not implement the full runtime verifier loop.

Phase 3.12 does not claim correctness or equivalence validated.

Phase 3.12 does not claim speedup.

## What Changed

New source files:

```text
src/htfsd/low_tier/strict_verifier.py
src/htfsd/low_tier/token_bridge.py
src/htfsd/runtime/llama_cpp_capabilities.py
```

New test files:

```text
tests/test_phase_3_12_strict_accept_reject.py
tests/test_phase_3_12_token_bridge.py
tests/test_phase_3_12_backend_capabilities.py
```

New report:

```text
docs/reports/phase-3-12-strict-acceptance-rejection-prototype.md
```

No modifications to existing runtime files.

No modifications to `src/htfsd/low_tier/generate.py`.

No modifications to `src/htfsd/runtime/llama_cpp_backend.py`.

## Current Roadmap

```text
Phase 3.8  = Runtime log/output cleanliness
Phase 3.9  = Low-tier generation pipeline closure
Phase 3.10 = D-Flash correctness specification
Phase 3.11 = Token-level verifier design
Phase 3.12 = Strict acceptance/rejection prototype         ← CURRENT PHASE
Phase 3.13 = Correctness/equivalence validation harness
Phase 3.14 = Low-tier benchmark protocol/spec
Phase 3.15 = Low-tier benchmark dry run + Low-Tier D-Flash MVP closure report
Phase 4.0+ = High-tier preparation / feature-level speculative decoding
```

Phase 3.12 stayed within strict prototype scope.

No Phase 3.13, 3.14, or 3.15 work was started.

No high-tier work was started.

## Prior Specification

Phase 3.11 designed the token-level verifier.

Phase 3.11 commit: `9cba125 docs: design token level verifier`

Merge commit: `639edf9 feat: phase 3.11 token-level verifier design`

Phase 3.11 established:

```text
central principle: Gemma verifies candidate Gemma tokens derived from Qwen draft text
candidate tokenization: verifier.tokenize(context + candidate)[len(context_ids):]
verifier greedy decisions: eval + sample(temp=0.0) preferred
comparison algorithm: left-to-right, first mismatch = rejection point
partial prefix acceptance semantics
strict context update rule
trace schema definitions (design-only in Phase 3.11)
backend capability requirements (unknown status as of Phase 3.11)
```

Phase 3.12 now resolves the backend capability unknowns from Phase 3.11.

## Backend Capability Probe

Source: Static inspection of `llama_cpp.Llama` in llama-cpp-python 0.3.23.

```text
tokenizer_access          : supported
                            llama_cpp.Llama.tokenize(text: bytes, add_bos, special) -> list[int]
                            Method confirmed present in source.

decode_access             : supported
                            llama_cpp.Llama.detokenize(tokens, prev_tokens, special) -> bytes
                            Returns bytes (callers must .decode("utf-8")).

logits_access             : partially_supported
                            self.scores: np.ndarray, shape (n_ctx if logits_all else n_batch, n_vocab)
                            Only populated when Llama(logits_all=True) at load time.
                            Current LlamaCppBackend uses logits_all=False (default).

greedy_token_via_sample   : supported
                            llama_cpp.Llama.sample(temp=0.0, ...) -> int
                            Greedy argmax without requiring logits_all=True.
                            This is the preferred greedy approach for Phase 3.12.

eval_tokens               : supported
                            llama_cpp.Llama.eval(tokens: Sequence[int]) -> None
                            Updates KV cache and n_tokens.

one_token_step            : partially_supported
                            eval([token_id]) + sample(temp=0.0) both exist.
                            Not exposed by current LlamaCppBackend wrapper.
                            Thin extension needed (see wrapper_extension_required).

context_reset             : supported
                            llama_cpp.Llama.reset() sets n_tokens = 0.

token_eos                 : supported
                            llama_cpp.Llama.token_eos() -> int

token_bos                 : supported
                            llama_cpp.Llama.token_bos() -> int

n_vocab                   : supported
                            llama_cpp.Llama.n_vocab() -> int

wrapper_extension_required: partially_supported
                            Current LlamaCppBackend only exposes generate_text / generate_chat.
                            Phase 3.13 or a future sub-phase must add a thin
                            VerifierTokenAccess layer to expose tokenize, eval, sample.
                            Existing interfaces must not be broken.
```

Summary verdict: The backend is **token-verification capable with thin extension**.

The preferred greedy approach is `sample(temp=0.0)` — no need to require `logits_all=True`.

The current wrapper does not expose these APIs. A thin extension layer is required for Phase 3.13+ strict runtime verification.

Full capability classification is in `src/htfsd/runtime/llama_cpp_capabilities.py`.

## Prototype Scope

Phase 3.12 implements:

```text
1. VerificationDecision dataclass — strict frozen data structure for comparison results
2. VerifierCycleTrace dataclass — prototype-level cycle trace fields
3. compare_candidate_to_greedy() — pure comparison function (no model)
4. select_context_update_source() — context update label selection
5. CandidateSuffixResult dataclass — suffix derivation result
6. derive_candidate_suffix() — combined tokenization suffix derivation
7. make_word_tokenizer() — deterministic fake tokenizer for unit tests
8. LlamaCppCapabilityStatus dataclass — static backend capability classification
9. probe_llama_capabilities() — optional runtime probe (requires loaded model)
10. DEFAULT_CAPABILITY_STATUS — module-level static status instance
```

Phase 3.12 does not implement:

```text
- Full runtime strict verifier loop (Phase 3.13 scope)
- Wrapper extension for LlamaCppBackend (Phase 3.13 scope)
- Strict context update path wired into generate.py (Phase 3.13 scope)
- Equivalence validation harness (Phase 3.13 scope)
- Benchmark protocol or runner (Phase 3.14–3.15 scope)
- High-tier path (Phase 4.0+ scope)
```

## Strict Comparison Algorithm

Implemented in `src/htfsd/low_tier/strict_verifier.py` as `compare_candidate_to_greedy()`.

Design principle:

```text
Gemma verifies candidate Gemma tokens derived from Qwen draft text.
```

Algorithm:

```text
Given:
    candidate_verifier_token_ids = [a, b, c, d, e]
    verifier_greedy_token_ids    = [a, b, X, ...]

Comparison (left to right):
    Position 0: a == a  →  match
    Position 1: b == b  →  match
    Position 2: c != X  →  first_rejection_position = 2

Result:
    accepted_prefix           = [a, b]
    first_rejection_position  = 2
    rejected_token            = c
    unused_suffix             = [d, e]
    fallback_token_id         = X

Accounting:
    matched_verifier_token_count  = 2
    accepted_target_token_count   = 2
    rejected_target_token_count   = 1
    unused_suffix_token_count     = 2
```

Full accept:

```text
candidate = [1, 2, 3]
greedy    = [1, 2, 3]
result:
    verification_result          = full_accept
    accepted_target_token_count  = 3
    rejected_target_token_count  = 0
    unused_suffix_token_count    = 0
    fallback_token_id            = None
```

Full reject:

```text
candidate = [1, 2, 3]
greedy    = [9, 8, 7]
result:
    verification_result          = full_reject
    accepted_target_token_count  = 0
    rejected_target_token_count  = 1
    unused_suffix_token_count    = 2
    fallback_token_id            = 9
```

Empty candidate:

```text
candidate = []
greedy    = [9, 8, 7]
result:
    verification_result    = full_reject
    rejected_target_token_count = 0  (no candidate to reject)
    fallback_token_id      = 9
    rejection_reason       = empty_candidate
```

No greedy tokens:

```text
candidate = [1, 2, 3]
greedy    = []
result:
    stop_reason = no_progress_error
    fallback_token_id = None
```

## Acceptance Semantics

A candidate token at position i is accepted if and only if:

```text
candidate_verifier_token_ids[i] == verifier_greedy_token_ids[i]
```

Accepted units are verifier-side (Gemma-side) token ids.

accepted_target_token_count counts accepted verifier tokens, not drafter tokens.

draft_block_size is the drafter-side max token count, not the acceptance denominator.

## Rejection Semantics

A candidate token at position i is rejected if:

```text
candidate_verifier_token_ids[i] != verifier_greedy_token_ids[i]
```

rejected_target_token_count = 1 per rejection event.

The unused suffix (candidate tokens after the rejected position) is discarded.

Unused suffix tokens are NOT counted in rejected_target_token_count.

Bridge rejection (empty/invalid candidate) is not target-token rejection.

## Fallback Semantics

Fallback is triggered by:

```text
full_reject    : candidate[0] mismatches, fallback = greedy[0]
partial_accept : candidate[i] mismatches, fallback = greedy[i]
empty_candidate: fallback = greedy[0] (if available)
```

Fallback produces exactly one verifier greedy token per rejection event.

Fallback count is NOT correctness evidence, NOT performance evidence, NOT benchmark evidence.

No-progress error if no fallback is available:

```text
stop_reason = no_progress_error
```

## Unused Suffix Accounting

The unused suffix is the candidate token ids after the first mismatch position:

```text
unused_suffix = candidate_verifier_token_ids[first_rejection_position + 1:]
```

Unused suffix tokens are:

```text
discarded        : never appended to context
not rejected     : not counted in rejected_target_token_count
not reused       : not passed to the next cycle
```

The accounting invariant:

```text
accepted_target_token_count + rejected_target_token_count + unused_suffix_token_count
    == len(candidate_verifier_token_ids)

Except when candidate is empty:
    all three counts are 0.
```

## Context Update Semantics

Strict D-Flash context update rule (designed in Phase 3.11, implemented in data structures here):

Full accept:

```text
next_context = current_context + detokenize(accepted_prefix)
context_update_source = "full_accept"
```

Partial accept:

```text
next_context = current_context + detokenize(accepted_prefix) + detokenize([fallback_token_id])
context_update_source = "accepted_prefix"
```

Full reject / empty candidate:

```text
next_context = current_context + detokenize([fallback_token_id])
context_update_source = "fallback_only"
```

Must NOT update context with:

```text
rejected candidate suffix  (discarded)
unverified drafter text    (never in strict mode)
```

`select_context_update_source()` returns the appropriate label given a `VerificationDecision`.

Runtime wiring of context update into generate.py is deferred to Phase 3.13.

## Candidate Tokenization (Token Bridge)

Implemented in `src/htfsd/low_tier/token_bridge.py` as `derive_candidate_suffix()`.

Algorithm:

```text
context_ids  = verifier.tokenize(context_text)
combined_ids = verifier.tokenize(context_text + candidate_text)
candidate_verifier_token_ids = combined_ids[len(context_ids):]
```

Boundary mismatch detection:

```text
If combined_ids[:len(context_ids)] != context_ids:
    bridge_status = boundary_mismatch
    candidate_verifier_token_ids = []
    rejection_reason = tokenization_boundary_mismatch
```

This implements the core design requirement from Phase 3.11:

```text
Tokenizing candidate alone is insufficient.
Context+candidate must be tokenized together.
Suffix derived from the combined result.
```

The fake tokenizer (`make_word_tokenizer`) demonstrates and tests this behavior.
When using a real SentencePiece model, the tokenizer call will be:

```text
llama_model.tokenize(text.encode("utf-8"), add_bos=False, special=False)
```

## Trace Fields

`VerifierCycleTrace` in `strict_verifier.py` contains all trace fields designed in Phase 3.11:

```text
cycle_index
candidate_text
candidate_normalized_text
candidate_verifier_token_ids
candidate_verifier_token_count
verifier_greedy_token_ids
verifier_greedy_token_count
matched_verifier_token_count
first_rejection_position
verification_result
rejection_reason
fallback_reason
accepted_target_token_count
rejected_target_token_count
unused_suffix_token_count
fallback_token_id
context_update_source
comparison_profile        = "strict_token_level_v1"
backend_capability_status = {}  (populate from LlamaCppCapabilityStatus)
deterministic_settings    = {}  (temperature=0.0, greedy, seed, etc.)
```

Do not emit:

```text
acceptance_rate
speedup
lossless
target_equivalent
correctness_validated
```

## Tests

New test files:

```text
tests/test_phase_3_12_strict_accept_reject.py  — 33 tests
tests/test_phase_3_12_token_bridge.py           — 20 tests
tests/test_phase_3_12_backend_capabilities.py   — 19 tests (1 skipped: requires model)
```

Total new tests: 60 passed, 1 skipped.

All tests require no GGUF model, no GPU, no disk access.

Key test coverage:

```text
full accept (candidate == greedy)
partial accept (prefix matches, mismatch at position i)
full reject (first token mismatches)
empty candidate (no candidate tokens)
missing greedy tokens (no_progress_error)
unused suffix is NOT counted as rejected
fallback-only cycle commits exactly one token
repeated fallback-only cycles do not become speedup evidence
candidate longer than greedy sequence
accounting invariant: accepted + rejected + unused == len(candidate)
VerificationDecision is frozen (immutable)
select_context_update_source returns correct labels
forbidden field names absent from VerificationDecision
suffix derivation ok (clean boundary)
boundary mismatch detection
tokenizer error handling
LlamaCppCapabilityStatus static classification
capability status values are valid literals
version is recorded
notes present for partially_supported capabilities
DEFAULT_CAPABILITY_STATUS is immutable
```

## Verification

```text
focused tests (Phase 3.12):
    test_phase_3_12_strict_accept_reject.py  : 33 passed
    test_phase_3_12_token_bridge.py          : 20 passed
    test_phase_3_12_backend_capabilities.py  : 18 passed, 1 skipped

prior phase tests:
    test_phase_3_11_token_level_verifier_design.py : 23 passed
    test_phase_3_10_dflash_correctness_spec.py     : 5 passed

full suite:
    292 passed, 1 skipped, 1 pre-existing failure
    (test_prompt_sets.py::test_prompt_registry_reports_available_ids
     pre-existing on main before Phase 3.12 — not introduced by Phase 3.12)

forbidden-claim scan: clean
git diff --check: exit=0
```

## Remaining Limitations

Phase 3.12 does not implement:

```text
Wrapper extension for LlamaCppBackend
    - tokenize, eval, sample, reset, token_eos are not yet exposed
    - Current LlamaCppBackend only exposes generate_text / generate_chat
    - Phase 3.13 must add a thin VerifierTokenAccess layer

Full runtime strict verifier loop
    - compare_candidate_to_greedy() is pure with fake tokens
    - Not wired into the generation pipeline
    - generate.py is unchanged

Strict context update wired into generate.py
    - Context update rule is implemented in data structures
    - Not applied in live inference path yet

Equivalence validation harness
    - Phase 3.13 scope

Benchmark protocol or runner
    - Phase 3.14–3.15 scope

High-tier / EAGLE-style speculation
    - Phase 4.0+ scope
```

Backend capability is now classified as **token-verification capable with thin extension**.

No model runtime calls were made during Phase 3.12.

SentencePiece boundary sensitivity in real GGUF tokenization requires runtime testing when a real model is loaded.

## Interpretation Guards

`bridge_valid_block_count` is a bridge-level structural diagnostic count only.

It is not accepted block count.

It is not accepted token count.

It is not acceptance-rate evidence.

It is not target-equivalence evidence.

`cycle_fallback_count` is a cycle-level fallback count only.

It is not correctness evidence.

It is not performance evidence.

It is not benchmark evidence.

It is not a quality score.

`draft_block_size` is the drafter-side max token count.

It is not Gemma target token count.

It is not the acceptance denominator.

`rejected_target_token_count` is exactly 1 per rejection event.

It does not include the unused suffix token count.

`unused_suffix_token_count` is the count of candidate tokens discarded after first mismatch.

It is not a rejected token count.

It is not an acceptance metric.

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

No token-level acceptance rate is reported.

No EAGLE-style speculation is implemented.

No vLLM integration is introduced.

Phase 3.12 is a strict accept/reject prototype phase.

This is not yet a D-Flash/speculative decoding correctness implementation.

## Error Reports

Token bridge test failures (4 tests) on first run: The `make_word_tokenizer` splits on
single spaces. When context `"the quick"` is joined with candidate `"brown fox"` without
a trailing space, the join produces `"the quickbrown fox"` — `"quickbrown"` becomes a
different token than `"quick"`, causing a boundary mismatch. This is intentional
SentencePiece-like behavior demonstrating the design principle from Phase 3.11:
tokenization is boundary-sensitive. Tests fixed by using context strings with trailing
spaces (`"the quick "`) so the join produces clean word boundaries.

## Commit

Pending. Files ready for commit.

## Next Step

Recommended next phase:

```text
Phase 3.13: Correctness/Equivalence Validation Harness
```

Phase 3.13 should begin by:

```text
1. Extending LlamaCppBackend with a thin VerifierTokenAccess layer
   (expose tokenize, eval, sample, reset, token_eos without breaking existing interfaces)
2. Wiring derive_candidate_suffix() to the real verifier tokenizer
3. Wiring compare_candidate_to_greedy() to actual greedy token decisions
4. Implementing strict context update in the generation path
5. Building the equivalence validation harness for baseline comparison
```

Do not start benchmarks in Phase 3.13.

Do not start high-tier in Phase 3.13.
