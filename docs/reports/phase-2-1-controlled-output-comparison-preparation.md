# Phase 2.1 Controlled Output Comparison Preparation

## Summary

Phase 2.1 passed. The project now has an output comparison precheck command that inspects one low-tier raw-capture trace and one target-baseline raw-capture trace for readiness.

The precheck validates prerequisites only. It does not compare output text for equality, correctness, or quality.

## Preconditions

The precheck verifies:

```text
both traces exist
both traces pass schema validation
both traces have raw capture enabled
prompt coverage matches
generation settings match
Gemma model file matches
Gemma device status is ok in both traces
required raw output fields are present
```

Command:

```bash
python scripts/prepare_output_comparison.py \
  --low-tier logs/reports/<low-tier-raw-trace>.json \
  --baseline logs/reports/<target-baseline-raw-trace>.json
```

## Raw Capture Requirement

Raw capture remains opt-in.

Required low-tier raw fields:

```text
raw_prompt
qwen_raw_output
gemma_raw_output
```

Required target-baseline raw fields:

```text
raw_prompt
baseline_raw_output
```

The command fails readiness if raw capture metadata or raw fields are missing.

## Generation Settings Requirement

The precheck requires matching generation settings:

```text
max_tokens
temperature
seed
stop
prompt_mode
capture_raw_output
output_summary_max_chars
```

The verified raw-capture traces matched on generation settings.

## Runtime Metadata Requirement

The precheck requires:

```text
Gemma model file match
low-tier Gemma device status = ok
target-baseline Gemma device status = ok
```

The verified traces used:

```text
Gemma E2B CUDA
device_status: ok
```

## Normalization Policy

The normalization preview is conservative:

```text
preserve original raw output
normalize CRLF to LF
strip leading/trailing whitespace
do not collapse repeated whitespace by default
do not remove semantic content
do not remove model-specific content
```

This policy is for preview and future analysis preparation only.

## Precheck Result

Raw traces generated:

```text
low-tier: logs/reports/20260524T180900Z-low-tier-trace.json
target-baseline: logs/reports/20260524T180908Z-target-baseline-trace.json
```

Precheck reports generated:

```text
markdown: logs/reports/20260524T180915Z-output-comparison-precheck.md
json: logs/reports/20260524T180915Z-output-comparison-precheck.json
```

Result:

```text
output_comparison_ready: yes
blocking_reasons: []
schema_status: ok
raw_capture_status: enabled for both traces
prompt_coverage_status: ok
generation_settings_match: true
runtime_metadata_match: true
raw_field_presence_status: ok
```

## Tests

Full test suite passed:

```text
99 passed
```

Tests cover:

- Passing precheck for matching raw-capture traces
- Missing raw capture
- Prompt coverage mismatch
- Generation settings mismatch
- Gemma model file mismatch
- Blocking reason recording
- Conservative normalization preview
- Explicit non-claim report wording
- CLI markdown and JSON report writing

## Non-Claims

This is not an output equality report.

No output parity claim is made.

No exact-generation claim is made.

No benchmark claim is made.

## Remaining Issues

- Output text is not compared.
- No correctness or quality judgment is made.
- The normalization preview is conservative and not yet a comparison algorithm.
- Token-level target verification remains future work.

## Conclusion

passed

Phase 2.1 establishes a readiness gate for future controlled output comparison work.

## Next Step

Phase 2.2 should add an output normalization preview/report that displays normalized previews and differences for inspection, while still avoiding equality or correctness claims.
