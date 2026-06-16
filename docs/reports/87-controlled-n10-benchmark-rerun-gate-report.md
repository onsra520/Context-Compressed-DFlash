# Task 87 — Controlled n=10 Benchmark Rerun Gate Report

## 1. Objective
Run a controlled `n=10` benchmark gate using the Task 86 rerun manifest. This task validates that the benchmark pipeline can complete cleanly and generates complete and correctly shaped artifacts before authorizing the full `n=30` (Task 88) rerun. 

## 2. Rerun Setting
The rerun was executed strictly under the `task86_rerun_gate_manifest.json` parameters:
- **Datasets**: `gsm8k_short`, `qmsum_meeting_qa_long`
- **Conditions**: Baseline-AR, DFlash-R1, LLMLingua-AR-R2, CC-DFlash-R2
- **Parameters**: `n=10`, `seed=42`, `max_new_tokens=512`, `prompt_source=dataset`, `prompt_policy=strict zero-shot`, `keep_rate_percent=50`.

> [!NOTE]
> Task 87/Task 88 use `max_new_tokens=512` as the controlled rerun setting. Task 83 remains the repaired reference under its original setting and should not be treated as an identical-latency comparison against the 512-token rerun.

## 3. Artifact List
**Generated Execution Outputs:**
- `results/task87_gsm8k_short_baseline_ar_n10.jsonl`
- `results/task87_gsm8k_short_dflash_r1_n10.jsonl`
- `results/task87_gsm8k_short_llmlingua_ar_r2_n10.jsonl`
- `results/task87_gsm8k_short_cc_dflash_r2_n10.jsonl`
- `results/task87_qmsum_meeting_qa_long_baseline_ar_n10.jsonl`
- `results/task87_qmsum_meeting_qa_long_dflash_r1_n10.jsonl`
- `results/task87_qmsum_meeting_qa_long_llmlingua_ar_r2_n10.jsonl`
- `results/task87_qmsum_meeting_qa_long_cc_dflash_r2_n10.jsonl`

**Analysis Artifacts:**
- `scripts/analyze_task87_n10_gate.py`
- `results/task87_n10_gate_summary.json`
- `results/task87_n10_gate_table.csv`
- `results/task87_qmsum_dflash_r1_latency_inspection.json`
- `docs/reports/87-controlled-n10-benchmark-rerun-gate-report.md`

## 4. GSM8K n=10 Result
All four conditions completed cleanly with 10/10 rows, 0 empty outputs, 0 repetitions, and 0 hit caps. 
- **Baseline-AR**: 167.3 avg output tokens | 15.01 e2e tok/s | 11.14s e2e latency | 10/10 exact match
- **DFlash-R1**: 161.7 avg output tokens | 47.74 e2e tok/s | 3.38s e2e latency | 10/10 exact match
- **LLMLingua-AR-R2**: 161.3 avg output tokens | 14.54 e2e tok/s | 11.08s e2e latency | 10/10 exact match
- **CC-DFlash-R2**: 164.8 avg output tokens | 39.95 e2e tok/s | 4.12s e2e latency | 10/10 exact match

## 5. QMSum n=10 Result
All four conditions completed cleanly with 10/10 rows, 0 empty outputs, 0 repetitions, and 0 hit caps.
- **Baseline-AR**: 102.9 avg output tokens | 12.26 e2e tok/s | 8.38s e2e latency | 0.33 overlap proxy
- **DFlash-R1**: 102.0 avg output tokens | 5.66 e2e tok/s | 18.00s e2e latency | 0.33 overlap proxy
- **LLMLingua-AR-R2**: 112.6 avg output tokens | 8.40 e2e tok/s | 13.39s e2e latency | 0.29 overlap proxy
- **CC-DFlash-R2**: 114.7 avg output tokens | 9.39 e2e tok/s | 12.20s e2e latency | 0.30 overlap proxy

## 6. Gate Checklist Result
- **Status**: `PASS_WITH_NOTES`
- The `scripts/analyze_task86_rerun_gate.py` successfully completed without errors.
- The `scripts/analyze_task87_n10_gate.py` successfully computed the metric aggregations, but flagged a DFlash-R1 latency anomaly on QMSum.

## 7. Failure/Caveat Notes
- No blocking execution failures were detected. However, QMSum DFlash-R1 showed a latency anomaly and should be inspected before Task88.
- Caveat (carried forward from prior tasks): QMSum remains strictly diagnostic and makes no semantic correctness claims. 

## 8. Decision: Allow or Block Task 88 n=30
**Decision**: ALLOW WITH NOTES.
Task88 is allowed only after checking whether the QMSum DFlash-R1 slowdown is a row-level outlier, runtime anomaly, or expected effect of the 512-token setting. (Inspection confirms it is an outlier-based slowdown from Row 4).

## 9. Claim Boundary
> [!IMPORTANT]
> **This task makes no universal speedup claims.**
> **This task makes no semantic correctness claims from QMSum.**
> **This task makes no deployment readiness claims.**
> **This task makes no confirmed 8GB support claims.**
> **This task makes no online-compression claims.**
> This task simply executes a controlled validation sequence.
