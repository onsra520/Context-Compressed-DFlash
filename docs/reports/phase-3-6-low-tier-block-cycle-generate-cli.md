# Phase 3.6 Low-Tier Block-Cycle Generate CLI

## Summary

Phase 3.6 adds a practical low-tier generate CLI:

```text
input prompt -> block-cycle low-tier path -> response_text + descriptive metrics
```

New command:

```bash
.venv/bin/python scripts/generate_low_tier.py \
  --prompt "Hello. Reply in one short sentence." \
  --draft-block-size 8 \
  --max-cycles 4
```

The implementation remains low-tier only. It does not enter high-tier work.

## Motivation

The low-tier project already had:

```text
block-cycle trace path
benchmark-readiness dry run
timing scaffold
no-claim boundary
```

The missing user-facing piece was:

```text
prompt in -> response out -> initial descriptive metrics
```

This phase adds that surface while preserving the Phase 3.3 and Phase 3.4 interpretation guards.

## User-Facing Goal

The CLI accepts a single prompt and prints:

```text
RESPONSE:
...

METRICS:
trace_type: low_tier_cycle_generate
prompt_mode: raw
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
output_chars: ...
response_chars: ...
```

JSON mode is available:

```bash
.venv/bin/python scripts/generate_low_tier.py \
  --prompt "Explain caching in one sentence." \
  --draft-block-size 8 \
  --max-cycles 4 \
  --json
```

## Pipeline Shape

The generate pipeline follows the D-Flash-shaped low-tier cycle flow:

```text
current_context = prompt
response_parts = []

for each cycle:
  drafter receives current_context
  drafter produces draft_text_chunk
  text_bridge validates or rejects draft_text_chunk

  if bridge_status is valid:
    verifier receives current_context + normalized draft_text_chunk
    response chunk includes the normalized draft text and verifier text
  else:
    verifier runs from current_context
    response chunk includes fallback verifier text

  current_context is updated
  cycle metrics are recorded
```

Response assembly is intentionally simple and deterministic. It is not a target-equivalence layer.

## CLI Interface

New files:

```text
src/htfsd/low_tier/generate.py
src/htfsd/cli/generate_low_tier.py
scripts/generate_low_tier.py
tests/test_generate_low_tier.py
```

Console entry point:

```text
htfsd-generate-low-tier
```

Supported CLI arguments:

```text
--prompt
--draft-block-size
--max-cycles
--max-total-chars
--prompt-mode
--capture-raw-output
--json
--write-trace
```

Defaults:

```text
draft_block_size: 8
max_cycles: 4
prompt_mode: raw
capture_raw_output: false
write_trace: false
```

## Output Response

The live text CLI produced a response and metrics with real local GGUF backends. The terminal also showed verbose llama.cpp runtime logging before the CLI payload.

Text-mode summary:

```text
trace_type: low_tier_cycle_generate
prompt_mode: raw
draft_block_size: 8
max_cycles: 4
total_cycles: 4
bridge_valid_block_count: 4
bridge_rejected_block_count: 0
cycle_fallback_count: 0
output_chars: 251
response_chars: 251
```

JSON-mode summary:

```text
trace_type: low_tier_cycle_generate
prompt_mode: raw
draft_block_size: 8
max_cycles: 4
total_cycles: 4
bridge_valid_block_count: 4
bridge_rejected_block_count: 0
cycle_fallback_count: 0
output_chars: 318
response_chars: 318
```

These are descriptive generate-run fields only.

## Metrics

The result object is:

```text
LowTierGenerateResult
```

It includes:

```text
prompt
response_text
trace_type
prompt_mode
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
trace_path
```

Metrics include:

```text
total_wall_time_seconds
drafter_latency_seconds_total
verifier_latency_seconds_total
bridge_latency_seconds_total
output_chars
response_chars
draft_text_chunk_count
verifier_text_chunk_count
tokens_per_second_descriptive
latency_seconds_descriptive
```

`tokens_per_second_descriptive` remains `null` because cross-family token counts are not reliable enough for this user-facing low-tier response surface.

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

## Trace Artifact Policy

By default, the CLI does not write trace artifacts.

If `--write-trace` is passed, it writes:

```text
logs/reports/<timestamp>-low-tier-generate-trace.json
```

These local trace artifacts are ignored logs and should not be committed.

The trace includes:

```text
prompt
response_text
cycle traces
metrics
interpretation guards
non_claims
```

Raw draft/verifier chunks are included only when `--capture-raw-output` is set.

## Verification

New test file:

```text
tests/test_generate_low_tier.py
```

Focused tests:

```text
.venv/bin/pytest tests/test_generate_low_tier.py tests/test_low_tier_cycle_trace.py tests/test_timing_readiness.py -v
18 passed
```

Live text CLI:

```text
.venv/bin/python scripts/generate_low_tier.py \
  --prompt "Hello. Reply in one short sentence." \
  --draft-block-size 8 \
  --max-cycles 4
exit_code: 0
```

Live JSON CLI:

```text
.venv/bin/python scripts/generate_low_tier.py \
  --prompt "Explain caching in one sentence." \
  --draft-block-size 8 \
  --max-cycles 4 \
  --json
exit_code: 0
```

Full-suite, forbidden-claim scan, and formatting checks are part of the final Phase 3.6 completion gate.

Full test suite:

```text
.venv/bin/pytest -v
192 passed
```

Forbidden-claim scan:

```text
clean
```

Formatting check:

```text
git diff --check
clean
```

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

`bridge_valid_block_count` is not acceptance.

`cycle_fallback_count` is not correctness or performance evidence.

## Remaining Limitations

The CLI is intentionally simple:

```text
no high-tier path
no target model verification
no hidden-state extraction
no quality evaluation
no timing comparison
verbose llama.cpp runtime logs may appear in terminal output
```

The generated response is a low-tier diagnostic response, not a proof of target-equivalent generation.

## Conclusion

Phase 3.6 adds the first practical low-tier prompt-in/response-out CLI over the block-cycle path. It prints response text, records initial descriptive metrics, supports JSON output, and can write local trace artifacts on demand.

## Next Step

Recommended next phase:

```text
Phase 3.7: Low-Tier Generate CLI Hardening and UX Design
```

That phase should decide whether to reduce llama.cpp terminal noise, add clearer output modes, and define a small user-facing smoke checklist without adding benchmark or high-tier claims.
