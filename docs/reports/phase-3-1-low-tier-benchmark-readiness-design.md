# Phase 3.1 Low-Tier Benchmark Readiness Design

## Summary

Phase 3.1 designs a benchmark-readiness layer for the closed `Low-Tier Diagnostic MVP v0.1`.

This phase defines future timing boundaries, metrics shape, run protocol, artifact layout, environment capture, fallback-aware timing categories, and no-claim reporting rules. It is design-only and does not add benchmark code.

## Motivation

The MVP now has reproducible diagnostic traces with:

```text
prompt_set_id: phase-2-controlled-eligibility-v2
prompt_count: 16
valid_draft_continuation_count: 16
baseline_empty_after_normalization_count: 0
eligible_valid_draft_record_count: 16
pytest: 174 passed
forbidden-claim scan: clean
```

The next risk is over-reading latency fields before the project has stable timing definitions. Benchmark readiness should define how timing is captured and reported before any future dry run starts producing measurement artifacts.

## Benchmark-Readiness Scope

Benchmark readiness includes:

```text
timing boundary definitions
load time separation
warmup policy
measured repetition policy
prompt set policy
metrics schema
environment snapshot fields
artifact layout
fallback-aware timing categories
no-claim reporting language
Phase 3.2 implementation shape
```

It does not include benchmark execution, statistical claims, speed comparisons, or output-quality conclusions.

## Non-Benchmark Boundary

Phase 3.1 is a design report. It does not run timed experiments and does not compare low-tier and baseline timing as evidence for runtime advantage.

Future readiness reports may record descriptive timing fields, but the fields must remain clearly labeled as readiness metadata until the project has:

```text
stable timing boundaries
consistent warmup behavior
repeated measured runs
separated load and generation timing
fallback-aware category summaries
documented environment snapshot
```

## Timing Boundaries

Future timing capture should separate these boundaries:

```text
environment_check_time
model_discovery_time
model_load_time
prompt_preparation_time
drafter_generation_time
bridge_normalization_time
verifier_continuation_time
baseline_generation_time
selection_or_diagnostic_time
total_wall_time
```

Benchmark-candidate generation boundaries:

```text
drafter_generation_time
bridge_normalization_time
verifier_continuation_time
baseline_generation_time
```

Operational overhead boundaries:

```text
environment_check_time
model_discovery_time
model_load_time
prompt_preparation_time
selection_or_diagnostic_time
```

Aggregate wall-clock boundary:

```text
total_wall_time
```

Required rule:

```text
model load time is reported separately and is not mixed into generation-only timing
```

## Load Time vs Generation Time

Definitions:

```text
cold run:
  a run that includes model construction/loading after process start

warm run:
  a run after the backend has already loaded the relevant model objects

load-inclusive timing:
  timing that includes model load and setup boundaries

generation-only timing:
  timing that includes only per-prompt model generation and bridge work

diagnostic overhead timing:
  timing spent in schema checks, normalization previews, selector work, report writing, and other non-generation diagnostics
```

Required policies:

```text
Do not compare load-inclusive low-tier timing to generation-only baseline timing.
Do not mix diagnostic overhead into model generation timing.
Report load-inclusive and generation-only fields separately.
Report diagnostic overhead separately from model-generation fields.
```

## Warmup Policy

Recommended warmup policy:

```text
1 warmup trace per mode before measured repetitions
warmup uses the same prompt set and generation settings as measured runs
warmup artifacts may be kept locally under ignored logs
warmup artifacts are excluded from summary timing metrics
warmup status is recorded in the run manifest
```

Warmup should be run for both low-tier and baseline paths when both paths are part of a readiness dry run.

## Repetition Policy

Recommended repeated-run policy:

```text
minimum 3 measured repetitions for dry-run readiness
minimum 5 measured repetitions for future benchmark-candidate work
record each repetition separately
record run order
record whether models were loaded once or per repetition
report descriptive summaries only after timing boundaries are stable
```

Do not claim statistical strength from the readiness repetitions. Repetitions are for stability inspection and artifact validation first.

## Prompt Set Policy

Initial readiness should use the canonical MVP prompt set:

```text
phase-2-controlled-eligibility-v2
```

Each run should record:

```text
prompt_set_id
prompt_count
prompt_ids
prompt_mode
capture_raw_output
generation_settings
```

Default readiness mode should use:

```text
prompt_mode: raw
capture_raw_output: false by default unless a diagnostic run explicitly needs raw output
```

Raw output capture is useful for diagnostic inspection, but timing readiness should avoid raw capture by default unless the run purpose requires it.

## Metrics Schema

Suggested trace-level fields:

```text
run_id
run_kind
prompt_set_id
prompt_count
prompt_mode
capture_raw_output
generation_settings
drafter_model_file
verifier_model_file
drafter_device_status
verifier_device_status
drafter_expected_device
verifier_expected_device
drafter_n_gpu_layers
verifier_n_gpu_layers
model_load_time_seconds
generation_time_seconds
diagnostic_overhead_seconds
total_wall_time_seconds
total_prompt_tokens
total_completion_tokens
tokens_per_second_descriptive
latency_seconds_descriptive
```

Suggested per-record fields:

```text
prompt_id
contribution_category
selection_category
fallback_count
draft_valid_count
draft_rejected_count
baseline_empty_after_normalization
eligible_for_draft_contribution_diagnostic
drafter_generation_time_seconds
bridge_normalization_time_seconds
verifier_continuation_time_seconds
baseline_generation_time_seconds
record_total_time_seconds
prompt_tokens
completion_tokens
tokens_per_second_descriptive
latency_seconds_descriptive
```

Naming rules:

```text
Use tokens_per_second_descriptive rather than claim-oriented names.
Use latency_seconds_descriptive for reported timing summaries.
Do not name readiness fields as proof fields.
```

## Environment Snapshot

Minimally viable Phase 3.2 environment snapshot fields:

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

The snapshot should be written into a run manifest. If a field cannot be discovered reliably, the manifest should record `unknown` rather than omitting the field.

## Artifact Layout

Future benchmark-readiness artifacts should live under ignored logs:

```text
logs/benchmark-readiness/
  <timestamp>-run-manifest.json
  <timestamp>-low-tier-trace.json
  <timestamp>-baseline-trace.json
  <timestamp>-timing-summary.json
  <timestamp>-benchmark-readiness-report.md
```

Optional repetition layout:

```text
logs/benchmark-readiness/
  <timestamp>-run-manifest.json
  repetitions/
    rep-001-low-tier-trace.json
    rep-001-baseline-trace.json
    rep-002-low-tier-trace.json
    rep-002-baseline-trace.json
  <timestamp>-timing-summary.json
  <timestamp>-benchmark-readiness-report.md
```

Do not commit raw benchmark-readiness logs.

## Fallback-Aware Timing Categories

Timing summaries must preserve contribution categories:

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

Required rule:

```text
Do not aggregate fallback-derived timing with valid-draft timing without separate category labels.
```

Recommended category summaries:

```text
record_count
prompt_ids
generation_time_seconds_summary
tokens_per_second_descriptive_summary
fallback_count_total
draft_valid_count_total
draft_rejected_count_total
selection_category_count
warnings
```

## No-Claim Reporting Rules

Allowed wording:

```text
This run recorded descriptive timing fields.
This run produced timing-readiness artifacts.
The timing boundaries were captured.
The report separates load time, generation time, and diagnostic overhead.
The report groups timing fields by contribution category.
```

Disallowed wording:

```text
low-tier runtime advantage is proven
numeric speedup is established
runtime quality is proven
production benchmark is complete
statistical evidence is established
```

Reports should call Phase 3.2 and Phase 3.3 outputs readiness or dry-run artifacts unless a later phase defines stronger evidence requirements.

## Proposed Future Implementation

Recommended next implementation phase:

```text
Phase 3.2: Low-Tier Timing Boundary and Metrics Scaffold
```

Phase 3.2 should implement:

```text
timing dataclasses
run manifest schema
environment snapshot helper
timing summary writer
optional timing wrappers around existing trace commands
no benchmark claims
```

Suggested module shape:

```text
src/htfsd/metrics/timing_schema.py
src/htfsd/metrics/environment_snapshot.py
src/htfsd/metrics/timing_summary.py
scripts/run_benchmark_readiness.py
```

Phase 3.2 should prefer wrapping existing trace commands and report writers rather than changing diagnostic behavior.

## Verification

Verification for this design phase:

```text
.venv/bin/pytest -v
forbidden-claim scan
git diff --check
```

Expected status:

```text
tests pass
forbidden-claim scan returns no matches
formatting check returns no whitespace errors
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

## Recommended Next Step

Proceed to:

```text
Phase 3.2: Low-Tier Timing Boundary and Metrics Scaffold
```

Phase 3.2 should add only timing schema and scaffold infrastructure. It should not produce benchmark claims.

## Conclusion

Phase 3.1 defines the measurement boundary before any timing scaffold is implemented. The design keeps load time, generation time, diagnostic overhead, and fallback-aware categories separate.

The next phase can now add a small timing scaffold with a run manifest and descriptive metrics fields while preserving the MVP's diagnostic-only claim boundary.
