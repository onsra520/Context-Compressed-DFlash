# Phase 3.9 Low-Tier Generation Pipeline Closure

## Summary

Phase 3.9 closes the current low-tier block-cycle generation pipeline as an engineering milestone.

The milestone name is:

```text
Low-Tier Block-Cycle Generation Pipeline v0.2
```

This closure means the prompt-in / response-out engineering path is stable enough to hand off into the next specification phase. It does not close D-Flash correctness.

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

Phase 3.9 remains an engineering-pipeline phase.

D-Flash correctness work begins at Phase 3.10 with specification.

Benchmark work begins only after correctness/equivalence validation.

High-tier preparation remains Phase 4.0+ work.

## Milestone

`Low-Tier Block-Cycle Generation Pipeline v0.2` is the closed engineering milestone for the current low-tier generation path.

Phase 3.9 closes the low-tier block-cycle generation pipeline as an engineering milestone.

Phase 3.9 does not close D-Flash correctness.

D-Flash correctness work begins at Phase 3.10 with specification.

## Closure Scope

This closure covers:

```text
prompt input
effective prompt recording
raw/instruction/chat prompt modes
default instruction mode
block-cycle loop control
drafter block generation
text bridge validation/rejection
verifier continuation/fallback behavior
context update across cycles
response assembly
conservative response cleanup
text CLI output
JSON CLI output
quiet/verbose behavior
runtime log/output separation
optional trace writing
descriptive metrics
interpretation guards
non-claims
```

This closure does not add token-level correctness semantics.

## Pipeline Contract

The pipeline contract is:

```text
user prompt
  -> prompt policy creates effective_prompt
  -> drafter receives current context
  -> drafter emits draft_text_chunk
  -> text bridge normalizes and validates the draft text chunk
  -> verifier receives current context plus normalized draft text when bridge-valid
  -> verifier receives current context alone on fallback
  -> response chunk is appended
  -> current context is updated
  -> cycle repeats until max_cycles or max_total_chars
  -> final response_text is assembled and conservatively cleaned
```

The pipeline is deterministic enough for fake-backend engineering tests. Live model text can still vary with runtime/model behavior and is not interpreted as correctness evidence.

## Prompt Modes

The stable prompt modes are:

```text
raw
instruction
chat
```

Default user-facing mode:

```text
instruction
```

Instruction mode applies:

```text
You are a concise assistant. Follow the user request directly.
User: {prompt}
Assistant:
```

Raw mode remains available for diagnostics.

Chat mode remains available when the backend supports chat completion.

The result records:

```text
prompt
effective_prompt
prompt_mode
```

Blank prompt validation returns a clear user-facing error through stderr.

## Block-Cycle Generation

Each cycle records:

```text
cycle_id
draft_block_size
draft_text_summary
verifier_text_summary
bridge_status
rejection_reason
cycle_fallback_count
drafter_latency_seconds
verifier_latency_seconds
bridge_latency_seconds
context_length_before
context_length_after
response_chars_after
```

Raw chunk fields remain opt-in through `--capture-raw-output`.

The configured `max_cycles` controls the upper bound for the loop.

The configured `max_total_chars` can stop response assembly early.

## Bridge and Fallback Semantics

The bridge is a text-level structural diagnostic bridge.

When the bridge status is valid:

```text
verifier_prompt = current_context + normalized_draft_text
cycle_fallback_count = 0
```

When the bridge status is rejected:

```text
verifier_prompt = current_context
cycle_fallback_count = 1
```

Rejection/fallback behavior is engineering behavior in this phase. It does not imply token-level target verification.

## Response Assembly

Response assembly is intentionally simple:

```text
valid bridge cycle: normalized draft text + verifier text
rejected bridge cycle: verifier fallback text
all cycles: append response chunk to response_parts
final: join response_parts
```

Response cleanup is conservative:

```text
strip leading/trailing whitespace
normalize CRLF/CR to LF
collapse excessive blank lines
remove exact prompt/effective-prompt prefix echo
```

No semantic rewriting is introduced.

The result records:

```text
response_text
metrics.response_cleanup_applied
```

## CLI Behavior

Default text mode prints:

```text
RESPONSE:
<response_text>

METRICS:
trace_type: low_tier_cycle_generate
prompt_mode: instruction
draft_block_size: ...
max_cycles: ...
total_cycles: ...
bridge_valid_block_count: ...
bridge_rejected_block_count: ...
cycle_fallback_count: ...
total_wall_time_seconds: ...
drafter_latency_seconds_total: ...
verifier_latency_seconds_total: ...
bridge_latency_seconds_total: ...
output_chars: ...
response_chars: ...
response_cleanup_applied: true/false

INTERPRETATION GUARDS:
bridge_valid_block_count: structural bridge metadata only
cycle_fallback_count: fallback event metadata only
```

Quiet mode prints only:

```text
RESPONSE:
<response_text>
```

Verbose text mode allows backend/runtime detail and still prints the final response and metrics payload.

Validation errors go to stderr and return a nonzero exit code.

## JSON Behavior

JSON mode emits the result payload to stdout.

JSON includes:

```text
prompt
effective_prompt
prompt_mode
response_text
trace_type
draft_block_size
max_cycles
total_cycles
bridge_valid_block_count
bridge_rejected_block_count
cycle_fallback_count
cycles
metrics
interpretation_guards
non_claims
trace_path when present
```

When stdout and stderr are separated, runtime logs do not corrupt JSON stdout in normal operation.

## Trace and Metrics

Optional trace writing is available through:

```text
--write-trace
```

Trace artifacts are written under ignored local logs by default:

```text
logs/reports/<timestamp>-low-tier-generate-trace.json
```

Metrics are descriptive:

```text
total_wall_time_seconds
drafter_latency_seconds_total
verifier_latency_seconds_total
bridge_latency_seconds_total
output_chars
response_chars
response_cleanup_applied
draft_text_chunk_count
verifier_text_chunk_count
tokens_per_second_descriptive
latency_seconds_descriptive
```

These fields are not benchmark conclusions.

## Runtime Log / Output Cleanliness

Phase 3.8 established the output policy used by the closed v0.2 pipeline:

```text
CLI payload -> stdout
runtime logs/warnings -> stderr where safely routable
user-facing errors -> stderr
JSON payload -> stdout
```

`LlamaCppBackend` defaults to `verbose=False`.

`--verbose` allows backend verbosity for text-mode inspection.

If `--json` and `--verbose` are combined, JSON stdout cleanliness takes priority.

Native llama.cpp warnings may still appear in tools that merge stdout and stderr.

## Implementation Changes

Phase 3.9 adds the closure report and closure-oriented tests.

No generation algorithm rewrite is introduced.

No correctness semantics are introduced.

## Verification

Closure test red step:

```text
phase 3.9 closure report test failed while report was absent
```

Focused and full verification are part of the final completion gate:

```text
focused generate tests: 17 passed
generate + backend tests: 22 passed
full suite: 205 passed
live text CLI: exit 0
live quiet CLI: exit 0
live verbose CLI: exit 0
live JSON CLI: exit 0
JSON stdout parse check: passed
forbidden-claim scan: clean
git diff --check: clean
```

## Remaining Limitations

The v0.2 pipeline is an engineering/control-flow milestone only.

Remaining limitations:

```text
no D-Flash correctness specification yet
no token-level verifier
no strict accept/reject semantics
no target equivalence validation
no output parity validation
no benchmark protocol
no benchmark runner
no speed comparison
no high-tier path
native runtime warnings may still appear when stdout/stderr are merged
live response quality is not guaranteed by this closure
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

The correct name is `low-tier block-cycle generation pipeline`.

This is not a D-Flash/speculative decoding correctness pipeline.

## Conclusion

Phase 3.9 closes `Low-Tier Block-Cycle Generation Pipeline v0.2` as a stable engineering milestone. The project now has a documented, tested prompt-in / response-out low-tier block-cycle generation path ready for Phase 3.10 correctness specification.

## Next Step

Recommended next phase:

```text
Phase 3.10: D-Flash Correctness Specification
```
