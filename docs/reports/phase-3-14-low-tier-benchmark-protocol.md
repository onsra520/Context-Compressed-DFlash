# Phase 3.14 Low-tier Benchmark Protocol

## Status

Benchmark protocol/spec defined.

No benchmark results.

No speedup measurements.

No performance claims.

Phase 3.14 scope: protocol definition only.

## What Changed

New files:

```text
docs/specs/phase-3-14-low-tier-benchmark-protocol.md
docs/reports/phase-3-14-low-tier-benchmark-protocol.md
tests/test_phase_3_14_low_tier_benchmark_protocol.py
```

No modifications to existing runtime files.

No modifications to `src/htfsd/low_tier/generate.py`.

No modifications to `src/htfsd/runtime/llama_cpp_backend.py`.

No modifications to Phase 3.12 or Phase 3.13 modules.

## Current Roadmap

```text
Phase 3.8  = Runtime log/output cleanliness
Phase 3.9  = Low-tier generation pipeline closure
Phase 3.10 = D-Flash correctness specification
Phase 3.11 = Token-level verifier design
Phase 3.12 = Strict acceptance/rejection prototype
Phase 3.13 = Correctness/equivalence validation harness
Phase 3.14 = Low-tier benchmark protocol/spec           ← CURRENT PHASE
Phase 3.15 = Low-tier benchmark dry run + Low-Tier D-Flash MVP closure report
Phase 4.0+ = High-tier preparation / feature-level speculative decoding
```

Low-tier closure terminates at Phase 3.15.

Phase 3.14 stayed within protocol/spec scope.

No Phase 3.15 benchmark execution started.

No high-tier work started.

## Prior Phases

Phase 3.12 (strict accept/reject prototype):

```text
compare_candidate_to_greedy()
VerificationDecision
full accept / partial accept / full reject
first rejection position
unused suffix accounting
one-token fallback semantics
LlamaCppCapabilityStatus (static backend API classification)
```

Phase 3.13 (correctness/equivalence validation harness):

```text
EquivalenceResult / DivergenceReport / BaselineRunResult / StrictRunResult
compare_outputs() — pure equivalence comparison
run_fake_baseline() / run_fake_strict() / run_validation_case()
unused suffix leak detection
wrong fallback detection
54 tests: all pure, no model required
```

Phase 3.14 defines the protocol that Phase 3.15 will execute.

## Protocol Scope

Phase 3.14 defined:

```text
benchmark eligibility criteria
correctness gate requirements
equivalence gate requirements
runtime direction (GGUF + llama.cpp / llama-cpp-python)
model roles (drafter, verifier, target)
dataset and prompt set requirements
prompt categories (A through H)
deterministic settings
baseline definition (verifier greedy autoregressive)
strict low-tier definition (drafter + verifier accept/reject + fallback)
structural metric definitions
performance metric names (Phase 3.15 scope only)
timing field names (Phase 3.15 scope only)
trace field requirements
metadata requirements
failure mode definitions
interpretation guards
non-claims
Phase 3.15 dry run requirements
risks and open questions
```

## Benchmark Eligibility

Benchmark measurements are only eligible for reporting if ALL correctness gates pass.

Eligibility checklist per request:

```text
[ ] strict output checked against verifier greedy baseline
[ ] no unused suffix leaked into strict output
[ ] fallback tokens matched verifier greedy baseline
[ ] accepted tokens were verifier-token exact matches
[ ] no-progress errors reported explicitly
[ ] stop/EOS handling was deterministic
[ ] max_new_tokens recorded
[ ] max_cycles recorded
[ ] model/runtime/config metadata recorded
[ ] equivalent == True for this request
```

If any request is divergent (`equivalent == False`), performance metrics for that
request must not be reported.

A Phase 3.15 benchmark run is valid for performance comparison only if:

```text
divergent_request_count == 0
```

## Correctness Gate

The correctness gate requires per request:

```text
1. strict.token_ids == baseline.token_ids (token-by-token equality)
2. No unused suffix tokens appear in strict.token_ids
3. Each fallback token equals verifier greedy token at the same position
4. Each accepted prefix token equals verifier greedy token at the same position
5. no_progress_error tracked and reported
6. EOS/stop handling identical in baseline and strict paths
```

Uses `EquivalenceResult` from Phase 3.13.

## Equivalence Gate

Per-request structural check:

```text
equivalent_request_count  = number of requests where result.equivalent == True
divergent_request_count   = number of requests where result.equivalent == False
```

Equivalence rate is a structural correctness metric, not a performance metric.

Do not interpret equivalence rate as speedup or quality evidence.

## Baseline Definition

The baseline is:

```text
verifier greedy autoregressive output
model:    verifier = Gemma E2B
backend:  llama_cpp.Llama with GGUF weights
decoding: sample(temp=0.0) greedy
output:   token sequence until EOS or max_new_tokens
```

The baseline is NOT:

```text
Gemma E4B output    (future/high-tier target — NOT the Phase 3.14/3.15 baseline)
Qwen3-0.6B output   (Qwen is the drafter, not the verifier baseline)
```

## Strict Low-tier Definition

```text
1. drafter (Qwen3-0.6B, CPU) produces draft_text_chunk
2. candidate text bridge:
   candidate_verifier_token_ids = verifier.tokenize(context + candidate)[len(ctx_ids):]
3. verifier (Gemma E2B, GPU) produces verifier_greedy_token_ids via eval + sample(temp=0.0)
4. compare_candidate_to_greedy(): left-to-right token ID comparison
5. accepted_prefix = candidate_ids[:first_rejection_position]
6. one-token fallback = verifier_greedy_token_ids[first_rejection_position]
7. unused_suffix = candidate_ids[first_rejection_position+1:]  (discarded)
8. strict context update: new_context += accepted_prefix + [fallback]
9. repeat until max_new_tokens or max_cycles or EOS
```

Only verifier-safe tokens enter strict context.

Unverified drafter text must not enter strict context.

Unused suffix tokens are discarded — not rejected, not reused.

## Dataset and Prompt Set Requirements

```text
deterministic:      same prompt always produces same baseline token sequence
versioned:          prompt set has a version identifier
stored:             in repository or clearly referenced
diverse:            catches obvious failure modes
non-flattering:     not optimized to flatter the prototype's performance
size:               ≤20 prompts for Phase 3.15 dry run
private-data-free:  no private or sensitive data
```

Required prompt categories:

```text
Category A: short factual prompt
Category B: instruction-following prompt
Category C: code-like prompt
Category D: reasoning-style prompt
Category E: newline/format-sensitive prompt
Category F: Unicode or punctuation prompt
Category G: stop-sequence-sensitive prompt
Category H: fallback-heavy prompt
```

## Metrics

Structural metrics (correctness/tracing, not performance):

```text
cycle_count
accepted_target_token_count
rejected_target_token_count
unused_suffix_token_count
fallback_token_count
fallback_only_cycle_count
no_progress_error_count
full_accept_cycle_count
partial_accept_cycle_count
full_reject_cycle_count
equivalent_request_count
divergent_request_count
```

Performance metrics (Phase 3.15 only, no values in Phase 3.14):

```text
baseline_wall_time_ms
strict_low_tier_wall_time_ms
drafter_time_ms
verifier_time_ms
bridge_time_ms
comparison_time_ms
fallback_time_ms
tokens_per_second
```

Do not report measured performance values in Phase 3.14.

## Trace Requirements

Required trace fields per D-Flash cycle:

```text
request_id, prompt_id, prompt_text, prompt_category,
cycle_index, candidate_text, candidate_normalized_text,
candidate_verifier_token_ids, candidate_verifier_token_count,
verifier_greedy_token_ids, verifier_greedy_token_count,
matched_verifier_token_count, first_rejection_position,
verification_result, rejection_reason, fallback_reason,
accepted_target_token_count, rejected_target_token_count,
unused_suffix_token_count, fallback_token_id,
context_update_source, strict_output_token_ids,
baseline_output_token_ids, equivalent,
divergence_position, divergence_reason, stop_reason,
max_new_tokens, max_cycles, deterministic_settings,
backend_capability_status, comparison_profile
```

Trace fields must not include: `acceptance_rate`, `speedup`, `lossless`,
`target_equivalent`, `correctness_validated`.

## Metadata Requirements

Required per benchmark run:

```text
git_commit_hash, phase_number, benchmark_protocol_version,
prompt_set_version, model_role_drafter, model_role_verifier,
drafter_model_path, verifier_model_path,
drafter_gguf_filename, verifier_gguf_filename,
llama_cpp_python_version, llama_cpp_build_info,
python_version, os_platform, cuda_available, gpu_name,
config_file_path, deterministic_settings,
max_new_tokens, max_cycles, draft_block_size, timestamp_utc
```

## Phase 3.15 Dry Run Requirements

```text
1. All requests must pass correctness gate (equivalent == True).
   If any fail: report divergence details, do NOT aggregate performance metrics.

2. Use Phase 3.14 prompt set (≤20 prompts, all required categories).

3. Record complete metadata per this protocol.

4. Record complete cycle-level trace per this protocol.

5. Report structural metrics separately from performance metrics.

6. Do NOT report speedup unless all correctness gates pass.

7. Include Phase 3.13 fake harness results as prior baseline reference.

8. The report is the Low-Tier D-Flash MVP closure report.

9. Phase 3.15 does NOT implement high-tier.

10. Phase 3.15 does NOT implement Gemma E4B benchmark.
```

## Tests

New test file:

```text
tests/test_phase_3_14_low_tier_benchmark_protocol.py
```

Tests added:

```text
- spec file exists
- report file exists
- all 29 required spec sections present
- all 24 required report sections present
- roadmap correct (3.14, 3.15, 4.0+; no 3.16/3.17)
- Phase 3.15 is closure milestone
- correctness gate defined
- measurements invalid without gate
- equivalence gate defined
- baseline as verifier greedy autoregressive
- E4B excluded as baseline
- strict low-tier path defined
- unused suffix discarded
- correct design principle stated
- GGUF + llama.cpp required
- vLLM appears only in exclusion context
- 7 structural metrics defined
- 3 performance metric names defined
- 19 trace fields defined
- 10 metadata fields defined
- interpretation guards present
- fallback count not quality
- unused suffix not rejected
- measurements invalid without gate
- non-claims section present
- no speedup claim
- no benchmark result claim
- no high-tier claim
- no EAGLE claim
- Phase 3.15 as next step
- 17 forbidden positive claims absent from spec
- 17 forbidden positive claims absent from report
- commit field says "not committed by agent"
- 8 prompt categories defined
- canonical model role names used
- no qwen_*/gemma_* forbidden fields
```

All tests require no GGUF model, no GPU, no disk access beyond spec/report files.

## Verification

```text
focused tests (Phase 3.14):
    test_phase_3_14_low_tier_benchmark_protocol.py : all passed

prior phase tests:
    test_phase_3_13_equivalence_harness.py  : 27 passed
    test_phase_3_13_fake_validation.py      : 27 passed
    test_phase_3_12_strict_accept_reject.py : 33 passed
    test_phase_3_12_token_bridge.py         : 20 passed
    test_phase_3_12_backend_capabilities.py : 18 passed, 1 skipped
    test_phase_3_11_token_level_verifier_design.py : 23 passed
    test_phase_3_10_dflash_correctness_spec.py     : 5 passed

full suite:
    (see Verification run results)
    1 pre-existing failure: test_prompt_sets.py::test_prompt_registry_reports_available_ids
    Not introduced by Phase 3.14.

forbidden-claim scan: clean
git diff --check: exit=0
```

## Remaining Limitations

Phase 3.14 did not implement:

```text
Benchmark runner
    - No implementation of benchmark execution code
    - No throughput measurement

LlamaCppBackend extension
    - tokenize, eval, sample not yet exposed by wrapper
    - Required for Phase 3.15 real model runs

Real model equivalence validation
    - All Phase 3.13 harness tests used fake token IDs
    - Real model runs first happen in Phase 3.15

Text-level equivalence (Mode B)
    - Token ID equality sufficient for Phase 3.14 protocol definition
    - Text-level comparison deferred

High-tier / EAGLE-style speculation
    - Phase 4.0+ scope

Gemma E4B benchmark
    - Not the low-tier baseline; future/high-tier only

No vLLM integration
    - Not planned; GGUF + llama.cpp is the current backend
```

## Interpretation Guards

Benchmark measurements are invalid if the correctness gate fails.

`bridge_valid_block_count` is a bridge-level structural diagnostic count.

It is not accepted block count.

It is not accepted token count.

It is not acceptance-rate evidence.

It is not target-equivalence evidence.

`cycle_fallback_count` is a per-cycle fallback count.

It is not correctness evidence.

It is not performance evidence.

It is not benchmark evidence.

It is not a quality score.

`draft_block_size = 8` means drafter-side draft max tokens.

It is not 8 accepted Gemma target tokens.

It is not the acceptance denominator.

`rejected_target_token_count` is exactly 1 per rejection event.

It does not include the unused suffix token count.

`unused_suffix_token_count` is count of discarded candidate tokens.

It is not a rejected token count.

It is not an acceptance metric.

`tokens_per_second` without an equivalence gate is not a valid performance metric.

## Non-Claims

No benchmark result is contained in this document.

No speedup claim is made.

No performance-improvement claim is made.

No throughput measurement is made.

No low-tier-is-faster claim is made.

No production lossless-generation claim is made.

No target Gemma E4B equivalence claim is made.

No high-tier implementation claim is made.

No EAGLE-style speculation is described here as implemented.

No vLLM integration is described here as implemented.

No correctness validation is claimed for real model outputs.

No statistically significant performance result is reported.

Equivalence under Phase 3.13 fake conditions does not imply production correctness.

## Error Reports

No errors encountered. Spec, report, and tests written without failures.

## Commit

Not committed by agent. Commit/merge handled manually by project owner.

Suggested commit message:

```text
docs: define low-tier benchmark protocol
```

## Next Step

```text
Phase 3.15: Low-tier benchmark dry run + Low-Tier D-Flash MVP closure report
```

Phase 3.15 must:

```text
1. Extend LlamaCppBackend with thin VerifierTokenAccess layer
2. Execute the benchmark protocol defined in Phase 3.14
3. Report structural metrics for all prompts
4. Check correctness gate per request
5. Report performance metrics only if correctness gate passes for all requests
6. Produce the Low-Tier D-Flash MVP closure report
7. Close the low-tier D-Flash work
8. NOT start high-tier work
```
