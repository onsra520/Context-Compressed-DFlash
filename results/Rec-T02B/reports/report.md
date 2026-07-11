# Rec-T02B - Benchmark Contract Reconstruction

Status: PASS

## Scope

Rec-T02B rebuilt the benchmark contract layer without model runtime, compression runtime, old benchmark glue, or notebook evidence. The implementation defines the per-row schema, condition config schema, timing contract, evaluator contract, DFlash metric invariants, process-isolation audit, atomic artifact writer, and aggregation guardrails.

## Implementation

- Added `src/ccdf/benchmark/` for schemas, synthetic execution, aggregation, validation, timing contract, and process-isolation audit.
- Added `src/ccdf/artifacts/writer.py` for atomic JSON/JSONL writes and stale-artifact checks.
- Added deterministic evaluator contracts in `src/ccdf/evaluation/gsm8k.py` and `src/ccdf/evaluation/qmsum.py`.
- Added DFlash metric invariant checks in `src/ccdf/metrics/dflash.py`.
- Added contract tests in `tests/test_rec_t02b_benchmark_contract.py`.

## Required Artifacts

- `results/Rec-T02B/benchmark_schema.json`
- `results/Rec-T02B/metric_contract.json`
- `results/Rec-T02B/timing_contract.json`
- `results/Rec-T02B/evaluator_contract.json`
- `results/Rec-T02B/process_isolation_audit.json`
- `results/Rec-T02B/synthetic_rows.jsonl`
- `results/Rec-T02B/synthetic_summary.json`
- `results/Rec-T02B/logs/`

Extra per-dataset synthetic row artifacts were retained to prove aggregation over manifest/config cohorts:

- `results/Rec-T02B/gsm8k_synthetic_rows.jsonl`
- `results/Rec-T02B/qmsum_synthetic_rows.jsonl`

## Contract Coverage

The row schema covers identity, prompt hashes, output hashes, timing, VRAM, DFlash counters, measurement mode, and evaluator output.

Benchmark mode rejects profiling-only fields:

- `draft_proposal_ms`
- `target_verification_ms`
- `cache_management_ms`
- `synchronization_overhead_ms`

Profiling mode accepts those fields only with `measurement_mode=profiling`.

The artifact reader rejects stale rows when `dataset_manifest_hash` or `resolved_config_hash` does not match the requested aggregation cohort.

## Synthetic Evidence

Command:

```bash
PYTHONPATH=src .venv/bin/python -m ccdf.benchmark --output-dir results/Rec-T02B
```

Result:

```json
{"process_isolation": true, "rows": {"path": "results/Rec-T02B/synthetic_rows.jsonl", "sha256": "b2409a51997abf0c0511642c1d58f38179f5addca2f1698dfd5cf724d4ff4799"}}
```

Synthetic rows:

- GSM8K Baseline-AR: 1 row
- GSM8K DFlash-R1: 1 row
- QMSum Baseline-AR: 1 row
- QMSum DFlash-R1: 1 row

Aggregation checks:

- Baseline rows have `mean_per_row_tau=0.0` and `global_weighted_tau=0.0`.
- DFlash rows have `mean_per_row_tau=4.0` and `global_weighted_tau=4.0`.
- DFlash invariants pass on every synthetic DFlash row.

## Process Isolation

Artifact: `results/Rec-T02B/process_isolation_audit.json`

The audit launched one subprocess per condition:

- `baseline-ar`: PID `84344`
- `dflash-r1`: PID `84345`

Decision: PASS. PIDs were distinct; no process reuse occurred.

## Evaluator Boundary

GSM8K evaluator labels:

- `strict_correct`
- `wrong_numeric`
- `invalid`
- `cap_limited_incomplete`

QMSum evaluator reports lexical proxy values only:

- reference recall
- reference precision
- invalid/cap-hit
- output length

QMSum semantic correctness remains `NOT_CLAIMED`.

## Checks

Commands:

```bash
PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_rec_t02b_benchmark_contract.py
PYTHONPATH=src .venv/bin/python -m ccdf.benchmark --output-dir results/Rec-T02B
PYTHONPATH=src .venv/bin/python -m pytest -q
```

Results:

- Focused Rec-T02B tests: `9 passed`
- Full available test suite: `19 passed`
- Synthetic process isolation: `true`

## Gate Decision

PASS.

Gate evidence:

- Benchmark schema is stable and validated in round-trip tests.
- Timing boundary is described in `timing_contract.json`.
- Process isolation passes.
- DFlash metric invariants pass.
- Evaluators are deterministic.
- Artifact writer is atomic.
- Synthetic summaries are computed from validated run artifacts.
- Stale artifacts are rejected by manifest/config hash checks.
- Benchmark mode rejects per-iteration profiling instrumentation fields.
