# Phase 2.16 De-Smoke and Role-Based Naming Refactor

## Summary

Phase 2.16 refactored MVP-facing model naming from prototype/model-specific labels to role-based labels.

This phase does not change runtime behavior. This phase stabilizes MVP-facing names before the reproducibility pack.

## Motivation

Phase 2.15 accepted Low-Tier Diagnostic MVP v0.1 as a diagnostic pipeline rather than a one-off smoke path. The core configuration, trace records, schema guards, and CLI summaries now use stable role names where the current model assignments are implementation details.

## Naming Policy

Role mapping:

```text
drafter  -> current Qwen3-0.6B
verifier -> current Gemma E2B
target   -> current/future Gemma E4B
```

Canonical MVP-facing names:

```text
drafter_model_file
drafter_expected_device
drafter_device_status
drafter_n_gpu_layers
drafter_decode_tokens_per_second

verifier_model_file
verifier_expected_device
verifier_device_status
verifier_n_gpu_layers
verifier_decode_tokens_per_second
```

## Config Migration

The canonical config keys are now:

```text
models.drafter
models.verifier
models.target
```

`configs/local.example.yaml` was migrated to those role keys. Deprecated aliases remain supported for local compatibility:

```text
qwen_drafter -> drafter
gemma_e2b    -> verifier
gemma_e4b    -> target
```

The target role remains optional.

## Refactor Scope

Updated core areas:

```text
src/htfsd/types.py
src/htfsd/config.py
src/htfsd/runtime/diagnostics.py
src/htfsd/metrics/run_trace.py
src/htfsd/metrics/baseline_trace.py
src/htfsd/metrics/trace_schema.py
src/htfsd/metrics/trace_compare.py
src/htfsd/metrics/output_compare.py
src/htfsd/cli/check_env.py
src/htfsd/cli/run_low_tier_trace.py
src/htfsd/cli/run_baseline_trace.py
configs/local.example.yaml
```

`PairSmokeResult` was replaced by `LowTierTraceResult` in core types. The smoke entry points are still present as development diagnostics.

## Compatibility Strategy

Compatibility aliases are preserved for:

```text
old local configs
historical trace records
older tests and fixtures
smoke-era scripts
```

Fresh diagnostics and traces emit canonical role-based fields. Existing model-specific trace fields are retained as deprecated compatibility aliases so downstream tools can continue reading older artifacts during the migration.

## Trace Schema Strategy

The schema guard now defines role-based required fields for live and baseline records. It also accepts deprecated field aliases when validating older traces.

Fresh Phase 2.16 trace verification confirmed canonical fields are present:

```text
low-tier trace:
  drafter_* fields present
  verifier_* fields present

target-baseline trace:
  verifier_* fields present
```

## Verification

Executed:

```bash
.venv/bin/python scripts/check_env.py
.venv/bin/python scripts/run_low_tier_trace.py --capture-raw-output --prompt-mode raw --prompt-set phase-2-controlled-eligibility-v2
.venv/bin/python scripts/run_baseline_trace.py --capture-raw-output --prompt-mode raw --prompt-set phase-2-controlled-eligibility-v2
.venv/bin/python scripts/select_diagnostic_records.py --low-tier logs/reports/20260525T135719Z-low-tier-trace.json --baseline logs/reports/20260525T135738Z-target-baseline-trace.json
.venv/bin/python scripts/inspect_eligible_records.py --low-tier logs/reports/20260525T135719Z-low-tier-trace.json --baseline logs/reports/20260525T135738Z-target-baseline-trace.json
.venv/bin/pytest -q
```

Observed:

```text
environment check: ok
low-tier trace records: 16
low-tier fallback_count: 0
baseline trace records: 16
selector eligible_valid_draft_record_count: 16
inspection eligible_record_count: 16
tests: 174 passed
```

## Naming Audit Result

The naming audit still finds old names in allowed locations:

```text
historical reports
compatibility alias mappings
compatibility alias tests
smoke command names and outputs
older fixture fields used to verify alias handling
```

No canonical config example uses the old required keys. Fresh trace records include the role-based fields.

## Non-Claims

This is not output equality validation.
No output parity claim is made.
No target-equivalence claim is made.
No correctness claim is made.
No lossless-generation claim is made.
No benchmark claim is made.
No performance-improvement claim is made.
No draft-acceptance metric is reported.
No high-tier implementation claim is made.

## Remaining Issues

Some compatibility aliases remain in core helper modules so historical traces and old local configs keep working. Smoke scripts still use smoke-era command names by design.

## Conclusion

passed

Phase 2.16 completed the MVP-facing role-name cleanup without changing runtime behavior.

## Next Step

Phase 2.17: Low-Tier Diagnostic MVP Reproducibility Pack.
