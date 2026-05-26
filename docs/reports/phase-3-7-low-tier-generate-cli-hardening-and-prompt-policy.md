# Phase 3.7 Low-Tier Generate CLI Hardening and Prompt Policy

## Summary

Phase 3.7 hardens the user-facing low-tier block-cycle generation CLI added in Phase 3.6.

The correct pipeline name is:

```text
low-tier block-cycle generation pipeline
```

This phase adds:

```text
instruction prompt policy
raw/instruction/chat prompt-mode options
effective_prompt recording
conservative response cleanup
response_cleanup_applied metric
quiet/verbose argument parsing
input validation
trace payload hardening
additional fake-backend tests
```

This remains a low-tier usability hardening phase. It does not add high-tier behavior or new research claims.

## Motivation

Phase 3.6 proved prompt-in/response-out generation works. It also showed that raw mode can produce confusing prompt-misaligned output, including generic answer scaffolding unrelated to the requested concise response.

The goal of Phase 3.7 is to make the CLI easier to inspect and demo without claiming generation correctness.

## Pipeline Name

Use:

```text
low-tier block-cycle generation pipeline
```

Do not use:

```text
D-Flash correctness pipeline
speculative decoding correctness pipeline
lossless speculative decoding pipeline
target-equivalent generation pipeline
```

## Prompt Policy

The generate CLI now supports:

```text
--prompt-mode raw
--prompt-mode instruction
--prompt-mode chat
```

The default is:

```text
prompt_mode: instruction
```

Instruction mode applies a simple prompt wrapper:

```text
You are a concise assistant. Follow the user request directly.
User: {prompt}
Assistant:
```

This is not a model-native chat template. It is a simple instruction wrapper for user-facing generation.

Raw mode remains available for diagnostics:

```bash
.venv/bin/python scripts/generate_low_tier.py \
  --prompt "Hello. Reply in one short sentence." \
  --prompt-mode raw \
  --draft-block-size 8 \
  --max-cycles 4
```

The result object records both:

```text
prompt
effective_prompt
```

## Response Cleanup

Response cleanup is conservative:

```text
strip leading/trailing whitespace
normalize CRLF/CR to LF
collapse excessive blank lines
remove exact prompt/effective-prompt echo only when it appears as a prefix
```

The result records:

```text
metrics.response_cleanup_applied
```

No semantic rewriting is performed. The cleanup layer does not remove model content merely because it looks awkward or low quality.

## CLI Output Contract

Text output keeps stable sections:

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
output_chars: ...
response_chars: ...
response_cleanup_applied: true/false
```

JSON output includes:

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
metrics
interpretation_guards
non_claims
trace_path
```

## Runtime Verbosity

The CLI now accepts:

```text
--quiet
--verbose
```

Current limitation:

```text
native llama.cpp runtime logs may still appear before the CLI payload
```

The flags are present so the CLI contract can distinguish compact user-facing output from intentionally verbose runs. Full suppression of native runtime logs remains a follow-up because the current GGUF runtime can emit logs below the Python print layer.

## Input Validation

The CLI now returns a clear nonzero error for:

```text
blank prompt
draft_block_size <= 0
max_cycles <= 0
max_total_chars <= 0
```

Invalid prompt mode is handled by argparse choices.

## Trace Policy

When `--write-trace` is used, the CLI writes:

```text
logs/reports/<timestamp>-low-tier-generate-trace.json
```

Trace payload includes:

```text
prompt
effective_prompt
prompt_mode
response_text
response_cleanup_applied
cycle traces
metrics
interpretation guards
non_claims
```

Raw chunks remain opt-in through:

```text
--capture-raw-output
```

Local trace files remain ignored artifacts and should not be committed.

## Verification

Focused tests:

```text
.venv/bin/pytest tests/test_generate_low_tier.py tests/test_low_tier_cycle_trace.py tests/test_timing_readiness.py -v
25 passed
```

Live default instruction-mode CLI:

```text
.venv/bin/python scripts/generate_low_tier.py \
  --prompt "Hello. Reply in one short sentence." \
  --draft-block-size 8 \
  --max-cycles 4
exit_code: 0
prompt_mode: instruction
total_cycles: 4
bridge_valid_block_count: 4
bridge_rejected_block_count: 0
cycle_fallback_count: 0
```

Live JSON CLI:

```text
.venv/bin/python scripts/generate_low_tier.py \
  --prompt "Explain caching in one sentence." \
  --draft-block-size 8 \
  --max-cycles 4 \
  --json
exit_code: 0
prompt_mode: instruction
total_cycles: 4
bridge_valid_block_count: 4
bridge_rejected_block_count: 0
cycle_fallback_count: 0
```

Live raw-mode CLI:

```text
.venv/bin/python scripts/generate_low_tier.py \
  --prompt "Hello. Reply in one short sentence." \
  --prompt-mode raw \
  --draft-block-size 8 \
  --max-cycles 4
exit_code: 0
prompt_mode: raw
total_cycles: 4
bridge_valid_block_count: 4
bridge_rejected_block_count: 0
cycle_fallback_count: 0
```

Full suite:

```text
.venv/bin/pytest -v
199 passed
```

Repository hygiene:

```text
forbidden-claim scan: clean
git diff --check: clean
```

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

The correct name is low-tier block-cycle generation pipeline.

This is not a D-Flash/speculative decoding correctness pipeline.

`bridge_valid_block_count` is not acceptance.

`cycle_fallback_count` is not correctness or performance evidence.

## Remaining Limitations

Instruction mode improves the user-facing prompt policy, but it does not guarantee high-quality or request-aligned output.

Raw mode remains useful for diagnostics and can still produce generic or prompt-misaligned text.

Runtime logs from llama.cpp may still appear before the CLI payload.

The CLI still does not perform:

```text
target-token verification
baseline equivalence checks
lossless generation checks
benchmark comparisons
high-tier execution
```

## Conclusion

Phase 3.7 hardens the low-tier generate CLI without expanding research claims. The CLI now has a safer default prompt policy, cleaner response handling, clearer validation, and more stable text/JSON output contracts.

## Next Step

Recommended next phase:

```text
Phase 3.8: Low-Tier Generate CLI Runtime Log Suppression Design
```

That phase should specifically decide whether to add backend-level log suppression or process-level output isolation for cleaner demos.
