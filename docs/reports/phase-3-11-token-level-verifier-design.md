# Phase 3.11 Token-Level Verifier Design

## Status

Design phase.

Phase 3.11 designs the token-level verifier. It does not implement or validate correctness.

## What Changed

Created the main design specification:

```text
docs/specs/phase-3-11-token-level-verifier-design.md
```

Added lightweight documentation tests to verify that the design specification preserves required boundaries:

```text
tests/test_phase_3_11_token_level_verifier_design.py
```

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
Phase 3.14 = Low-tier benchmark protocol/spec
Phase 3.15 = Low-tier benchmark dry run + Low-Tier D-Flash MVP closure report
Phase 4.0+ = High-tier preparation / feature-level speculative decoding
```

Phase 3.11 stayed within design scope.

## Prior Specification

Phase 3.10 defined correctness semantics at the text-prefix level.

Phase 3.10 commit: `13022de docs: define dflash correctness specification`

Phase 3.10 reserved token-level trace fields:

```text
accepted_target_token_count
rejected_target_token_count
first_rejection_position
```

Phase 3.11 now designs the semantics for these reserved fields.

## Design Summary

The central design principle is:

```text
Gemma verifies candidate Gemma tokens derived from Qwen draft text.
```

Not:

```text
Gemma verifies Qwen tokens.
```

The D-Flash token-level loop:

```text
1. Drafter produces draft_text_chunk.
2. Bridge normalizes/validates → candidate_text.
3. candidate_text tokenized via verifier tokenizer → candidate_verifier_token_ids.
4. Verifier produces greedy decisions → verifier_greedy_token_ids.
5. Tokens compared left to right.
6. Longest matching prefix is accepted.
7. First mismatch → rejected_position, fallback starts.
8. Context updated with accepted prefix + fallback token only.
9. Unused candidate suffix is discarded (not rejected).
```

## Tokenizer Mismatch

Drafter (Qwen3-0.6B) and verifier (Gemma E2B) use different tokenizers.

```text
draft_block_size = 8  →  8 Qwen-side draft tokens
                      →  NOT 8 Gemma target tokens
```

Qwen token ids and Gemma token ids are not comparable.

Qwen draft text must be tokenized with the Gemma tokenizer before any token-level comparison is defined.

Canonical naming:

```text
candidate_verifier_token_ids   (NOT: qwen_token_ids, draft_token_ids)
verifier_greedy_token_ids      (NOT: gemma_greedy_token_ids, target_greedy_token_ids)
```

Role-based naming is preferred:

```text
drafter_*   (canonical)
verifier_*  (canonical)
target_*    (reserved for Phase 4.0+ target model)
```

## Candidate Tokenization

The design uses combined context+candidate tokenization:

```text
tokens_context               = verifier.tokenize(current_context_text)
tokens_context_plus_candidate = verifier.tokenize(current_context_text + draft_text_chunk)
candidate_verifier_token_ids  = tokens_context_plus_candidate[len(tokens_context):]
```

Tokenizing the candidate alone risks boundary-sensitive tokenization errors (leading spaces,
SentencePiece word boundary effects). Combined tokenization then suffix extraction is the
safer approach.

Boundary conditions designed:

```text
Empty candidate after normalization → bridge rejection, trigger fallback
BOS/EOS tokens excluded from candidate_verifier_token_ids
Stop tokens truncate the candidate sequence
```

## Verifier Greedy Decision Source

Preferred approach (B): token/logit step:

```text
eval context tokens → get_logits → argmax → greedy token id → repeat
```

Fallback approach (A): generate-then-tokenize:

```text
generate verifier continuation greedily → tokenize result → use as verifier_greedy_token_ids
```

Text-level fallback (C): Phase 3.10 Option A:

```text
If neither approach is available, use strict text-prefix verification.
Token-level design is preserved for when backend capability is confirmed.
```

## Token Comparison Algorithm

```text
Compare candidate_verifier_token_ids against verifier_greedy_token_ids left to right.

full_accept    : all tokens match → accept all, no fallback
partial_accept : prefix matches → accept prefix, fallback at first_rejection_position
full_reject    : first token mismatches → fallback at position 0
```

`first_rejection_position` is a future trace field — not emitted by Phase 3.11 runtime.

## Partial Match and First Rejection Position

Partial prefix semantics:

```text
accepted span   = candidate_verifier_token_ids[0 : first_rejection_position]
rejected span   = candidate_verifier_token_ids[first_rejection_position]     (1 token)
unused suffix   = candidate_verifier_token_ids[first_rejection_position + 1:]  (discarded)
```

The unused suffix is not counted as rejected. It is discarded because verification stops at
the first mismatch. This matches D-Flash invariants.

Phase 3.12 may implement full block accept/reject first (Option A) and add partial prefix
accept later (Option B). Both options are designed here.

## Acceptance Semantics

A candidate token at position i is accepted only if:

```text
candidate_text passed bridge validation
candidate_verifier_token_ids derived from verifier tokenizer (context + candidate)
verifier_greedy_token_ids produced under deterministic settings (temperature=0.0, greedy)
candidate_verifier_token_ids[i] == verifier_greedy_token_ids[i]
context has not diverged from the verifier baseline
```

Accepted units are verifier-side (Gemma-side) token ids.

`accepted_target_token_count` is a future design field only. Not emitted in Phase 3.11.

## Rejection Semantics

A candidate token at position i is rejected if:

```text
candidate_verifier_token_ids[i] != verifier_greedy_token_ids[i]
```

Rejection metadata (future trace fields):

```text
first_rejection_position
rejection_reason
candidate_token_id
verifier_token_id
matched_verifier_token_count
rejected_target_token_count  (1 per rejection event; unused suffix NOT counted)
```

Bridge rejection is not target-token rejection.

## Fallback Semantics

Fallback produces exactly one verifier greedy token from the rejection point:

```text
fallback_token_id = verifier_greedy_token_ids[first_rejection_position]
```

Context update after fallback:

```text
next_context = current_context + accepted_prefix_text + fallback_token_text
```

No-progress guard:

```text
If matched_verifier_token_count == 0 across repeated consecutive cycles,
log a warning. Stop if the condition is persistent.
```

Fallback count is not quality evidence, performance evidence, or correctness evidence.

## Context Update Semantics

Strict context update rule:

```text
next_context = current_context + accepted_prefix_text + fallback_token_text
```

Or on full accept:

```text
next_context = current_context + accepted_full_text
```

Must not update context with:

```text
rejected candidate suffix
unverified drafter text
ambiguous tokenization output
display-cleaned text that differs from verifier token text
```

Current `generate.py` prototype does not implement this rule. Phase 3.12 must replace the
current context update with the strict rule.

Drafter and verifier KV cache / context state must be managed independently.

## Trace Schema Requirements

Future token-level trace fields (Phase 3.12+):

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
context_update_source
comparison_profile
deterministic_settings
backend_capability_status
```

These are design-only field definitions in Phase 3.11. Not emitted by Phase 3.11 runtime.

## Backend Capability Requirements

Summary of `llama-cpp-python` GGUF capability status:

| Capability | Status |
|---|---|
| `llama.tokenize(text)` → `list[int]` | **unknown** — requires probing |
| `llama.detokenize(ids)` → `str` | **unknown** — requires probing |
| `llama.eval(token_ids)` | **unknown** — requires probing |
| `llama.get_logits()` | **unknown** — requires `logits_all=True` at load |
| Greedy argmax from logits | **supported** (can compute if logits accessible) |
| Step one token at a time | **unknown** |
| Per-cycle KV cache reset | **unknown** |
| Deterministic (temperature=0.0, seed) | **partially supported** |
| Stop token detection | **partially supported** |

Current `LlamaCppBackend` gap:

```text
Only exposes: generate_text, generate_chat
Missing: tokenize, eval, get_logits
```

Phase 3.12 must probe and resolve these capabilities before implementing strict token-level verification.

Do not switch to vLLM. Do not share KV cache between drafter and verifier.

## Deterministic Settings

All correctness work requires:

```text
temperature    = 0.0
decoding       = greedy
seed           = fixed
prompt_mode    = stable
context update = strict
stop sequences = identical for drafter and verifier
normalization  = defined comparison profile
model identity = recorded in trace
runtime version= llama-cpp-python version recorded
```

Correctness/equivalence claims remain forbidden until Phase 3.13 validation.

## Metrics Naming Rules

Current structural metrics remain (unchanged):

```text
bridge_valid_block_count    : bridge-level diagnostic (NOT acceptance metric)
bridge_rejected_block_count : bridge-level diagnostic
cycle_fallback_count        : cycle-level fallback count (NOT correctness or performance)
```

Do not rename these to acceptance metrics.

Future token-level metrics (Phase 3.12+):

```text
accepted_target_token_count
rejected_target_token_count
matched_verifier_token_count
unused_suffix_token_count
```

Not added to runtime in Phase 3.11.

## Verification

```text
design tests  : see tests/test_phase_3_11_token_level_verifier_design.py
prior spec    : tests/test_phase_3_10_dflash_correctness_spec.py — 5 passed
full suite    : run after adding test file
forbidden-claim scan : clean (no positive performance, correctness, or equivalence claims)
git diff --check     : clean
```

## Remaining Limitations

Phase 3.11 does not implement:

```text
token-level runtime verifier
strict accept/reject behavior
correctness validation harness
baseline equivalence test
benchmark code
high-tier behavior
vLLM integration
```

Backend capability for token-level verification is currently **unknown**.

Phase 3.12 must probe and confirm before implementation.

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

No vLLM path is introduced.

Phase 3.11 is a token-level verifier design phase.

This is not yet a D-Flash/speculative decoding correctness implementation.

## Error Reports

No errors were encountered during Phase 3.11 design. The design specification was created from scratch based on Phase 3.10 correctness semantics, D-Flash invariants, and inspection of the current `LlamaCppBackend` implementation.

## Commit

Pending final commit.

## Next Step

Recommended next phase:

```text
Phase 3.12: Strict Acceptance/Rejection Prototype
```

Phase 3.12 should begin by probing `llama-cpp-python` tokenizer and logit API availability,
then implement the simplest strict verification prototype that satisfies D-Flash correctness invariants.
