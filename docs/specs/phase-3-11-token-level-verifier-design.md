# Phase 3.11 Token-Level Verifier Design

## Summary

Phase 3.11 designs the token-level verifier for the HTFSD D-Flash low-tier path.

Phase 3.11 is a design phase.

Phase 3.11 does not implement the strict runtime accept/reject verifier.

Phase 3.11 does not validate correctness.

Phase 3.11 does not run benchmarks.

Phase 3.11 does not start high-tier.

The central design statement is:

```text
Gemma verifies candidate Gemma tokens derived from Qwen draft text.
```

Not:

```text
Gemma verifies Qwen tokens.
```

This distinction is the foundation of the entire token-level verification design.

## Current Roadmap

The corrected roadmap is:

```text
Phase 3.8  = Runtime log/output cleanliness
Phase 3.9  = Low-tier generation pipeline closure
Phase 3.10 = D-Flash correctness specification
Phase 3.11 = Token-level verifier design
Phase 3.12 = Strict acceptance/rejection prototype
Phase 3.13 = Correctness/equivalence validation harness
Phase 3.14 = Low-tier benchmark protocol/spec
Phase 3.15 = Low-tier benchmark dry run + Low-Tier D-Flash MVP closure report
Phase 4.0+ = High-tier preparation / feature-level speculative decoding
```

Phase 3.11 is a design phase. Runtime correctness implementation starts in Phase 3.12.

## Prior Specification

Phase 3.10 defined correctness semantics.

Commit: `13022de docs: define dflash correctness specification`

Phase 3.10 artifacts:

```text
docs/specs/phase-3-10-dflash-correctness-specification.md
docs/reports/phase-3-10-dflash-correctness-specification.md
tests/test_phase_3_10_dflash_correctness_spec.py
```

Phase 3.10 defined a staged correctness path:

```text
Option A first: text-prefix verification
Option B later: Gemma target-token verification
Option C possible intermediate: strict block-level exact continuation
```

Phase 3.10 reserved these token-level trace fields for future use:

```text
accepted_target_token_count
rejected_target_token_count
first_rejection_position
```

Phase 3.11 now designs the token-level path these fields point toward.

## Scope

This design document defines:

```text
tokenizer mismatch handling
candidate tokenization pipeline
verifier greedy decision source
token comparison algorithm
partial match and first rejection position
acceptance semantics (token-level)
rejection semantics (token-level)
fallback semantics (token-level)
context update semantics (token-level)
trace schema requirements for Phase 3.12+
backend capability requirements
llama-cpp-python / GGUF constraints
deterministic settings
failure modes
metrics naming rules
implementation boundary for Phase 3.12
risks and open questions
interpretation guards
non-claims
```

## Non-Scope

This phase does not implement:

```text
strict runtime accept/reject verifier
production token-level verification loop
correctness validation harness
baseline equivalence test
benchmark protocol
benchmark runner
speedup measurement
performance comparison
Gemma E4B target verification
hidden-state extraction
EAGLE-style speculation
vLLM integration
```

This phase does not add runtime output fields:

```text
accepted_target_token_count
rejected_target_token_count
acceptance_rate
target_equivalent
lossless
speedup
```

These may appear only as design-only future field definitions in this document.

## Problem Statement

The current low-tier pipeline in `src/htfsd/low_tier/generate.py` is a diagnostic/prototype path.

It does not implement speculative decoding verification.

Current behavior:

```text
cycle:
    drafter generates draft_text_chunk
    bridge validates/normalizes draft text
    if bridge valid:
        verifier prompt = context + normalized draft text
        verifier generates up to draft_block_size tokens of its own continuation
        response chunk = normalized draft text + verifier continuation text
    else:
        verifier generates fallback from current context
        response chunk = verifier fallback text
    context += response chunk
```

This is incorrect for D-Flash correctness because:

```text
verifier text is concatenated after drafter text, not used to verify it
no token-level comparison occurs
drafter text enters the context unconditionally if bridge-valid
verifier output is not used as a correctness authority
no accept/reject/fallback state machine exists
```

Phase 3.11 must design the correct D-Flash loop behavior before Phase 3.12 implements it.

## Tokenizer Mismatch

The drafter and verifier use different tokenizers.

```text
drafter = Qwen3-0.6B   → Qwen tokenizer (SentencePiece-based)
verifier = Gemma E2B   → Gemma tokenizer (SentencePiece-based, different vocabulary)
```

Consequences:

```text
Qwen token at position i is not the same vocabulary unit as Gemma token at position i
draft_block_size = 8 means at most 8 Qwen-side draft tokens
8 Qwen draft tokens do not correspond to 8 Gemma verifier tokens
Qwen token count is not a valid acceptance denominator
Qwen token ids cannot be compared directly against Gemma token ids
```

Therefore:

```text
Qwen draft tokens must be converted to text first.
The text must be tokenized with the Gemma/verifier tokenizer.
Only then can token-level comparison against verifier greedy output be defined.
```

This is why the correct design statement is:

```text
Gemma verifies candidate Gemma tokens derived from Qwen draft text.
```

Naming must follow this distinction:

```text
candidate_verifier_token_ids  (NOT: qwen_token_ids, draft_token_ids)
verifier_greedy_token_ids     (NOT: gemma_token_ids, target_token_ids)
matched_verifier_token_count  (NOT: accepted_qwen_tokens, draft_accepted_tokens)
```

## Design Principle

The token-level verifier design principle:

```text
1. Drafter (Qwen) generates draft_text_chunk as raw text.
2. draft_text_chunk is processed through the text bridge (normalization, validation).
3. Bridge-valid draft_text_chunk is tokenized using the verifier (Gemma) tokenizer.
4. This produces candidate_verifier_token_ids.
5. The verifier (Gemma E2B) produces greedy token decisions for the same context position.
6. These are verifier_greedy_token_ids.
7. candidate_verifier_token_ids and verifier_greedy_token_ids are compared position by position.
8. The longest matching prefix is accepted.
9. At the first mismatch, the candidate is rejected and fallback begins.
10. Context is updated with only accepted + fallback verifier tokens.
```

This design preserves D-Flash correctness invariants.

## Candidate Source

The candidate source is:

```text
draft_text_chunk
```

Produced by:

```text
drafter backend (Qwen3-0.6B via llama-cpp-python)
```

Bounded by:

```text
configured draft_block_size (Qwen-side max tokens)
text bridge normalization
text bridge validation
configured stop sequences
```

The candidate source is text, not token ids.

The candidate source is not Gemma token ids.

The candidate source must be tokenized with the verifier tokenizer before token-level verification.

Role names to use in new code, docs, and traces:

```text
drafter_*  (canonical)
drafter_draft_text_chunk
drafter_draft_block_size
drafter_latency_seconds
```

Avoid introducing new model-specific names:

```text
qwen_*  (deprecated alias only)
```

## Candidate Tokenization

### Design

Input:

```text
current_context_text   : full text accumulated so far
draft_text_chunk       : raw drafter output for this cycle
```

Tokenization target:

```text
verifier tokenizer via llama-cpp-python
```

Correct tokenization approach:

```text
Step 1: tokenize current_context_text alone.
        tokens_context = verifier.tokenize(current_context_text)

Step 2: tokenize (current_context_text + draft_text_chunk) together.
        tokens_context_plus_candidate = verifier.tokenize(current_context_text + draft_text_chunk)

Step 3: derive candidate token suffix.
        candidate_verifier_token_ids = tokens_context_plus_candidate[len(tokens_context):]
```

This avoids boundary-sensitive tokenization errors.

### Why combined tokenization is required

Tokenizing `draft_text_chunk` alone may produce different token ids than tokenizing it as a continuation of `current_context_text`.

Example: A leading space before a word may be merged with the prior word's boundary token in SentencePiece.

Tokenizing combined then stripping the context prefix is the safest way to derive the true candidate token suffix.

### Boundary conditions

```text
If candidate_verifier_token_ids is empty after normalization:
    treat as bridge rejection, trigger fallback.

If draft_text_chunk is empty or whitespace-only after normalization:
    treat as bridge rejection, trigger fallback.

BOS and EOS tokens:
    must not be included in candidate_verifier_token_ids.
    must not be included in verifier_greedy_token_ids for comparison purposes.

Stop tokens:
    if a stop token appears in the candidate sequence, truncate the candidate at that position.

Newline tokens and Unicode tokens:
    follow bridge normalization profile; do not rewrite for comparison purposes.
```

### Naming

```text
candidate_text                  : draft_text_chunk after bridge normalization
candidate_verifier_token_ids    : verifier token ids derived from candidate_text
candidate_verifier_token_count  : len(candidate_verifier_token_ids)
```

### Risk

If `llama-cpp-python`'s tokenize API is not available or returns inconsistent results for context + candidate combined tokenization, this approach must fall back to text-level verification (Phase 3.10 Option A).

This is documented in the Backend Capability Requirements section.

## Verifier Greedy Decision Source

### Design

The verifier greedy decision source is:

```text
Gemma E2B running under deterministic (temperature=0.0, greedy) settings
via llama-cpp-python GGUF backend
```

The goal is to obtain:

```text
verifier_greedy_token_ids
```

Where each token id is the argmax greedy decision by Gemma E2B at each position in the context, starting after the current accepted context.

### Preferred approach (Approach B)

Use `llama-cpp-python` token/logit step APIs to evaluate the model one token at a time:

```text
Step 1: Load context tokens into verifier KV cache.
Step 2: Obtain logits for the next position.
Step 3: Take argmax → greedy token id at position 0.
Step 4: Advance model state by one token.
Step 5: Obtain logits for next position.
Step 6: Take argmax → greedy token id at position 1.
Step 7: Repeat for candidate_verifier_token_count positions.
```

This approach is the most correct because it produces exact greedy token decisions without text-level ambiguity.

### Fallback approach (Approach A)

If token/logit step APIs are not reliably available in the current `llama-cpp-python` version:

```text
Generate verifier continuation text greedily for at least candidate_verifier_token_count tokens.
Tokenize the generated continuation text with the verifier tokenizer.
Use the resulting token ids as verifier_greedy_token_ids.
```

This approach is less precise because it introduces a second round of tokenization. It may diverge from exact greedy decisions at boundary positions.

### Approach C (text-level fallback)

If neither Approach A nor B is reliable for Phase 3.12:

```text
Use strict text-prefix verification as defined in Phase 3.10 Option A.
Design Phase 3.11 token-level semantics as the target architecture.
Implement text-level verification in Phase 3.12 first.
Migrate to token-level in a later phase when backend capability is confirmed.
```

### Required backend capability for preferred approach

```text
verifier.tokenize(text) → list[int]      # tokenize text to token ids
verifier.eval(token_ids)                 # evaluate token ids, update KV cache
verifier.get_logits() → list[float]      # access logits for next position
argmax(logits) → int                     # greedy next token id
verifier.n_vocab() → int                 # vocab size for argmax bound
```

This capability must be confirmed before Phase 3.12 implements strict token-level verification.

### Role names in traces and docs

```text
verifier_greedy_token_ids       : greedy token decisions from the verifier
verifier_greedy_token_count     : number of greedy decisions obtained
```

Avoid:

```text
gemma_greedy_token_ids  (model-specific name — deprecated)
target_greedy_token_ids (reserved for Phase 4.0+ target model)
```

## Token Comparison Algorithm

### Algorithm

```python
def compare_tokens(
    candidate_verifier_token_ids: list[int],
    verifier_greedy_token_ids: list[int],
) -> ComparisonResult:
    """
    Compare candidate verifier tokens against verifier greedy tokens.

    Returns:
        matched_verifier_token_count : number of matched tokens from the left
        first_rejection_position     : index of first mismatch (None if full match)
        verification_result          : "full_accept" | "partial_accept" | "full_reject"
    """
    matched = 0
    for i, (c_tok, v_tok) in enumerate(
        zip(candidate_verifier_token_ids, verifier_greedy_token_ids)
    ):
        if c_tok == v_tok:
            matched += 1
        else:
            return ComparisonResult(
                matched_verifier_token_count=matched,
                first_rejection_position=i,
                verification_result="partial_accept" if matched > 0 else "full_reject",
            )
    # All candidate tokens matched
    return ComparisonResult(
        matched_verifier_token_count=matched,
        first_rejection_position=None,
        verification_result="full_accept",
    )
```

### States

```text
full_accept    : all candidate_verifier_token_ids match verifier_greedy_token_ids
                 matched_verifier_token_count == candidate_verifier_token_count
                 first_rejection_position = None

partial_accept : matched_verifier_token_count > 0 and < candidate_verifier_token_count
                 first_rejection_position = index of first mismatch

full_reject    : matched_verifier_token_count == 0
                 first_rejection_position = 0
                 fallback starts from verifier greedy position 0
```

### Length mismatch handling

```text
If len(verifier_greedy_token_ids) < len(candidate_verifier_token_ids):
    compare up to len(verifier_greedy_token_ids)
    remaining candidate tokens are rejected if stop token was reached by verifier

If len(candidate_verifier_token_ids) == 0:
    full_reject immediately, trigger fallback
```

### Stop token handling

```text
If verifier greedy produces a stop token at position j:
    compare up to position j
    accept tokens [0..j-1] if they match
    context update includes the stop token behavior (EOS → terminate cycle)
```

## Partial Match and First Rejection Position

### Partial match semantics

Phase 3.11 designs partial prefix match semantics.

Phase 3.12 may implement the simplest strict prototype first (full block accept/reject only) and add partial prefix accept later.

Partial prefix match:

```text
accepted span = candidate_verifier_token_ids[0 : first_rejection_position]
rejected span = candidate_verifier_token_ids[first_rejection_position]  (single token)
unused suffix = candidate_verifier_token_ids[first_rejection_position + 1 :]
```

The unused suffix is not counted as rejected.

It is silently discarded because verification stops at the first mismatch.

This matches the D-Flash invariant:

```text
unused_suffix = [d, e]  →  discarded, not rejected
```

### first_rejection_position

```text
first_rejection_position : int | None

None   → full accept (no mismatch)
0      → full reject (no tokens accepted)
i > 0  → partial accept (tokens 0..i-1 accepted, token i rejected)
```

This field is reserved for the trace schema. Phase 3.11 does not emit it from live runtime.

## Acceptance Semantics

A verifier token candidate is accepted (at position i) only if:

```text
1. candidate_text passed text bridge validation.
2. candidate_verifier_token_ids were derived under the verifier tokenizer from context + candidate.
3. verifier_greedy_token_ids were produced under deterministic settings (temperature=0.0, greedy).
4. candidate_verifier_token_ids[i] == verifier_greedy_token_ids[i].
5. The context has not diverged from the verifier baseline.
```

Accepted units are:

```text
verifier-side token ids   (NOT drafter token ids)
```

The accepted token count is:

```text
accepted_target_token_count = matched_verifier_token_count
```

This field is a future design field. Phase 3.11 does not emit it from runtime.

The accepted token count must not be confused with:

```text
draft_block_size        (drafter-side limit, not acceptance count)
bridge_valid_block_count  (bridge-level structural metric, not acceptance metric)
```

## Rejection Semantics

A candidate token is rejected at position i if:

```text
candidate_verifier_token_ids[i] != verifier_greedy_token_ids[i]
```

Additional rejection triggers:

```text
tokenizer conversion fails or is ambiguous
verifier greedy decisions cannot be produced
candidate is empty after bridge normalization
stop token behavior is ambiguous at the boundary
context state cannot be aligned between drafter and verifier
```

Rejection metadata (future trace fields):

```text
first_rejection_position    : index of first mismatching token
rejection_reason            : reason string (token_mismatch, empty_candidate, tokenizer_error, etc.)
candidate_token_id          : candidate_verifier_token_ids[first_rejection_position]
verifier_token_id           : verifier_greedy_token_ids[first_rejection_position]
matched_verifier_token_count: count of tokens accepted before rejection
rejected_target_token_count : 1 (the mismatching token; unused suffix is NOT counted)
```

Bridge rejection is not target-token rejection.

`rejected_target_token_count` counts only the first mismatching token — not the unused suffix.

## Fallback Semantics

Fallback is triggered when:

```text
full_reject     : no candidate tokens matched (first_rejection_position == 0)
partial_accept  : some tokens matched, fallback starts at first_rejection_position
```

Fallback behavior:

```text
Step 1: Accept the matched prefix (0 or more tokens) into context.
Step 2: Use verifier_greedy_token_ids[first_rejection_position] as the fallback token.
Step 3: Append fallback token to strict context.
Step 4: Record fallback_reason.
Step 5: Discard unused candidate suffix.
Step 6: Begin next cycle from updated context.
```

Fallback invariant:

```text
Each cycle that triggers fallback must still commit at least 1 token.
(Either from accepted prefix, or from the fallback token itself.)
If fallback cannot produce a token, stop with no_progress_error.
```

Fallback count guard:

```text
Repeated fallback-only cycles (matched_verifier_token_count == 0 across multiple cycles)
should be logged as warnings.
They are not quality evidence, performance evidence, or correctness evidence.
```

Naming:

```text
fallback_reason         : reason string
fallback_token_id       : the verifier greedy token id used as fallback
cycle_fallback_count    : existing structural metric (not a correctness metric)
```

## Context Update Semantics

### Strict rule

Strict D-Flash context update after one cycle:

```text
accepted_prefix_text = decode(candidate_verifier_token_ids[0 : first_rejection_position])
fallback_text        = decode([verifier_greedy_token_ids[first_rejection_position]])

next_context = current_context + accepted_prefix_text + fallback_text
```

Or if full accept:

```text
accepted_text = decode(candidate_verifier_token_ids)
next_context  = current_context + accepted_text
```

### What must not update context

```text
rejected candidate suffix                 (never appended)
unverified drafter text                   (never appended in strict mode)
ambiguous tokenization output             (fallback to text-level if ambiguous)
display-cleaned text that differs from verifier token text
```

### Distinction from current pipeline

Current `generate.py` prototype appends:

```text
normalized_draft_text + verifier_result.text
```

This is incorrect for strict D-Flash because:

```text
it uses unverified drafter text in the context unconditionally
it does not accept only the verified prefix
```

Phase 3.12 must replace this with the strict context update rule.

### State isolation

The verifier context state must be managed independently of the drafter context state.

Do not share KV cache or hidden states between drafter and verifier in the low-tier D-Flash path.

Design fields:

```text
context_update_source   : "accepted_prefix" | "fallback_only" | "full_accept"
context_length_before   : character/token count before update
context_length_after    : character/token count after update
```

## Trace Schema Requirements

Future trace fields for token-level verifier cycles.

These fields are design definitions for Phase 3.12+ implementation.

Phase 3.11 must not add these to live runtime output unless clearly marked as design-only or test fixture.

### Required future trace fields

```text
cycle_index                     : int
candidate_text                  : str
candidate_normalized_text       : str
candidate_verifier_token_ids    : list[int]
candidate_verifier_token_count  : int
verifier_greedy_token_ids       : list[int]
verifier_greedy_token_count     : int
matched_verifier_token_count    : int
first_rejection_position        : int | None
verification_result             : "full_accept" | "partial_accept" | "full_reject"
rejection_reason                : str | None
fallback_reason                 : str | None
accepted_target_token_count     : int
rejected_target_token_count     : int
unused_suffix_token_count       : int
context_update_source           : str
comparison_profile              : str
deterministic_settings          : dict
backend_capability_status       : dict
```

### Existing structural fields (unchanged, not renamed)

```text
bridge_valid_block_count        : bridge-level structural metric (NOT acceptance metric)
bridge_rejected_block_count     : bridge-level structural metric
cycle_fallback_count            : cycle-level fallback count (NOT correctness metric)
```

### Reserved but not emitted in Phase 3.11

```text
accepted_target_token_count
rejected_target_token_count
first_rejection_position
matched_verifier_token_count
```

These appear in this document as design field definitions only.

## Backend Capability Requirements

### Required capabilities for token-level verification

The following capabilities are required to implement Phase 3.12 strict token-level verification with `llama-cpp-python`:

| Capability | Status |
|---|---|
| Tokenize text → token ids (`llama.tokenize`) | **unknown** — present in llama-cpp-python API but requires testing |
| Decode token ids → text (`llama.detokenize`) | **unknown** — present in API but requires testing |
| Expose logits for next token position (`llama.get_logits`) | **unknown** — may require `logits_all=True` at load time |
| Evaluate context token ids (`llama.eval`) | **unknown** — present in low-level API but requires testing |
| Greedy argmax from logits | **supported** — can be computed from `get_logits` if logits are accessible |
| Step one token at a time | **unknown** — depends on `eval` + `get_logits` availability |
| Preserve / update KV cache across steps | **unknown** — depends on model load configuration |
| Reset or isolate context per cycle | **unknown** — may require model reload or reset logic |
| Deterministic output (temperature=0.0, seed) | **partially supported** — current backend passes seed and temperature |
| Stop token detection | **partially supported** — stop sequences passed to `generate_text` |

### Current backend gap

The current `LlamaCppBackend` wrapper in `src/htfsd/runtime/llama_cpp_backend.py` exposes:

```text
generate_text(prompt, max_tokens, temperature, stop) → TextGenerationResult
generate_chat(messages, max_tokens, temperature, stop) → TextGenerationResult
```

It does not expose:

```text
tokenize(text) → list[int]
detokenize(token_ids) → str
eval(token_ids) → None
get_logits() → list[float]
```

Phase 3.12 will need to either:

```text
A. Extend LlamaCppBackend to expose tokenizer and logit step APIs.
B. Use Approach A text-generation-based fallback for the first prototype.
C. Confirm API availability by probing llama-cpp-python version capabilities before extending.
```

### Non-capability

The current backend explicitly declares:

```text
supports_hidden_states = False
```

Hidden-state extraction is not available and is not required for D-Flash low-tier verification.

### Capability contract for Phase 3.12

Before Phase 3.12 implements strict token-level verification, the following must be confirmed:

```text
1. llama-cpp-python version in the project's .venv
2. whether llama.tokenize is accessible and correct
3. whether llama.eval + llama.get_logits are accessible
4. whether logits_all flag is required at model load time
5. whether per-cycle context reset is supported without model reload
6. whether the KV cache is predictably managed across eval calls
```

## llama-cpp-python / GGUF Constraints

Architectural constraints for the GGUF/llama-cpp-python low-tier path:

```text
1. Do not switch to vLLM. The runtime is GGUF + llama-cpp-python.

2. Do not share KV cache between drafter and verifier.
   Drafter = Qwen3-0.6B (CPU). Verifier = Gemma E2B (CUDA).
   They are separate llama-cpp-python model instances.

3. Do not use hidden states for speculative decoding in Phase 3.11 or Phase 3.12.
   supports_hidden_states = False is correct for the current backend.

4. Do not use EAGLE-style speculation. That belongs to Phase 4.0+.

5. Token-level access may require lower-level llama-cpp-python APIs
   that the current LlamaCppBackend does not expose.
   Extending the backend must preserve existing generate_text / generate_chat interfaces.

6. Tokenizer behavior may be version-sensitive.
   The exact llama-cpp-python version must be recorded in deterministic settings.

7. Greedy token decisions are sensitive to seed, temperature, and n_ctx.
   All must be fixed for reproducible verification.

8. Per-cycle context reset strategy is an open design question.
   Options: stateless re-evaluation per cycle vs. stateful KV cache management.
   Stateless is safer for the first Phase 3.12 prototype.
```

## Deterministic Settings

All correctness/equivalence work requires:

```text
temperature    = 0.0
decoding       = greedy (argmax)
seed           = fixed (per session or per test)
prompt_mode    = stable (chat or instruction, not mixed per run)
context update = strict (only verified/fallback tokens update context)
stop handling  = identical stop sequences for drafter and verifier
normalization  = defined comparison profile (inherit from Phase 3.10)
model identity = model file path recorded in trace
runtime version= llama-cpp-python version recorded in trace
```

Correctness/equivalence claims remain forbidden until Phase 3.13 validation.

Deterministic settings fields for traces:

```text
deterministic_settings:
    temperature         : 0.0
    decoding            : "greedy"
    seed                : int
    prompt_mode         : str
    model_path_drafter  : str
    model_path_verifier : str
    llama_cpp_version   : str
    comparison_profile  : str
```

## Failure Modes

Anticipated failure modes for the token-level verifier:

```text
1. tokenizer_unavailable
   llama-cpp-python tokenize API not accessible.
   Mitigation: fall back to text-level verification (Phase 3.10 Option A).

2. tokenizer_boundary_error
   candidate tokenization produces different results when tokenized
   in isolation vs. as context continuation.
   Mitigation: always tokenize context + candidate together, derive suffix.

3. logits_unavailable
   get_logits not accessible without logits_all=True at load time.
   Mitigation: use Approach A (generate continuation text, tokenize result).

4. context_reset_failure
   cannot reset verifier context between cycles without model reload.
   Mitigation: use stateless full-context re-evaluation per cycle.

5. stop_token_ambiguity
   stop token appears mid-candidate, splitting accepted and fallback spans.
   Mitigation: truncate candidate at stop token, accept prefix only.

6. empty_candidate_after_normalization
   bridge produces empty text after normalization.
   Mitigation: treat as bridge rejection, use verifier fallback.

7. no_progress
   repeated fallback-only cycles with matched_verifier_token_count == 0.
   Mitigation: detect no-progress condition, log warning, stop if persistent.

8. context_divergence
   drafter context and verifier context diverge unexpectedly.
   Mitigation: always reconstruct full verifier context from the strict context log.
```

## Metrics Naming Rules

Current structural metrics remain:

```text
bridge_valid_block_count    : bridge-level structural count (NOT acceptance metric)
bridge_rejected_block_count : bridge-level structural count
cycle_fallback_count        : cycle-level fallback count (NOT correctness or performance metric)
```

Do not rename:

```text
bridge_valid_block_count  → accepted_blocks
bridge_valid_block_count  → acceptance_count
cycle_fallback_count      → success_count
cycle_fallback_count      → quality_metric
```

Future token-level metrics (Phase 3.12+):

```text
accepted_target_token_count     : verifier tokens accepted per cycle
rejected_target_token_count     : mismatching token count (1 per rejection event)
matched_verifier_token_count    : tokens matched in the comparison prefix
unused_suffix_token_count       : candidate tokens discarded after first mismatch
```

These are future design field definitions only. Phase 3.11 does not add them to runtime.

## Implementation Boundary for Phase 3.12

Phase 3.12 is the strict acceptance/rejection prototype.

Phase 3.12 may choose to start with:

```text
Option A (simplest): full block accept/reject only.
    If all candidate_verifier_token_ids match, accept the block.
    If any mismatch, reject the entire block and use verifier fallback.
    Implement partial prefix accept in a later sub-phase.

Option B (full design): partial prefix accept from the first prototype.
    Implement the full comparison algorithm from Phase 3.11.
```

Phase 3.11 designs both options. Phase 3.12 decides which to implement first.

The Phase 3.12 prototype must:

```text
1. Confirm or resolve backend capability status (tokenize, logits).
2. Add verifier tokenizer access to LlamaCppBackend without breaking existing interfaces.
3. Implement the comparison algorithm.
4. Implement strict context update (no unverified drafter text in context).
5. Implement no-progress guard.
6. Add token-level trace fields.
7. Add equivalence tests (Phase 3.13 scope).
```

Phase 3.12 must not claim correctness or benchmark results.

Phase 3.12 must not start high-tier.

## Risks and Open Questions

Open design questions for Phase 3.12:

```text
1. Can llama-cpp-python expose tokenize / eval / get_logits in the project's current version?
   Status: unknown. Must be probed before Phase 3.12 implementation.

2. What exact normalization profile should Phase 3.12 use for candidate text before tokenization?
   Status: inherit from Phase 3.10 bridge normalization. Document explicitly in Phase 3.12.

3. How should fallback length be bounded for baseline-comparable output?
   Status: Phase 3.11 design specifies exactly 1 fallback token per rejection event.
   Phase 3.12 must enforce this bound.

4. How should stop sequences interact with partial candidate prefix acceptance?
   Status: truncate candidate at stop token, accept prefix only.
   Detailed stop token handling must be specified in Phase 3.12.

5. Can deterministic settings remain stable across cycles with KV cache reuse?
   Status: unknown. Stateless full-context re-evaluation is the safer approach for Phase 3.12.

6. How should the combined context+candidate tokenization handle BOS/EOS special tokens?
   Status: BOS and EOS must be excluded from candidate_verifier_token_ids. Exact handling
   depends on llama-cpp-python tokenize behavior with special tokens.

7. When candidate_verifier_token_ids length < verifier_greedy_token_ids length (or vice versa),
   how should the length mismatch be handled?
   Status: compare up to min(len(c), len(v)). Design specified above. Phase 3.12 must test.

8. Should the first Phase 3.12 prototype use full block accept/reject (Option A)
   or partial prefix accept (Option B)?
   Status: open question for Phase 3.12 design decision. Both are defined here.
```

Risks:

```text
1. If tokenize API is not accessible, Phase 3.12 must fall back to text-level verification.
   This delays full token-level correctness but does not block the prototype.

2. If logits are not accessible without model reload with logits_all=True,
   Phase 3.12 must use Approach A (generate then tokenize), which introduces boundary risk.

3. If per-cycle context reset requires model reload, performance will be severely impacted.
   The verifier must be designed for stateless re-evaluation or context padding.

4. SentencePiece boundary-sensitive tokenization may produce non-intuitive candidate token splits.
   Tests must cover edge cases: leading spaces, newlines, Unicode, empty strings.
```

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

It is not correctness evidence.

`matched_verifier_token_count` is a future design field for Phase 3.12+.

It must not be added to Phase 3.11 runtime output.

It is not an acceptance-rate field.

It is not a performance field.

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

No acceptance rate is measured.

No EAGLE-style speculation is implemented.

No vLLM path is introduced.

Phase 3.11 is a token-level verifier design phase.

This is not yet a D-Flash/speculative decoding correctness implementation.

## Conclusion

Phase 3.11 defines the token-level verifier design for the HTFSD D-Flash low-tier path.

The central design principle is:

```text
Gemma verifies candidate Gemma tokens derived from Qwen draft text.
```

The design specifies:

```text
candidate tokenization via verifier tokenizer (combined context+candidate approach)
verifier greedy decision source (preferred: eval+logits; fallback: generate-then-tokenize)
token comparison algorithm (left-to-right, first mismatch = rejection point)
partial prefix acceptance semantics
strict context update rule (only accepted+fallback tokens update context)
token-level trace schema (reserved fields for Phase 3.12+)
backend capability requirements (tokenize, eval, logits — currently unknown/unverified)
failure mode catalog
```

Backend capability for full token-level implementation is currently **unknown**.

The Phase 3.12 prototype must probe and confirm `llama-cpp-python` tokenizer and logit API availability before implementing strict token-level verification. If blocked, Phase 3.12 should implement text-level verification first and preserve this token-level design for when backend capability is confirmed.

## Next Step

Recommended next phase:

```text
Phase 3.12: Strict Acceptance/Rejection Prototype
```

Phase 3.12 should begin by probing `llama-cpp-python` tokenizer and logit API availability, then implement the simplest strict verification prototype that satisfies D-Flash correctness invariants.
