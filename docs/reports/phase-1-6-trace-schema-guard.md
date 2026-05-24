# Phase 1.6 Trace Schema Guard

## Summary

Phase 1.6 passed. The project now has an explicit schema guard for low-tier trace records, covering both live trace mode and controlled fallback mode. The guard protects required fields for bridge status, fallback accounting, runtime policy, model files, and latency so future changes cannot silently drop them.

An inspect command was added:

```bash
python scripts/inspect_trace_schema.py logs/reports/<trace-file>.json --mode live
python scripts/inspect_trace_schema.py logs/reports/<trace-file>.json --mode controlled-fallback
```

## Required Trace Fields

Shared required fields:

- `prompt_id`
- `bridge_status`
- `rejection_reason`
- `fallback_count`
- `draft_valid_count`
- `draft_rejected_count`
- `qwen_expected_device`
- `gemma_expected_device`
- `qwen_device_status`
- `gemma_device_status`
- `qwen_n_gpu_layers`
- `gemma_n_gpu_layers`
- `qwen_model_file`
- `gemma_model_file`
- `latency_seconds`

Controlled fallback records additionally require:

- `case_id`
- `gemma_fallback_used`

Raw prompt/output fields are not required and remain absent by default.

## Live Trace Schema Result

Live trace file:

- `logs/reports/20260524T142635Z-low-tier-trace.json`

Inspection result:

```text
records: 3
mode: live
trace schema: ok
```

## Controlled Fallback Schema Result

Controlled fallback trace file:

- `logs/reports/20260524T142638Z-low-tier-trace.json`

Inspection result:

```text
records: 4
mode: controlled-fallback
trace schema: ok
```

## Tests

Added schema tests for:

- Live trace required fields
- Controlled fallback required fields
- Missing-field failure behavior
- Raw text fields not being required
- Trace-file validation across records
- Inspect CLI success and failure output
- Live trace records satisfying schema
- Controlled fallback records satisfying schema

Full test suite passed: 68 tests.

Forbidden-claim scan passed with zero matches.

## Remaining Issues

- The schema guard checks field presence only; it does not yet enforce field value types or allowed value enums.
- This phase protects trace shape only. It does not add benchmark logic or exact token-level speculation.

## Conclusion

passed

## Next Step

Prepare baseline trace comparison scaffolding while keeping it claim-free: collect target-model-only trace metadata and compare schemas/counts without reporting speedup or equivalence.
