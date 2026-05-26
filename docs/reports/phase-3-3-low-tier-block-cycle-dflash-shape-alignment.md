# Phase 3.3 Low-Tier Block-Cycle D-Flash Shape Alignment

## Summary

Phase 3.3 adds a new low-tier cycle trace path for D-Flash shape alignment.

The previous low-tier diagnostic path was useful and valid as a foundation, but it was closer to a single large draft continuation path than to a D-Flash block-cycle path.

This phase adds an iterative draft-block cycle trace so the low-tier path is closer to the intended D-Flash shape.

This is D-Flash shape alignment, not final D-Flash correctness.

## Motivation

Phase 3.2 remains accepted as timing-readiness scaffold. The next step changed because timing a single-large-draft path would not represent the intended low-tier D-Flash-shaped flow.

The new cycle trace records repeated draft-block cycles before future dry-run timing work. The output is trace-focused and no-claim.

## Previous Diagnostic Shape

The accepted Low-Tier Diagnostic MVP v0.1 path remains valid:

```text
prompt
  -> drafter generates one larger draft continuation
  -> text bridge validates or rejects the whole draft
  -> verifier continues from prompt plus the whole draft, or fallback context
```

That path remains available through:

```text
scripts/run_low_tier_trace.py
scripts/run_baseline_trace.py
scripts/run_benchmark_readiness.py
```

Phase 3.3 does not remove or alter those paths.

## New Block-Cycle Shape

The new trace path records this shape:

```text
prompt
  -> cycle 1:
       drafter receives current context
       drafter generates draft_text_chunk
       text bridge validates or rejects the draft block
       verifier processes current context plus draft block, or fallback context
       current context is updated
       cycle trace is recorded

  -> cycle 2..N:
       repeat until max cycles or optional max total text budget
```

The new command is:

```bash
.venv/bin/python scripts/run_low_tier_cycle_trace.py \
  --prompt-set phase-2-controlled-eligibility-v2 \
  --prompt-mode raw \
  --draft-block-size 8 \
  --max-cycles 4 \
  --capture-raw-output
```

## Implementation Changes

Added:

```text
src/htfsd/metrics/cycle_trace_schema.py
src/htfsd/text_bridge/cycle_trace.py
src/htfsd/cli/run_low_tier_cycle_trace.py
scripts/run_low_tier_cycle_trace.py
tests/test_low_tier_cycle_trace.py
```

Updated:

```text
pyproject.toml
```

The console entry point is:

```text
htfsd-run-low-tier-cycle-trace
```

The implementation adds a new path only. Existing MVP trace, baseline trace, selector, inspection, and timing-readiness scaffold remain unchanged.

## Trace Schema

Run-level fields include:

```text
trace_type: low_tier_cycle_trace
prompt_set_id
prompt_id
prompt_mode
capture_raw_output
draft_block_size
max_cycles
max_total_tokens
total_cycles
bridge_valid_block_count
bridge_rejected_block_count
cycle_fallback_count
runtime_policy
drafter_device_status
verifier_device_status
drafter_model_file
verifier_model_file
cycles
non_claims
```

Cycle-level fields include:

```text
cycle_id
draft_block_size
draft_text_summary
bridge_status
rejection_reason
cycle_fallback_count
drafter_latency_seconds
verifier_latency_seconds
context_length_before
context_length_after
draft_text_chunk, when raw capture is enabled
normalized_draft_text, when raw capture is enabled
verifier_raw_output, when raw capture is enabled
```

The schema avoids fields that would imply true token-level speculative verification.

## Tokenizer Boundary

Qwen tokenizer != Gemma tokenizer.

In this phase:

```text
draft_block_size: 8
```

means:

```text
Qwen draft max tokens = 8
```

It does not mean eight Gemma tokens. The trace records the generated text as `draft_text_chunk`, not as verified target tokens.

For scaffold practicality, the verifier continuation in the new command also uses the small per-cycle generation budget. That is a diagnostic bound, not a claim about target-token verification.

## Verification

Fresh cycle-trace command:

```text
trace_file: logs/reports/20260526T021258Z-low-tier-cycle-trace.json
trace_records: 16
total_cycles: 64
bridge_valid_block_count: 64
bridge_rejected_block_count: 0
cycle_fallback_count: 0
```

Focused cycle-trace tests:

```text
tests/test_low_tier_cycle_trace.py: 4 passed
```

Full test suite:

```text
185 passed
```

Forbidden-claim scan:

```text
clean
```

Formatting check:

```text
clean
```

## Example Cycle Trace

Example from the fresh trace:

```json
{
  "cycle_id": 1,
  "draft_block_size": 8,
  "draft_text_summary": "required. The user is asking for a",
  "bridge_status": "valid",
  "rejection_reason": null,
  "cycle_fallback_count": 0,
  "drafter_latency_seconds": 0.0,
  "verifier_latency_seconds": 0.0,
  "context_length_before": 26,
  "context_length_after": 85
}
```

The report rounds latency values in this example. The JSON artifact contains the recorded floating-point values.

## No-Claim Boundary

This is not output equality validation.
No output parity claim is made.
No target-equivalence claim is made.
No correctness claim is made.
No lossless-generation claim is made.
No benchmark claim is made.
No performance-improvement claim is made.
No draft-acceptance metric is reported.
No high-tier implementation claim is made.

This is D-Flash shape alignment, not final D-Flash correctness.
This is block-cycle trace scaffolding, not benchmark evidence.
No speedup claim is made.
No acceptance-rate claim is made.

## Remaining Limitations

This phase does not implement token-level target verification.

This phase does not prove the verifier output is target-equivalent.

This phase does not turn `bridge_valid_block_count` into a draft-success metric.

This phase records per-cycle latency fields, but the fields are descriptive trace metadata only.

The optional `max_total_tokens` stop uses the current text-level scaffold boundary and is not a cross-family tokenizer guarantee.

## Conclusion

Phase 3.3 adds the missing D-Flash-shaped iterative draft-block trace path without reopening the accepted MVP trace or Phase 3.2 timing scaffold.

The fresh run produced 16 prompt records and 64 cycle records with the refined eligibility prompt set. All 64 draft blocks passed the current text bridge in this run, and no cycle fallback was recorded.

These facts describe trace shape and bridge accounting only. They are not benchmark or correctness evidence.

## Next Step

Recommended next phase:

```text
Phase 3.4: Low-Tier Benchmark Dry Run / No-Claim Report
```

Phase 3.4 should use the D-Flash-shaped cycle trace path as the low-tier timing subject, while preserving the no-claim timing-readiness boundary from Phase 3.1 and Phase 3.2.
