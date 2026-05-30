# Phase 3.13 Correctness/Equivalence Validation Harness

## Status

Validation harness implemented and tested.

Phase 3.13 does not claim correctness is production-validated.

Phase 3.13 does not measure throughput, speedup, or benchmark results.

Phase 3.13 does not implement high-tier or EAGLE-style speculation.

## What Changed

New source files:

```text
src/htfsd/validation/__init__.py
src/htfsd/validation/equivalence.py
src/htfsd/validation/fake_harness.py
```

New test files:

```text
tests/test_phase_3_13_equivalence_harness.py
tests/test_phase_3_13_fake_validation.py
```

New report:

```text
docs/reports/phase-3-13-correctness-equivalence-validation-harness.md
```

No modifications to existing runtime files.

No modifications to `src/htfsd/low_tier/generate.py`.

No modifications to `src/htfsd/runtime/llama_cpp_backend.py`.

No modifications to Phase 3.12 modules.

## Current Roadmap

```text
Phase 3.8  = Runtime log/output cleanliness
Phase 3.9  = Low-tier generation pipeline closure
Phase 3.10 = D-Flash correctness specification
Phase 3.11 = Token-level verifier design
Phase 3.12 = Strict acceptance/rejection prototype
Phase 3.13 = Correctness/equivalence validation harness   ← CURRENT PHASE
Phase 3.14 = Low-tier benchmark protocol/spec
Phase 3.15 = Low-tier benchmark dry run + Low-Tier D-Flash MVP closure report
Phase 4.0+ = High-tier preparation / feature-level speculative decoding
```

Phase 3.13 stayed within validation harness scope.

No Phase 3.14 or 3.15 work was started.

No high-tier work was started.

## Prior Prototype

Phase 3.12 implemented the strict acceptance/rejection prototype.

Phase 3.12 commit: `6de2500 feat: prototype strict token verification`

Merge commit: `4866df2 feat: phase 3.12 strict acceptance rejection prototype`

Phase 3.12 established:

```text
compare_candidate_to_greedy()    — pure strict token comparison (no model)
VerificationDecision             — frozen dataclass with full accounting
full accept / partial accept / full reject
first rejection position
unused suffix accounting         — unused suffix ≠ rejected
one-token fallback semantics
LlamaCppCapabilityStatus         — static backend API classification
derive_candidate_suffix()        — combined tokenization suffix derivation
```

Phase 3.13 builds on Phase 3.12 by wrapping the pure algorithm in a simulation
harness that can compare cycle sequences end-to-end against a deterministic baseline.

## Validation Scope

Phase 3.13 validates the strict D-Flash algorithm under controlled fake conditions.

Phase 3.13 does not validate real model outputs.

Phase 3.13 does not require a loaded GGUF model for unit tests.

Optional local model tests are possible but are gated by caller code and are not
implemented as default tests in this phase.

Phase 3.13 validates:

```text
1. That the pure comparison algorithm + cycle simulator produce the correct output
   token sequence when given a deterministic baseline and candidate batches.
2. That unused suffix tokens never enter the committed output.
3. That fallback tokens equal the expected verifier greedy token.
4. That divergence detection reports the first incorrect token position.
5. That max_new_tokens and max_cycles bounds are respected.
6. That EOS terminates generation.
7. That no_progress_error is reported when no fallback is available.
8. That repeated fallback-only cycles produce warnings (not speedup evidence).
```

## Validation Modes

### Mode A — Pure Token Harness (implemented)

Inputs:

```text
baseline_token_ids    — verifier greedy reference sequence (deterministic, fake)
candidate_batches     — one list of candidate token IDs per cycle
```

Outputs:

```text
EquivalenceResult
    .status:            "equivalent" | "divergent" | "inconclusive"
    .baseline:          BaselineRunResult
    .strict:            StrictRunResult
    .divergence:        DivergenceReport
    .cycle_count:       number of cycles run
    .warnings:          list of warning strings
```

Does not require a real model. Fully tested with fake token IDs.

### Mode B — Fake Text Harness (not implemented in Phase 3.13)

Would use fake decode/token maps to compare text output.

Deferred to Phase 3.14 or later if needed.

### Mode C — Optional llama-cpp Local Harness (not implemented in Phase 3.13)

Would use a real loaded llama_cpp.Llama instance.

Deferred to Phase 3.14 or later, gated by environment variable/config.

## Equivalence Definition

Equivalence is defined as:

```text
strict.token_ids == baseline.token_ids
```

Token-by-token equality, left-to-right.

Stop reason mismatches between the two paths are recorded as warnings but do not
count as divergence. This is correct because:

```text
baseline may stop at max_tokens (budget consumed).
strict may stop at max_cycles (candidate batches exhausted).
Both may produce the same token sequence despite different stop reasons.
```

Equivalence does not imply:

```text
correctness validated
production lossless generation
target Gemma E4B equivalence
benchmark-grade performance equivalence
```

## Baseline-vs-Strict Comparison

Implemented in `compare_outputs()` in `equivalence.py`.

Steps:

```text
1. Length check: if len(baseline.token_ids) != len(strict.token_ids):
       status = divergent
       divergence_reason = length_mismatch
       divergence_position = min(len(baseline), len(strict))

2. Token-by-token check: for i, (b, s) in enumerate(zip(baseline_ids, strict_ids)):
       if b != s:
           status = divergent
           divergence_reason = token_mismatch
           divergence_position = i
           baseline_token = b
           strict_token = s

3. Stop reason check:
       if baseline.stop_reason != strict.stop_reason:
           warning recorded (not divergence)

4. All checks passed:
       status = equivalent
       divergence_reason = none
```

## Divergence Reporting

`DivergenceReport` captures:

```text
divergence_position:  index into token sequence (None if no divergence)
divergence_reason:    token_mismatch | length_mismatch | unused_suffix_leaked
                      | rejected_token_leaked | wrong_fallback_token
                      | stop_reason_mismatch | none
baseline_token:       expected token at divergence position
strict_token:         actual strict-path token at divergence position
detail:               human-readable detail string
has_divergence:       bool property (reason != "none")
```

Divergence examples caught by the harness:

```text
unused suffix leaked into strict output   →  length_mismatch (output too long)
wrong fallback token used                 →  token_mismatch at fallback position
rejected candidate token kept in output   →  token_mismatch or length_mismatch
```

## Invariant Coverage

The harness tests or supports checking these D-Flash invariants:

```text
 1. accepted tokens equal verifier greedy baseline tokens      [tested]
 2. fallback tokens equal verifier greedy baseline tokens      [tested]
 3. strict output token sequence equals baseline sequence      [tested]
 4. unused suffix tokens never enter strict output             [tested]
 5. rejected token counted as exactly one at first mismatch    [inherited from Phase 3.12]
 6. unused suffix not counted as rejected                      [inherited from Phase 3.12]
 7. fallback-only cycles commit exactly one token              [tested]
 8. no fallback → no_progress_error                            [tested]
 9. EOS terminates normally                                    [tested]
10. max_new_tokens bounds output length                        [tested]
11. max_cycles bounds loop execution                           [tested]
12. repeated fallback-only cycles produce warnings             [tested]
```

## Fake Harness

Implemented in `fake_harness.py`.

Key functions:

```text
run_fake_baseline(baseline_token_ids, max_new_tokens, eos_token_id)
    Simulates verifier greedy baseline run using predetermined token sequence.
    Returns BaselineRunResult.

run_fake_strict(baseline_token_ids, candidate_batches, max_new_tokens, max_cycles, eos_token_id)
    Simulates D-Flash strict cycle loop.
    Each cycle: compare candidate batch vs greedy window from baseline_token_ids.
    Commits accepted prefix + fallback.
    Discards unused suffix.
    Returns (StrictRunResult, list[CycleRecord]).

run_validation_case(case: ValidationCase)
    Runs a complete validation case: baseline + strict + comparison.
    Returns EquivalenceResult.

CycleRecord
    Per-cycle tracking: candidate_token_ids, VerificationDecision,
    committed_token_ids, context_update_source, unused_suffix_detected, warning.
```

Predefined `ValidationCase` fixtures (no model required):

```text
case_full_accept()
case_partial_accept_with_fallback()
case_full_reject_with_fallback()
case_max_new_tokens_truncation()
case_unused_suffix_leak_detection()
case_eos_termination()
case_no_progress_error()
```

EOS sentinel: `FAKE_EOS_TOKEN_ID = 999` (avoids collision with small integer test token IDs).

## Optional Local Model Harness

Not implemented in Phase 3.13.

For Phase 3.14 or later:

```text
1. Extend LlamaCppBackend with thin VerifierTokenAccess layer
   (expose tokenize, eval, sample, reset, token_eos)
2. Use real llama_cpp.Llama to produce baseline_token_ids
3. Use real verifier tokenizer in derive_candidate_suffix()
4. Use real eval() + sample(temp=0.0) for greedy decisions
5. Gate with environment variable or config path
```

Do not require real model execution in default unit tests.

## Tests

New test files:

```text
tests/test_phase_3_13_equivalence_harness.py  — 27 tests
tests/test_phase_3_13_fake_validation.py      — 27 tests
```

Total new tests: 54 passed.

All tests require no GGUF model, no GPU, no disk access.

Key test coverage:

```text
full accept: strict equals baseline (compare_outputs + run_validation_case)
partial accept + fallback: strict equals baseline
full reject + fallback: strict equals baseline
strict output does not include unused suffix
harness detects unused suffix leak (length_mismatch)
harness detects wrong fallback token (token_mismatch at fallback position)
harness detects output length mismatch
harness reports first divergence position correctly
max_new_tokens truncates both baseline and strict consistently
max_cycles bound stops iteration
no_progress_error: empty baseline + empty candidate
EOS terminates generation; tokens after EOS absent from output
repeated fallback-only cycles produce warnings (not speedup evidence)
CycleRecord tracks decision, committed tokens, context_update_source
compare_outputs: equivalent sequences
compare_outputs: first/middle/last token mismatch
compare_outputs: strict longer / shorter than baseline
stop reason mismatch is a warning, not a divergence
check_unused_suffix_leak(): no leak / single token / multi-token
make_divergence_from_leaked_suffix()
BaselineRunResult / StrictRunResult: frozen, correct fields
ValidationCase: defaults and construction
Forbidden field names absent from EquivalenceResult / StrictRunResult
```

## Verification

```text
focused tests (Phase 3.13):
    test_phase_3_13_equivalence_harness.py : 27 passed
    test_phase_3_13_fake_validation.py     : 27 passed

prior phase tests:
    test_phase_3_12_strict_accept_reject.py  : 33 passed
    test_phase_3_12_token_bridge.py          : 20 passed
    test_phase_3_12_backend_capabilities.py  : 18 passed, 1 skipped
    test_phase_3_11_token_level_verifier_design.py : 23 passed
    test_phase_3_10_dflash_correctness_spec.py     : 5 passed

full suite:
    346 passed, 1 skipped, 1 pre-existing failure
    (test_prompt_sets.py::test_prompt_registry_reports_available_ids
     pre-existing on main before Phase 3.13 — not introduced by Phase 3.13)

forbidden-claim scan: clean
git diff --check: exit=0
```

## Remaining Limitations

Phase 3.13 does not implement:

```text
Wrapper extension for LlamaCppBackend
    - tokenize, eval, sample are still not exposed through LlamaCppBackend
    - Phase 3.14 or local model harness scope

Full runtime strict verifier loop wired into generate.py
    - generate.py is unchanged
    - The harness is a standalone simulator, not connected to live inference

Real model equivalence validation
    - All tests use deterministic fake token IDs
    - No GGUF model was loaded in Phase 3.13

Text-level equivalence comparison (Mode B)
    - Token ID equality is sufficient for Phase 3.13
    - Text-level comparison deferred

Benchmark protocol or runner
    - Phase 3.14–3.15 scope

High-tier / EAGLE-style speculation
    - Phase 4.0+ scope
```

Stop reason matching is not enforced as divergence. Stop reason mismatches between
baseline (max_tokens) and strict (max_cycles) are expected when both paths produce
the same token sequence but exhaust their respective budgets via different mechanisms.

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

Fake harness equivalence under controlled conditions does not imply
production-grade correctness or lossless generation.

## Non-Claims

This is not a benchmark report.

This is not a performance comparison.

This is not D-Flash correctness validation for production use.

No speedup claim is made.

No low-tier benchmark claim is made.

No throughput measurement is made.

No performance-improvement claim is made.

No production lossless-generation claim is made.

No target Gemma E4B equivalence claim is made.

No high-tier implementation claim is made.

No token-level acceptance rate is reported.

No EAGLE-style speculation is implemented.

No vLLM integration is introduced.

Equivalence under deterministic fake conditions does not imply production correctness.

Phase 3.13 is a validation harness phase.

This is not yet a D-Flash/speculative decoding correctness certification.

## Error Reports

Five test failures on first run:

```text
1. FAKE_EOS_TOKEN_ID was set to 2, which collides with small integer test token IDs
   (token 2 in sequence [1,2,3] triggered EOS early).
   Fixed: changed FAKE_EOS_TOKEN_ID to 999.

2. run_fake_baseline max_new_tokens off-by-one: the check was before append,
   so max_new_tokens=3 produced only 2 tokens.
   Fixed: check moved to after append.

3. compare_outputs treated stop_reason mismatch as a divergence.
   "max_tokens" (baseline) vs "max_cycles" (strict) are expected when both paths
   produce the same tokens but exhaust budgets differently.
   Fixed: stop_reason mismatch demoted to a warning.

4. test_compare_outputs_stop_reason_mismatch was written to expect divergence.
   Fixed: test updated to expect equivalence + warning.

5. ValidationCase fixtures (full_accept, partial_accept, full_reject) failed
   because of the EOS/stop_reason bugs above.
   Fixed: by the above fixes.
```

## Commit

Pending. Files ready for commit.

## Next Step

Recommended next phase:

```text
Phase 3.14: Low-tier benchmark protocol/spec
```

Phase 3.14 should begin by:

```text
1. Defining the benchmark protocol (not running it yet)
2. Specifying metrics to be measured (latency, throughput, token output length)
3. Specifying what "dry run" means in Phase 3.15
4. Specifying the baseline comparison approach
5. NOT measuring speedup or making performance claims yet
```

Do not start Phase 3.15 benchmark execution in Phase 3.14.

Do not start high-tier in Phase 3.14.
