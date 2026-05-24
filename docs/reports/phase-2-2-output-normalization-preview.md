# Phase 2.2 Output Normalization Preview

## Summary

Phase 2.2 added a conservative output normalization preview command for raw-capture low-tier and target-baseline traces.

The preview command reuses the Phase 2.1 precheck first. If the precheck is not ready, preview generation is blocked and the blocking reasons are reported. If the precheck is ready, the command writes per-prompt normalized preview records for human inspection.

This is inspection infrastructure only.

## Preview Command

Command added:

```bash
python scripts/preview_output_comparison.py \
  --low-tier logs/reports/<low-tier-raw-trace>.json \
  --baseline logs/reports/<target-baseline-raw-trace>.json
```

The command writes:

```text
logs/reports/<timestamp>-output-normalization-preview.md
logs/reports/<timestamp>-output-normalization-preview.json
```

## Input Traces

Verification used:

```text
low-tier trace:
logs/reports/20260524T181810Z-low-tier-trace.json

target-baseline trace:
logs/reports/20260524T181817Z-target-baseline-trace.json
```

## Precheck Status

The Phase 2.1 precheck passed before preview generation:

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

## Normalization Policy

The preview uses the conservative normalization policy from Phase 2.1:

```text
preserve original raw output
normalize CRLF to LF
strip leading/trailing whitespace
do not collapse repeated whitespace by default
do not remove semantic content
do not remove model-specific content
```

Draft normalization and final-output normalization remain separate. The preview does not apply text bridge draft normalization to final outputs.

## Preview Fields

Each preview record includes:

```text
prompt_id
prompt_summary
prompt_hash
low_tier_output_present
baseline_output_present
low_tier_normalized_length
baseline_normalized_length
low_tier_empty_after_normalization
baseline_empty_after_normalization
normalized_outputs_exact_string_match
low_tier_preview
baseline_preview
```

Preview text is truncated to `preview_max_chars`, which defaults to `200`.

## Preview Result

Generated preview:

```text
logs/reports/20260524T181823Z-output-normalization-preview.md
logs/reports/20260524T181823Z-output-normalization-preview.json
```

Observed summary:

```text
preview_ready: yes
preview_records: 3
blocking_reasons: []
normalized_outputs_exact_string_match count: 0
low_tier_empty_after_normalization count: 0
baseline_empty_after_normalization count: 2
```

Per-record normalized lengths:

```text
trace-001: low_tier=79, baseline=0
trace-002: low_tier=38, baseline=0
trace-003: low_tier=9, baseline=355
```

These values are preview observations only.

## Tests

Focused preview tests:

```text
.venv/bin/pytest tests/test_output_preview.py -v
8 passed
```

Full verification is expected to include:

```text
.venv/bin/pytest -v
```

## Non-Claims

This is not an output equality report.
Exact string match preview is not target-equivalence validation.
No output parity claim is made.
No correctness claim is made.
No lossless-generation claim is made.
No benchmark claim is made.

## Remaining Issues

The preview report intentionally does not judge output quality or target alignment. Baseline empty outputs were observed for two prompts in this verification run, but Phase 2.2 only records those flags for inspection.

## Conclusion

passed

Phase 2.2 provides a guarded, conservative preview layer for raw-capture trace inspection.

## Next Step

Phase 2.3 should design controlled exact-string diagnostic comparison rules. It should remain diagnostic and should not be framed as target-equivalence validation.
