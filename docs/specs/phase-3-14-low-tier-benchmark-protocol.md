# Phase 3.14 Low-tier Benchmark Protocol

## Summary

This document defines the benchmark protocol for Phase 3.15 low-tier D-Flash dry run.

This document does not contain benchmark results.

This document does not contain speedup measurements.

This document does not contain performance claims.

Phase 3.14 scope is protocol definition only.

Benchmark execution begins in Phase 3.15.

Design principle:

```text
Gemma verifies candidate Gemma tokens derived from Qwen draft text.
```

## Current Roadmap

```text
Phase 3.8  = Runtime log/output cleanliness
Phase 3.9  = Low-tier generation pipeline closure
Phase 3.10 = D-Flash correctness specification
Phase 3.11 = Token-level verifier design
Phase 3.12 = Strict acceptance/rejection prototype
Phase 3.13 = Correctness/equivalence validation harness
Phase 3.14 = Low-tier benchmark protocol/spec                ← CURRENT PHASE
Phase 3.15 = Low-tier benchmark dry run + Low-Tier D-Flash MVP closure report
Phase 4.0+ = High-tier preparation / feature-level speculative decoding
```

Low-tier closure terminates at Phase 3.15.

Low-tier closure terminates at Phase 3.15. Do not extend beyond that milestone.

## Prior Phases

```text
Phase 3.12: Strict acceptance/rejection prototype
    - compare_candidate_to_greedy() — pure strict token comparison
    - VerificationDecision — frozen dataclass
    - full accept / partial accept / full reject
    - first rejection position
    - unused suffix accounting (unused ≠ rejected)
    - one-token fallback semantics
    - LlamaCppCapabilityStatus — static backend API classification

Phase 3.13: Correctness/equivalence validation harness
    - EquivalenceResult / DivergenceReport / BaselineRunResult / StrictRunResult
    - compare_outputs() — pure equivalence comparison
    - run_fake_baseline() / run_fake_strict() / run_validation_case()
    - unused suffix leak detection
    - wrong fallback detection
    - all tests: no model required
```

Phase 3.14 defines the benchmark protocol for Phase 3.15 to execute.

## Scope

Phase 3.14 defines:

```text
benchmark eligibility criteria
correctness gate requirements
equivalence gate requirements
runtime direction
model roles and canonical names
dataset and prompt set requirements
prompt categories
deterministic settings
baseline definition
strict low-tier definition
structural metric definitions
performance metric names (Phase 3.15 only)
timing field names (Phase 3.15 only)
trace field requirements
metadata requirements
failure mode definitions
interpretation guards
non-claims
Phase 3.15 dry run requirements
risks and open questions
```

## Non-Scope

Phase 3.14 does not:

```text
run benchmark experiments
implement the benchmark runner
measure throughput
measure speedup
compare performance against baseline
implement GPU memory optimization
implement high-tier benchmark
implement Gemma E4B benchmark
implement EAGLE benchmark
Do not implement vLLM benchmark
implement hidden-state benchmark
report measured performance values
```

## Benchmark Eligibility

Benchmark measurements are only eligible for reporting if ALL correctness gates pass.

If any correctness gate fails, benchmark performance results are invalid and must not be reported.

Eligibility checklist for each benchmark request:

```text
[ ] strict output was checked against verifier greedy baseline
[ ] no unused suffix leaked into strict output
[ ] fallback tokens matched verifier greedy baseline
[ ] accepted tokens were verifier-token exact matches
[ ] no-progress errors were reported explicitly
[ ] stop/EOS handling was deterministic
[ ] max_new_tokens was recorded
[ ] max_cycles was recorded
[ ] model/runtime/config metadata was recorded
[ ] equivalent field is True for this request
```

A request where `equivalent == False` must not contribute to performance metrics.

## Correctness Gate

The correctness gate requires:

```text
1. For each benchmark request:
   compare strict low-tier output token sequence against verifier greedy baseline.
   strict.token_ids must equal baseline.token_ids.

2. No unused suffix tokens may appear in strict.token_ids.

3. Each fallback token must equal the verifier greedy token at the same position.

4. Each accepted prefix token must equal the verifier greedy token at the same position.

5. no_progress_error must be tracked and reported.

6. EOS/stop handling must be identical in baseline and strict paths.
```

The correctness gate uses the `EquivalenceResult` from Phase 3.13.

A request is correctness-gated if `result.equivalent == True`.

## Equivalence Gate

The equivalence gate is a per-request structural check.

```text
equivalent_request_count  = number of requests where result.equivalent == True
divergent_request_count   = number of requests where result.equivalent == False
```

Equivalence rate is a structural correctness metric, not a performance metric.

Do not interpret equivalence rate as speedup or quality evidence.

A benchmark run is only valid for performance reporting if:

```text
divergent_request_count == 0
```

If any request is divergent, performance metrics must not be reported for that request.

## Runtime Direction

All benchmark measurements must use the GGUF + llama.cpp / llama-cpp-python backend.

```text
backend:          GGUF + llama.cpp / llama-cpp-python
version:          0.3.23 (confirmed)
tokenizer:        llama_cpp.Llama.tokenize()
greedy approach:  llama_cpp.Llama.sample(temp=0.0)
eval:             llama_cpp.Llama.eval()
```

Do not use vLLM.

Do not use Transformers HuggingFace runtime.

Do not use ONNX.

Do not use TensorRT.

Backend capability status is defined in `src/htfsd/runtime/llama_cpp_capabilities.py`.

## Model Roles

Canonical model roles for Phase 3.14 and Phase 3.15:

```text
drafter   = Qwen3-0.6B,  runs on CPU
verifier  = Gemma E2B,   runs on CUDA/GPU
target    = Gemma E4B,   NOT active in Phase 3.14 or 3.15
```

Deprecated aliases (compatibility only):

```text
qwen_drafter -> drafter
gemma_e2b    -> verifier
gemma_e4b    -> target
```

Do not use `qwen_*` or `gemma_*` in new fields, docs, reports, traces, or schemas.

The Phase 3.14 and Phase 3.15 benchmark baseline is:

```text
verifier = Gemma E2B
```

Do not use Gemma E4B as the low-tier benchmark baseline.

Gemma E4B is future/high-tier target.

## Dataset and Prompt Set Requirements

Prompt sets for Phase 3.15 must satisfy:

```text
deterministic:      same prompt must always produce the same baseline token sequence
versioned:          prompt set has a version identifier
stored:             stored in repository or clearly referenced (not external internet)
diverse:            diverse enough to catch obvious failure modes
non-flattering:     not optimized to improve the prototype's apparent performance
size:               small enough for Phase 3.15 dry run (target: ≤20 prompts)
private-data-free:  no private or sensitive data
```

## Prompt Categories

Phase 3.15 prompt set must include at least one prompt from each category:

```text
Category A: short factual prompt
    Example: "What is the capital of France?"

Category B: instruction-following prompt
    Example: "Write a one-sentence summary of photosynthesis."

Category C: code-like prompt
    Example: "Write a Python function that returns the nth Fibonacci number."

Category D: reasoning-style prompt
    Example: "If all roses are flowers and some flowers fade quickly,
              can we conclude some roses fade quickly?"

Category E: newline/format-sensitive prompt
    A prompt where response formatting matters (numbered list, bullet points).

Category F: Unicode or punctuation prompt
    A prompt containing non-ASCII characters or unusual punctuation.

Category G: stop-sequence-sensitive prompt
    A prompt where EOS or a stop sequence terminates output early.

Category H: fallback-heavy prompt
    A prompt designed to cause frequent mismatch between drafter and verifier,
    triggering repeated fallback cycles.
    Purpose: verify fallback semantics, not to flatter speedup numbers.
```

## Deterministic Settings

All benchmark runs must use identical deterministic settings for both baseline and
strict low-tier paths:

```text
temperature:     0.0
decoding:        greedy
seed:            fixed (same value for baseline and strict)
top_k:           1 (or equivalent)
top_p:           1.0 (or equivalent)
prompt_mode:     same for both paths (instruct/chat/raw)
stop_handling:   same stop token list
max_new_tokens:  same value for both paths
max_cycles:      specified for strict path
normalization:   same comparison_profile
tokenizer:       same tokenizer version and settings
```

Settings must be recorded in benchmark metadata.

## Baseline Definition

The baseline is defined as:

```text
verifier greedy autoregressive output
```

Specifically:

```text
model:        verifier = Gemma E2B
backend:      llama_cpp.Llama with GGUF weights
decoding:     sample(temp=0.0) greedy
context:      same prompt as strict path
output:       token sequence until EOS or max_new_tokens
stop reason:  recorded
```

The baseline is the reference output.

A benchmark measurement compares strict low-tier output against this baseline.

Equivalence is defined as:

```text
strict.token_ids == baseline.token_ids
```

The baseline is NOT:

```text
Gemma E4B output (Gemma E4B is future/high-tier target)
Qwen3-0.6B output (Qwen is the drafter, not the verifier baseline)
GPT-4 output
Human-labeled output
```

## Strict Low-tier Definition

Strict low-tier output is produced by:

```text
1. drafter (Qwen3-0.6B, CPU) produces draft_text_chunk
2. candidate text bridge:
   candidate_verifier_token_ids = verifier.tokenize(context + candidate_text)[len(context_ids):]
3. verifier (Gemma E2B, GPU) produces verifier_greedy_token_ids via eval + sample(temp=0.0)
4. compare_candidate_to_greedy():
   left-to-right token ID comparison
   first mismatch position = rejection point
5. accepted_prefix = candidate_ids[:first_rejection_position]
6. one-token fallback = verifier_greedy_token_ids[first_rejection_position]
7. unused_suffix = candidate_ids[first_rejection_position+1:]  (discarded)
8. strict context update:
   new_context = old_context + accepted_prefix + [fallback_token]
   (fallback_only if no accepted_prefix)
9. repeat until max_new_tokens or max_cycles or EOS
```

Only verifier-safe tokens enter strict context.

Unverified drafter text must not enter strict context.

Rejected candidate token is exactly one token at first mismatch.

Unused suffix tokens are discarded — not rejected, not reused.

## Measurement Plan

Phase 3.15 must measure two paths for each prompt:

```text
Path A: verifier baseline
    - prompt -> Gemma E2B greedy autoregressive
    - record baseline_wall_time_ms
    - record baseline_token_ids
    - record stop_reason

Path B: strict low-tier D-Flash
    - prompt -> Qwen3-0.6B drafter + Gemma E2B verifier (strict accept/reject)
    - record strict_low_tier_wall_time_ms
    - record strict.token_ids
    - record stop_reason
    - record cycle-level trace

Comparison:
    - run EquivalenceResult.compare_outputs(baseline, strict)
    - record equivalent (True/False)
    - if divergent, record divergence_position and divergence_reason
```

Do not report relative performance if `equivalent == False`.

## Structural Metrics

Structural metrics describe the algorithm's behavior per request.

These are correctness/tracing metrics, not performance metrics.

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

Do not use:

```text
acceptance_rate       — misleading without context
speedup               — not a structural metric
bridge_valid_blocks   — not accepted token count
fallback_count        — not quality evidence
```

## Performance Metrics

Performance metrics for Phase 3.15 only.

Do not report measured values in Phase 3.14.

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

Wall-time measurements must include model load time separately if measured during startup.

## Timing Fields

Per-request timing fields (Phase 3.15 scope):

```text
request_wall_time_ms:       total wall time for the request
baseline_wall_time_ms:      baseline path wall time
strict_low_tier_wall_time_ms: strict path wall time
drafter_wall_time_ms:       drafter inference wall time
verifier_wall_time_ms:      verifier inference wall time
bridge_wall_time_ms:        tokenization + suffix derivation wall time
comparison_wall_time_ms:    accept/reject comparison wall time
```

Timing measurements must use monotonic wall clock (e.g. `time.perf_counter()`).

Timing must not be used to claim speedup unless:

```text
1. equivalent_request_count == total_request_count (all requests passed correctness gate)
2. warmup runs are excluded from measurements
3. multiple samples are taken
4. system load and thermal state are documented
```

## Trace Requirements

Required trace fields for each D-Flash cycle in Phase 3.15:

```text
request_id
prompt_id
prompt_text
prompt_category
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
strict_output_token_ids
baseline_output_token_ids
equivalent
divergence_position
divergence_reason
stop_reason
max_new_tokens
max_cycles
deterministic_settings
backend_capability_status
comparison_profile
```

Trace fields must not include:

```text
acceptance_rate
speedup
lossless
target_equivalent
correctness_validated
```

## Metadata Requirements

Each Phase 3.15 benchmark run must record:

```text
git_commit_hash
phase_number:                "3.15"
benchmark_protocol_version:  "3.14"
prompt_set_version
model_role_drafter:          "Qwen3-0.6B"
model_role_verifier:         "Gemma E2B"
model_role_target:           "Gemma E4B (not active)"
drafter_model_path
verifier_model_path
drafter_gguf_filename
verifier_gguf_filename
llama_cpp_python_version:    "0.3.23"
llama_cpp_build_info
python_version
os_platform
cuda_available
gpu_name
config_file_path
deterministic_settings
max_new_tokens
max_cycles
draft_block_size
timestamp_utc
```

## Failure Modes

Phase 3.15 must handle and record these failure modes:

```text
boundary_mismatch:
    tokenization boundary unstable when context + candidate is tokenized
    action: record bridge_status = "boundary_mismatch", cycle is skipped

no_progress_error:
    no candidate tokens AND no greedy fallback available
    action: record stop_reason = "no_progress_error", terminate request

eos_in_candidate:
    EOS token appears in accepted prefix
    action: commit prefix up to and including EOS, terminate

eos_in_fallback:
    EOS token is the fallback token
    action: commit fallback token, terminate

max_new_tokens_reached:
    committed token count reaches max_new_tokens
    action: terminate, record stop_reason = "max_tokens"

max_cycles_reached:
    cycle count reaches max_cycles
    action: terminate, record stop_reason = "max_cycles"

drafter_failure:
    drafter produces empty or invalid draft text
    action: record error, produce fallback or terminate

verifier_tokenizer_failure:
    verifier tokenizer raises exception
    action: record bridge_status = "tokenizer_error", fallback or terminate

divergent_output:
    strict.token_ids != baseline.token_ids
    action: record equivalent = False, divergence_position, divergence_reason
    DO NOT report performance metrics for this request
```

## Interpretation Guards

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

`unused_suffix_token_count` is the count of candidate tokens discarded after first mismatch.

It is not a rejected token count.

It is not an acceptance metric.

`tokens_per_second` without an equivalence gate is not a valid performance metric.

Benchmark measurements are invalid if the correctness gate fails.

## Non-Claims

This protocol does not contain benchmark results.

This protocol does not contain speedup measurements.

This protocol does not contain performance comparisons.

No speedup claim is made.

No performance-improvement claim is made.

No throughput measurement is made.

No low-tier-is-faster claim is made.

No production lossless-generation claim is made.

No target Gemma E4B equivalence claim is made.

No high-tier implementation claim is made.

No EAGLE-style speculation is described here as implemented.

No vLLM integration is described here as implemented.

Equivalence under Phase 3.13 fake conditions does not imply production correctness.

## Phase 3.15 Dry Run Requirements

Phase 3.15 must satisfy:

```text
1. All benchmark requests pass correctness gate (equivalent == True).
   If any fail, report divergence details and do not aggregate performance metrics.

2. Use the Phase 3.14 prompt set (≤20 prompts, all required categories present).

3. Record complete metadata per this protocol.

4. Record complete cycle-level trace per this protocol.

5. Report structural metrics separately from performance metrics.

6. Do not report speedup unless all correctness gates pass.

7. Include the Phase 3.13 fake harness validation results as a prior baseline.

8. The report is the Low-Tier D-Flash MVP closure report.

9. Phase 3.15 does not implement high-tier.

10. Phase 3.15 does not implement Gemma E4B benchmark.
```

## Risks and Open Questions

```text
1. Wrapper extension for LlamaCppBackend
   LlamaCppBackend does not yet expose tokenize, eval, sample at the wrapper level.
   Phase 3.15 must either extend the wrapper or use the raw Llama instance directly.
   Risk: extension may break existing interfaces.

2. Tokenization boundary sensitivity
   derive_candidate_suffix() depends on stable context+candidate tokenization.
   Real SentencePiece/BPE models may produce boundary mismatches not caught in fake tests.
   Risk: boundary_mismatch events may be frequent in real model runs.

3. Fallback-only cycles
   If the drafter consistently mismatches the verifier, all cycles will be fallback-only.
   This is equivalent to pure verifier autoregressive generation — no speedup.
   Risk: repeated fallback-only cycles reduce any potential speedup benefit.
   Do not present fallback-only results as D-Flash speedup.

4. KV cache management
   eval() + sample() on one token at a time may reset or corrupt KV cache.
   Phase 3.15 must test that context accumulates correctly across cycles.
   Risk: KV cache not preserved correctly between cycles.

5. EOS / stop sequence handling
   Drafter and verifier may handle EOS differently.
   Phase 3.15 must ensure EOS in accepted prefix terminates correctly.
   Risk: drafter text may contain verifier EOS token at non-EOS positions.

6. Temperature/greedy consistency
   sample(temp=0.0) behavior may differ from argmax(logits) in edge cases.
   Phase 3.15 must verify that baseline and strict use identical greedy behavior.

7. No equivalence validation for real model outputs yet
   Phase 3.13 harness used fake token IDs.
   Phase 3.15 will be the first run with real model token IDs.
   Initial divergence count may be nonzero.
   Risk: real model runs may reveal correctness bugs not caught in Phase 3.12–3.13.
```

## Conclusion

Phase 3.14 defines the benchmark protocol for Phase 3.15.

This protocol establishes:

```text
correctness gate:     required before any performance measurement
equivalence gate:     per-request, required for valid performance reporting
baseline:             verifier greedy autoregressive output (Gemma E2B)
strict path:          drafter + verifier accept/reject + fallback (Gemma E2B)
metrics:              structural metrics + performance metrics (Phase 3.15 only)
trace:                required per-cycle fields
metadata:             required per-run fields
```

No benchmark results are in this document.

No speedup claims are in this document.

## Next Step

```text
Phase 3.15: Low-tier benchmark dry run + Low-Tier D-Flash MVP closure report
```

Phase 3.15 must:

```text
1. Execute the benchmark protocol defined in Phase 3.14
2. Report structural metrics for all prompts
3. Check correctness gate per request
4. Report performance metrics only if correctness gate passes for all requests
5. Produce the Low-Tier D-Flash MVP closure report
6. Close the low-tier D-Flash work
7. NOT start high-tier work
```
