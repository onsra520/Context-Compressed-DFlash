# Task 87 — Controlled n=10 Benchmark Rerun Gate Report

## 1. Objective
Run a controlled `n=10` benchmark gate using the Task 86 rerun manifest. This task validates that the benchmark pipeline can complete cleanly and generates perfectly shaped artifacts before authorizing the full `n=30` (Task 88) rerun. 

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
- `docs/reports/87-controlled-n10-benchmark-rerun-gate-report.md`

## 4. GSM8K n=10 Result
All four conditions executed flawlessly:
- `row_count` was strictly 10 for all conditions.
- No conditions stalled or hit VRAM OOM limits.
- `empty_output_count`: 0 across all conditions.
- `repetition_count`: 0 across all conditions.
- `hit_cap_count`: 0 across all conditions.

## 5. QMSum n=10 Result
All four conditions executed flawlessly:
- `row_count` was strictly 10 for all conditions.
- No conditions stalled or hit VRAM OOM limits.
- `empty_output_count`: 0 across all conditions.
- `repetition_count`: 0 across all conditions.
- `hit_cap_count`: 0 across all conditions.

## 6. Gate Checklist Result
- **Status**: `PASS`
- The `scripts/analyze_task86_rerun_gate.py` successfully completed without errors.
- The `scripts/analyze_task87_n10_gate.py` successfully computed the metric aggregations.

## 7. Failure/Caveat Notes
- None. The gate sequence ran flawlessly.
- Caveat (carried forward from prior tasks): QMSum remains strictly diagnostic and makes no semantic correctness claims. 

## 8. Decision: Allow or Block Task 88 n=30
**Decision**: ALLOW.
Task 87 passed all strict validation checks. Task 88 is authorized to proceed for `n=30` execution.

## 9. Claim Boundary
> [!IMPORTANT]
> **This task makes no universal speedup claims.**
> **This task makes no semantic correctness claims from QMSum.**
> **This task makes no deployment readiness claims.**
> **This task makes no confirmed 8GB support claims.**
> **This task makes no online-compression claims.**
> This task simply executes a controlled validation sequence.
