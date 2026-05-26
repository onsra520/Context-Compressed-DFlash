# Phase 3.4 Block-Cycle Benchmark-Readiness Dry Run / No-Claim Report

## Summary

Phase 3.4 adds a benchmark-readiness dry-run route for the Phase 3.3 low-tier block-cycle trace path.

The dry run routes `scripts/run_benchmark_readiness.py` through `trace_kind=low-tier-cycle`, writes scaffold timing artifacts under `logs/benchmark-readiness/`, and records block-cycle trace counts with explicit interpretation guards.

This phase does not benchmark the system. It records descriptive readiness artifacts only.

## Motivation

Phase 3.3 corrected the low-tier path toward a D-Flash-shaped block-cycle trace. Phase 3.4 uses the Phase 3.2 timing scaffold against that block-cycle path so future measurement work starts from the intended cycle structure rather than from the older single-large-draft diagnostic path.

The key boundary remains:

```text
bridge_valid_block_count is structural bridge metadata only.
cycle_fallback_count is fallback event metadata only.
```

Neither field is a runtime advantage, correctness, target-equivalence, or quality signal.

## Dry-Run Scope

The dry run uses:

```text
trace_kind: low-tier-cycle
dry_run: true
prompt_set_id: phase-2-controlled-eligibility-v2
prompt_mode: raw
draft_block_size: 8
max_cycles: 4
repetitions_requested: 1
capture_raw_output: false
```

The runner records one repetition for local verification. The repetition writes a cycle trace artifact and references it from the timing summary.

## Trace Kind

The supported dry-run trace kind is:

```text
low-tier-cycle
```

This trace kind invokes the Phase 3.3 block-cycle trace path and records repetition-level counts:

```text
trace_records
total_cycles
bridge_valid_block_count
bridge_rejected_block_count
cycle_fallback_count
```

The dry-run route preserves the existing scaffold mode. It does not modify the Phase 2.17 MVP reproducibility path, baseline trace path, selector, inspection layer, or diagnostic record selection logic.

## Fresh Dry-Run Command

```bash
.venv/bin/python scripts/run_benchmark_readiness.py \
  --dry-run \
  --trace-kind low-tier-cycle \
  --prompt-set phase-2-controlled-eligibility-v2 \
  --prompt-mode raw \
  --draft-block-size 8 \
  --max-cycles 4 \
  --repetitions 1
```

## Fresh Dry-Run Artifacts

Fresh run id:

```text
20260526T022544Z
```

Artifacts:

```text
logs/benchmark-readiness/20260526T022544Z-run-manifest.json
logs/benchmark-readiness/20260526T022544Z-timing-summary.json
logs/benchmark-readiness/20260526T022544Z-benchmark-readiness-report.md
logs/benchmark-readiness/repetitions/20260526T022544Z-rep-001-low-tier-cycle-trace.json
```

These artifacts are local readiness artifacts under ignored logs. They are not committed as source artifacts.

## Timing Boundary Population

The fresh dry-run summary populated only timing boundaries that were safely measured:

```text
total_wall_time_seconds: 30.181231700999888
generation_time_seconds: null
diagnostic_overhead_seconds: null
model_load_time_seconds: null
drafter_generation_time_seconds: null
verifier_continuation_time_seconds: null
selection_or_diagnostic_time_seconds: null
```

The dry run intentionally does not invent generation-only or diagnostic-overhead values. It also does not mix model-load time into generation-only timing.

## Block-Cycle Category Summary

Fresh repetition summary:

```text
trace_records: 16
total_cycles: 64
bridge_valid_block_count: 64
bridge_rejected_block_count: 0
cycle_fallback_count: 0
```

Category summary fields:

```text
bridge_valid_block: 64
bridge_rejected_block: 0
cycle_fallback: 0
cycle_no_fallback: 64
```

These are block-cycle readiness counts. They are not performance, correctness, or target-equivalence evidence.

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

## Verification

Focused tests:

```text
.venv/bin/pytest tests/test_timing_readiness.py tests/test_low_tier_cycle_trace.py -v
13 passed
```

Fresh dry-run command:

```text
benchmark readiness scaffold: ok
run_id: 20260526T022544Z
trace_kind: low-tier-cycle
dry_run: True
```

Full test suite:

```text
.venv/bin/pytest -v
187 passed
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

## Remaining Issues

Generation-only timing boundaries remain intentionally unpopulated until a later phase adds safe per-boundary instrumentation.

The dry-run path records descriptive timing-readiness artifacts only. It does not compare low-tier cycle timing against a baseline path.

## Conclusion

Phase 3.4 adds a no-claim dry-run route for block-cycle benchmark readiness. It produces local readiness artifacts, preserves the block-cycle interpretation guards, and keeps timing boundaries descriptive.

## Next Step

Proceed to:

```text
Phase 3.5: High-Tier Feasibility and Backend Decision Design
```
