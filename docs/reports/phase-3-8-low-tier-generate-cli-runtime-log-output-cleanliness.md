# Phase 3.8 Low-Tier Generate CLI Runtime Log / Output Cleanliness

## Summary

Phase 3.8 hardens runtime log and output-channel behavior for the user-facing low-tier block-cycle generation pipeline.

This phase keeps the current runtime direction:

```text
GGUF + llama.cpp / llama-cpp-python
```

It does not change the generation algorithm, prompt sets, device policy, or diagnostic semantics.

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

Phase 3.8 and Phase 3.9 remain engineering-pipeline phases.

D-Flash correctness work begins at Phase 3.10 with specification, not with a correctness claim.

Phase 3.8 is runtime log/output cleanliness only.

## Motivation

Phase 3.7 made the generate CLI more usable, but live runs showed native runtime messages could still appear before the user-facing payload.

The desired output-channel policy is:

```text
CLI payload -> stdout
runtime logs/warnings -> stderr
user-facing errors -> stderr
JSON payload -> stdout only when feasible
```

The goal is cleaner parsing and demo behavior. This phase does not hide real runtime failures.

## Runtime Log Source

The primary noise source is llama-cpp-python / llama.cpp during model initialization and generation.

Phase 3.8 now passes:

```text
verbose=False
```

to the llama-cpp-python model constructor by default.

When `--verbose` is used without `--json`, the backend is allowed to pass:

```text
verbose=True
```

Live checks showed that default and quiet modes still preserve short native context/cache warnings, but those warnings are routed to stderr when stdout/stderr are separated by the shell.

The stricter JSON redirection check confirmed:

```text
stdout: valid JSON payload
stderr: native runtime messages
```

## Output Channel Policy

Phase 3.8 updates the generate CLI policy:

```text
default text payload: stdout
quiet text payload: stdout
JSON payload: stdout
validation errors: stderr
runtime stdout during model work: routed to stderr unless verbose text mode is requested
```

JSON mode always routes runtime stdout away from stdout, including when `--verbose` is also present.

## CLI Behavior

Default text mode keeps:

```text
RESPONSE:
<response_text>

METRICS:
trace_type: low_tier_cycle_generate
prompt_mode: instruction
draft_block_size: 8
max_cycles: 4
total_cycles: ...
bridge_valid_block_count: ...
bridge_rejected_block_count: ...
cycle_fallback_count: ...
total_wall_time_seconds: ...
drafter_latency_seconds_total: ...
verifier_latency_seconds_total: ...
bridge_latency_seconds_total: ...
response_chars: ...
response_cleanup_applied: true/false

INTERPRETATION GUARDS:
bridge_valid_block_count: structural bridge metadata only
cycle_fallback_count: fallback event metadata only
```

User-facing validation errors now print to stderr and return a nonzero exit code.

## JSON Mode Behavior

JSON mode prints only the result payload to stdout in normal operation.

The JSON payload includes:

```text
prompt
effective_prompt
prompt_mode
response_text
metrics
interpretation_guards
non_claims
trace_path
```

The live redirection check used:

```bash
.venv/bin/python scripts/generate_low_tier.py \
  --prompt "Explain caching in one sentence." \
  --draft-block-size 8 \
  --max-cycles 4 \
  --json > /tmp/htfsd_stdout.json 2> /tmp/htfsd_stderr.log

.venv/bin/python -m json.tool /tmp/htfsd_stdout.json
```

The JSON parse check passed.

## Quiet and Verbose Modes

Quiet mode now prints only:

```text
RESPONSE:
<response_text>
```

Verbose text mode allows detailed native runtime output and still prints the final `RESPONSE`, `METRICS`, and interpretation guard sections.

If `--json` and `--verbose` are combined, JSON stdout cleanliness takes priority.

## Implementation Changes

Phase 3.8 changed:

```text
src/htfsd/runtime/llama_cpp_backend.py
src/htfsd/cli/generate_low_tier.py
tests/test_generate_low_tier.py
tests/test_llama_cpp_backend.py
```

Key changes:

```text
LlamaCppBackend accepts a verbose flag and defaults it to false.
Generate CLI routes runtime stdout to stderr for default, quiet, and JSON modes.
Generate CLI prints validation errors to stderr.
Quiet mode suppresses nonessential metrics.
Default text output includes compact interpretation guards.
Fake runtime-log tests verify JSON stdout remains parseable.
```

## Verification

Focused tests:

```text
.venv/bin/pytest tests/test_generate_low_tier.py tests/test_llama_cpp_backend.py -v
21 passed
```

Live default text CLI:

```text
exit_code: 0
payload: RESPONSE, METRICS, INTERPRETATION GUARDS
```

Live quiet CLI:

```text
exit_code: 0
payload: RESPONSE only
```

Live verbose CLI:

```text
exit_code: 0
payload: native runtime detail plus final RESPONSE and METRICS
```

Live JSON redirection:

```text
stdout JSON parse: passed
stderr received native runtime messages
```

Final completion verification:

```text
full suite: 204 passed
forbidden-claim scan: clean
git diff --check: clean
```

## Remaining Limitations

Native llama.cpp warnings can still appear in the terminal because they are meaningful runtime messages.

The Phase 3.8 guarantee is narrower:

```text
JSON stdout is parseable when stdout/stderr are separated.
Runtime messages are kept off JSON stdout in normal operation.
Verbose text mode may intentionally show runtime detail.
```

Shells or hosting tools that merge stdout and stderr may still display runtime messages before the payload.

## Interpretation Guards

`bridge_valid_block_count` is structural bridge metadata only.

It is not accepted block count.

It is not accepted token count.

It is not acceptance-rate evidence.

It is not target-equivalence evidence.

`cycle_fallback_count` is fallback event metadata only.

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

The correct name is `low-tier block-cycle generation pipeline`.

This is not a D-Flash/speculative decoding correctness pipeline.

## Conclusion

Phase 3.8 improves output cleanliness for the low-tier generate CLI without expanding the research scope. JSON mode is now parseable through stdout separation, validation errors move to stderr, quiet mode is compact, and verbose mode remains available for runtime inspection.

## Next Step

Recommended next phase:

```text
Phase 3.9: Low-Tier Generation Pipeline Closure
```
