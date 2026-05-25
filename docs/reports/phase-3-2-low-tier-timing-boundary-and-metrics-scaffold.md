# Phase 3.2 Low-Tier Timing Boundary and Metrics Scaffold

## Summary

Phase 3.2 implements a small timing-readiness scaffold based on the Phase 3.1 design.

The scaffold adds schema dataclasses, environment snapshot capture, timing summary writing, a minimal CLI runner, and tests. It writes readiness artifacts under ignored local logs and keeps all timing fields descriptive.

## What Was Implemented

New modules:

```text
src/htfsd/metrics/timing_schema.py
src/htfsd/metrics/environment_snapshot.py
src/htfsd/metrics/timing_summary.py
src/htfsd/cli/run_benchmark_readiness.py
scripts/run_benchmark_readiness.py
tests/test_timing_readiness.py
```

Updated entry point:

```text
pyproject.toml
```

New console script:

```text
htfsd-run-benchmark-readiness
```

## Timing Schema

The scaffold defines:

```text
TimingBoundary
RunManifest
TimingSummary
TimingCategorySummary
```

Timing boundary fields:

```text
environment_check_time_seconds
model_discovery_time_seconds
model_load_time_seconds
prompt_preparation_time_seconds
drafter_generation_time_seconds
bridge_normalization_time_seconds
verifier_continuation_time_seconds
baseline_generation_time_seconds
selection_or_diagnostic_time_seconds
generation_time_seconds
diagnostic_overhead_seconds
total_wall_time_seconds
```

Descriptive timing fields:

```text
tokens_per_second_descriptive
latency_seconds_descriptive
```

The scaffold does not define fields named:

```text
speedup
performance_gain
benchmark_score
acceptance_rate
```

## Run Manifest

The manifest records:

```text
run_id
created_at_utc
run_kind
mvp_name
prompt_set_id
prompt_count
prompt_mode
capture_raw_output
generation_settings
config_path
git_commit
runtime_backend
environment_snapshot
artifact_paths
non_claims
```

Default scaffold manifest values:

```text
mvp_name: Low-Tier Diagnostic MVP v0.1
prompt_set_id: phase-2-controlled-eligibility-v2
prompt_count: 16
prompt_mode: raw
capture_raw_output: false
runtime_backend: llama.cpp
```

## Environment Snapshot

The helper records best-effort environment metadata:

```text
os
python_version
package_versions
llama_cpp_python_version
cuda_available
cuda_toolkit_version_if_available
gpu_name_if_available
driver_version_if_available
git_commit
config_path
prompt_set_id
runtime_backend
```

Optional details are recorded as `unknown` when unavailable. Missing optional environment details do not fail the scaffold run.

Fresh scaffold run snapshot included:

```text
gpu_name_if_available: NVIDIA GeForce RTX 4070 Laptop GPU
driver_version_if_available: 596.49
llama_cpp_python_version: 0.3.23
git_commit: 125f921
```

## Timing Summary Writer

The writer creates:

```text
<run_id>-run-manifest.json
<run_id>-timing-summary.json
<run_id>-benchmark-readiness-report.md
```

It writes JSON with sorted keys and markdown with explicit non-claims. Missing measured timing boundaries are represented as `null` in JSON and are not interpreted as measurements.

## Readiness Runner

New command:

```bash
.venv/bin/python scripts/run_benchmark_readiness.py
```

Fresh scaffold run:

```text
run_id: 20260525T150243Z
run_manifest: logs/benchmark-readiness/20260525T150243Z-run-manifest.json
timing_summary: logs/benchmark-readiness/20260525T150243Z-timing-summary.json
readiness_report: logs/benchmark-readiness/20260525T150243Z-benchmark-readiness-report.md
benchmark_claims: none
```

The runner creates scaffold artifacts only. It does not run a timed benchmark loop.

## Artifact Layout

Artifacts are written under:

```text
logs/benchmark-readiness/
```

Fresh artifact layout:

```text
logs/benchmark-readiness/20260525T150243Z-run-manifest.json
logs/benchmark-readiness/20260525T150243Z-timing-summary.json
logs/benchmark-readiness/20260525T150243Z-benchmark-readiness-report.md
```

These logs are local readiness artifacts and are not committed.

## Fallback-Aware Categories

Timing summaries preserve these categories:

```text
valid_draft_continuation
fallback_after_rejection
fallback_only
unknown_contribution
eligible_valid_draft_record
excluded_fallback_derived_record
excluded_empty_baseline_record
excluded_unknown_contribution_record
```

Category records are scaffold placeholders in this phase. Phase 3.3 can populate them from actual dry-run traces.

Required interpretation rule remains:

```text
Do not aggregate fallback-derived timing with valid-draft timing without category labels.
```

## Verification

Focused TDD verification:

```text
.venv/bin/pytest tests/test_timing_readiness.py -v
7 passed
```

Required scaffold command:

```text
.venv/bin/python scripts/run_benchmark_readiness.py
passed
```

Full verification will remain:

```text
.venv/bin/pytest -v
forbidden-claim scan
git diff --check
```

Fresh full verification:

```text
.venv/bin/pytest -v: 181 passed
forbidden-claim scan: clean
git diff --check: clean
```

## Non-Claims

```text
This is not a benchmark report.
This is not a performance comparison.
No speedup claim is made.
No performance-improvement claim is made.
No output parity claim is made.
No target-equivalence claim is made.
No correctness claim is made.
No lossless-generation claim is made.
No draft-acceptance metric is reported.
No high-tier implementation claim is made.
```

## Remaining Issues

```text
timing boundaries are scaffold fields only
measured boundary values are null until Phase 3.3 or later
the runner does not execute warmup or measured repetitions yet
category summaries are placeholders until joined with trace outputs
load time and generation time are not populated yet
```

## Recommended Next Step

Proceed to:

```text
Phase 3.3: Low-Tier Benchmark Dry Run / No-Claim Report
```

Phase 3.3 should run a controlled dry run, populate scaffold timing fields where safe, keep load/generation/diagnostic overhead separated, and continue using no-claim reporting language.

## Conclusion

Phase 3.2 adds the timing-readiness scaffold without changing low-tier trace semantics, baseline trace semantics, diagnostic selector logic, prompt sets, generation settings, or device policy.

The project now has a small artifact writer and manifest format ready for a future dry-run phase. The scaffold prepares measurement infrastructure without producing benchmark conclusions or performance comparisons.
