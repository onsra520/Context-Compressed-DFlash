# Rec-T03B - Baseline-AR and DFlash-R1 Audit n=10

Status: PASS_WITH_WORKLOAD_LIMITATION

## Scope

Rec-T03B ran the required n=10 audit matrix over the frozen Rec-T02A subsets:

- GSM8K n10 Baseline-AR
- GSM8K n10 DFlash-R1
- QMSum n10 Baseline-AR
- QMSum n10 DFlash-R1

Total rows: `40/40`.

The run used benchmark mode with one isolated subprocess per dataset/condition. Profiling mode was not used for canonical latency.

## Configuration

- Target model: `models/target/unsloth--Qwen3-4B-bnb-4bit`
- Drafter model: `models/drafter/z-lab--Qwen3-4B-DFlash-b16`
- Target revision: `cad0bedfdd862093a12af478cb974ab2addd0e0a`
- Drafter revision: `b74e3a329c4d963783143b1e970d95b002be72bd`
- Tokenizer source: target model
- Temperature: `0.0`
- Max new tokens: `8`
- Measurement mode: `benchmark`

The small token cap was selected for this reconstruction audit to verify runtime correctness, process isolation, timing fields, DFlash counters, and artifact contracts without making quality claims from long generations. Cap hits are reported and not hidden.

## Matrix Completion

| Dataset | Condition | Rows | Success | Cap hits | Mean prefill ms | Mean decode ms | Mean E2E ms | Global weighted tau |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| GSM8K | Baseline-AR | 10 | 10 | 10 | 109.929 | 210.051 | 320.069 | 0.000 |
| GSM8K | DFlash-R1 | 10 | 10 | 10 | 111.095 | 503.311 | 616.767 | 1.525 |
| QMSum | Baseline-AR | 10 | 10 | 10 | 649.316 | 208.114 | 857.556 | 0.000 |
| QMSum | DFlash-R1 | 10 | 10 | 10 | 644.430 | 606.716 | 1254.109 | 1.600 |

Artifacts:

- `results/Rec-T03B/runs/gsm8k_baseline_ar.jsonl`
- `results/Rec-T03B/runs/gsm8k_dflash_r1.jsonl`
- `results/Rec-T03B/runs/qmsum_baseline_ar.jsonl`
- `results/Rec-T03B/runs/qmsum_dflash_r1.jsonl`
- `results/Rec-T03B/summary.csv`
- `results/Rec-T03B/dflash_acceptance_audit.csv`
- `results/Rec-T03B/quality_summary.json`
- `results/Rec-T03B/performance_summary.json`
- `results/Rec-T03B/gate_decision.json`

## DFlash Findings

DFlash-R1 produced valid counter artifacts on every row:

- `verification_calls == len(acceptance_lengths)`
- `accepted_draft_tokens == sum(acceptance_lengths) - verification_calls`
- `rollback_tokens == draft_tokens_proposed - accepted_draft_tokens`

Mean per-row tau and global weighted tau are both reported in the summary artifacts. DFlash did not beat Baseline-AR under this small-cap reconstruction run. The slowdown is classified as workload/cap-limited evidence rather than a proven implementation defect because:

- local target and drafter loads passed in Rec-T03A;
- DFlash generation produced valid target-verified outputs and counters;
- no duplicated prefill or metric invariant failure was observed;
- all rows hit the small `max_new_tokens=8` cap, limiting quality/performance interpretation.

## Quality Boundary

GSM8K quality is cap-limited by design in this audit. Numeric correctness should not be generalized from this run.

QMSum evaluation remains a proxy only. Semantic correctness is `NOT_CLAIMED`.

## Checks

Commands:

```bash
PYTHONPATH=src TRANSFORMERS_OFFLINE=1 HF_HUB_OFFLINE=1 .venv/bin/python -m pytest -q tests/test_rec_t03a_runtime_contract.py tests/test_rec_t03b_timing_contract.py
PYTHONPATH=src TRANSFORMERS_OFFLINE=1 HF_HUB_OFFLINE=1 .venv/bin/python -m ccdf.benchmark.rec_t03b matrix --output-dir results/Rec-T03B --max-new-tokens 8
PYTHONPATH=src TRANSFORMERS_OFFLINE=1 HF_HUB_OFFLINE=1 .venv/bin/python -m pytest -q
```

Results:

- Focused timing/Rec-T03B tests: `10 passed`
- Full available test suite: `35 passed`
- Matrix rows: `40/40`
- Process isolation: PASS

## Gate Decision

Gate decision: `PASS_WITH_WORKLOAD_LIMITATION`

Rec-T04A is allowed to proceed because the runtime contract, metric contract, dataset contract, DFlash invariants, and process-isolated artifacts passed. The limitation is explicit: this n=10 audit proves reconstruction readiness and workload behavior under a small cap; it does not claim DFlash speedup or QMSum semantic correctness.
