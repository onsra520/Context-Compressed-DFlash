# Rec-T04B - CC-DFlash Audit and Benchmark n=30

Status: PASS_WITH_SHORT_CONTEXT_BYPASS

## Scope

Rec-T04B ran the required n30 matrix over frozen Rec-T02A subsets:

| Dataset | Baseline-AR | DFlash-R1 | CC-DFlash-R2 |
| --- | ---: | ---: | ---: |
| GSM8K n30 | 30 | 30 | 30 |
| QMSum n30 | 30 | 30 | 30 |

Total rows: `180/180`.

Each dataset/condition ran in its own isolated subprocess. Benchmark latency is recorded separately from compression cost; net CC-DFlash interpretation includes compression cost.

## Configuration

- Target model: `models/target/unsloth--Qwen3-4B-bnb-4bit`
- Drafter model: `models/drafter/z-lab--Qwen3-4B-DFlash-b16`
- Compressor model: `models/llmlingua-2-bert-base-multilingual-cased-meetingbank`
- Temperature: `0.0`
- Max new tokens: `8`
- Measurement mode: `benchmark`
- QMSum semantic correctness: `NOT_CLAIMED`

The small generation cap is retained from Rec-T03B for reconstruction-gate comparability. Cap hits are reported rather than hidden.

## Matrix Summary

| Dataset | Condition | Rows | Cap hits | Mean prefill ms | Mean decode ms | Mean generation E2E ms | Mean compression ms | Mean net ms | Global weighted tau |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| GSM8K | Baseline-AR | 30 | 30 | 84.769 | 209.944 | 294.794 | 0.000 | 294.794 | 0.000 |
| GSM8K | DFlash-R1 | 30 | 30 | 87.925 | 377.170 | 466.249 | 0.000 | 466.249 | 2.128 |
| GSM8K | CC-DFlash-R2 | 30 | 30 | 86.951 | 371.158 | 459.188 | 0.009 | 459.197 | 2.128 |
| QMSum | Baseline-AR | 30 | 30 | 634.942 | 212.742 | 847.806 | 0.000 | 847.806 | 0.000 |
| QMSum | DFlash-R1 | 30 | 30 | 638.184 | 589.304 | 1229.275 | 0.000 | 1229.275 | 1.428 |
| QMSum | CC-DFlash-R2 | 30 | 30 | 339.915 | 543.771 | 885.057 | 2534.860 | 3419.917 | 1.367 |

## Findings

### DFlash vs Baseline

Under the small cap, DFlash-R1 did not beat Baseline-AR on either dataset. DFlash counters remained valid and target-verified, so this is classified as workload/cap-limited reconstruction evidence, not a proven runtime defect.

### CC-DFlash vs DFlash

GSM8K:

- Compression bypass count: `30/30`
- Conclusion: short-context compression is not worthwhile; DFlash-R1 or Baseline-AR should be preferred for GSM8K-like inputs.

QMSum:

- Mean full-prompt reduction: `52.86%`
- Prefill improved: DFlash `638.184 ms` to CC-DFlash `339.915 ms`
- Decode improved modestly: DFlash `589.304 ms` to CC-DFlash `543.771 ms`
- Compression cost dominated: `2534.860 ms`
- Net latency worsened: DFlash `1229.275 ms` vs CC-DFlash `3419.917 ms`

The QMSum benefit rule was not met:

```text
compression_total_ms < prefill_saved_ms + decode_saved_ms
```

Compression reduced target prefill but did not produce net E2E benefit in this configuration.

## Prompt and Metric Contracts

Gate checks passed:

- prompt fairness: PASS
- token metric scope: PASS
- DFlash invariants: PASS
- process isolation: PASS
- QMSum semantic correctness: `NOT_CLAIMED`

Artifacts:

- `results/Rec-T04B/runs/*.jsonl`
- `results/Rec-T04B/summary.csv`
- `results/Rec-T04B/runtime_decomposition.csv`
- `results/Rec-T04B/compression_metrics.csv`
- `results/Rec-T04B/dflash_acceptance_comparison.csv`
- `results/Rec-T04B/quality_summary.json`
- `results/Rec-T04B/failure_samples.jsonl`
- `results/Rec-T04B/claim_boundary.json`
- `results/Rec-T04B/gate_decision.json`

## Failure Sample Review

Artifact: `results/Rec-T04B/failure_samples.jsonl`

Rows reviewed: `60`.

All rows hit the small token cap, so the review focuses on cap-hit behavior, proxy deltas, output length, and condition comparison. The artifact records CC-DFlash versus DFlash recall proxy buckets where available and includes cap-hit rows.

## Checks

Commands:

```bash
PYTHONPATH=src TRANSFORMERS_OFFLINE=1 HF_HUB_OFFLINE=1 .venv/bin/python -m pytest -q tests/test_rec_t04b_condition_contract.py tests/test_rec_t04a_compression_contract.py tests/test_rec_t03b_timing_contract.py
PYTHONPATH=src TRANSFORMERS_OFFLINE=1 HF_HUB_OFFLINE=1 .venv/bin/python -m ccdf.benchmark.rec_t04b matrix --output-dir results/Rec-T04B --max-new-tokens 8
PYTHONPATH=src TRANSFORMERS_OFFLINE=1 HF_HUB_OFFLINE=1 .venv/bin/python -m pytest -q
```

Results:

- Focused tests: `8 passed`
- Full available test suite: `41 passed`
- Matrix rows: `180/180`

## Gate Decision

Gate decision: `PASS_WITH_SHORT_CONTEXT_BYPASS`

This result is sufficient to open a closure task after Rec-T04B. It does not claim that CC-DFlash is beneficial on short-context workloads or that QMSum outputs are semantically correct.
