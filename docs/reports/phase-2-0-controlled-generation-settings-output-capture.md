# Phase 2.0 Controlled Generation Settings and Output Capture Mode

## Summary

Phase 2.0 passed. The project now has centralized controlled generation settings, a shared prompt set for low-tier and target-baseline traces, and an explicit opt-in raw output capture mode.

This is not a benchmark. No performance-improvement claim is made. No output-equivalence claim is made. No draft-acceptance metric is reported.

## Generation Settings

Controlled trace settings are now represented by `GenerationSettings`:

```text
max_tokens: 64
temperature: 0.0
seed: 42
stop: null
prompt_mode: raw
capture_raw_output: false by default
output_summary_max_chars: 120
```

The low-tier trace and target-baseline trace both record the same settings snapshot in trace metadata and per-record `generation_settings`.

The trace CLIs now accept:

```bash
--capture-raw-output
--max-tokens
--temperature
```

## Prompt Set

The default trace prompt set is centralized as:

```text
prompt_set_id: phase-1-controlled-trace-v1
prompt-001: Explain speculative decoding in one short sentence.
prompt-002: Write a five word greeting.
prompt-003: List two benefits of GPU inference.
```

Both low-tier and target-baseline traces use this shared source.

Existing trace IDs remain compatible:

```text
low-tier: trace-001, trace-002, trace-003
target-baseline: baseline-001, baseline-002, baseline-003
```

The comparison utility continues to normalize the numeric suffix for prompt coverage.

## Raw Output Capture Policy

Default behavior keeps raw text out of trace records:

```text
capture_raw_output: false
raw_prompt: absent
qwen_raw_output: absent
gemma_raw_output: absent
baseline_raw_output: absent
```

When explicitly enabled, raw fields are added only to ignored trace logs under `logs/reports/`:

```bash
python scripts/run_low_tier_trace.py --capture-raw-output
python scripts/run_baseline_trace.py --capture-raw-output
```

Raw output capture is for controlled local analysis only. It does not imply output equality or correctness.

## Low-Tier Trace Result

Command run:

```bash
.venv/bin/python scripts/run_low_tier_trace.py
```

Result:

```text
trace_records: 3
fallback_count: 0
qwen_device_status: ok
gemma_device_status: ok
trace_file: logs/reports/20260524T150758Z-low-tier-trace.json
```

Raw-capture command also completed:

```bash
.venv/bin/python scripts/run_low_tier_trace.py --capture-raw-output
```

Result:

```text
trace_records: 3
fallback_count: 0
qwen_device_status: ok
gemma_device_status: ok
trace_file: logs/reports/20260524T150819Z-low-tier-trace.json
```

## Baseline Trace Result

Command run:

```bash
.venv/bin/python scripts/run_baseline_trace.py
```

Result:

```text
trace_records: 3
gemma_device_status: ok
trace_file: logs/reports/20260524T150807Z-target-baseline-trace.json
```

Raw-capture command also completed:

```bash
.venv/bin/python scripts/run_baseline_trace.py --capture-raw-output
```

Result:

```text
trace_records: 3
gemma_device_status: ok
trace_file: logs/reports/20260524T150826Z-target-baseline-trace.json
```

## Schema Result

Trace schema remains compatible with existing compact records.

Raw fields are optional:

```text
raw_prompt
qwen_raw_output
gemma_raw_output
baseline_raw_output
```

Schema validation accepts records with and without these optional raw fields.

## Comparison Metadata

The trace comparison report now includes generation-settings metadata:

```text
generation_settings_match
capture_raw_output_status
max_tokens_match
temperature_match
prompt_mode_match
stop_match
```

Comparison command run:

```bash
.venv/bin/python scripts/compare_trace_report.py \
  --low-tier logs/reports/20260524T150819Z-low-tier-trace.json \
  --baseline logs/reports/20260524T150826Z-target-baseline-trace.json
```

Result:

```text
low_tier_records: 3
baseline_records: 3
prompt_id_overlap: 3
schema_status: low-tier=ok baseline=ok
report_file: logs/reports/20260524T150834Z-trace-comparison-v0.md
```

## Tests

Full test suite passed:

```text
91 passed
```

New and updated tests cover:

- Generation settings defaults
- CLI generation overrides
- Shared prompt set source
- Low-tier settings metadata
- Baseline settings metadata
- Raw fields absent by default
- Raw fields present only when explicitly enabled
- Schema compatibility with optional raw fields
- Comparison metadata for settings match/mismatch

## Non-Claims

This is not a benchmark.

No performance-improvement claim is made.

No output-equivalence claim is made.

No draft-acceptance metric is reported.

## Remaining Issues

- Output equality is not compared.
- Raw output capture is opt-in and should remain uncommitted.
- `prompt_mode` is recorded as policy metadata for trace control; trace generation still uses the existing raw prompt path.
- Exact token-level draft verification remains future work.

## Conclusion

passed

Phase 2.0 establishes the controlled settings and opt-in raw capture foundation needed before future equality analysis can be designed.

## Next Step

Design Phase 2.1 around controlled output comparison preparation: raw output normalization policy, matching generation settings checks, and explicit equality-analysis preconditions. It should still avoid benchmark and exact-generation claims.
