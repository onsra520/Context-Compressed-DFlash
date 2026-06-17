# Task 70 - QMSum Long-Context Diagnostic Audit

Date: 2026-06-13

## Result

PASS_WITH_NOTES

Task 70 performed a read-only diagnostic audit of existing QMSum-style long-context artifacts. No new benchmark was run, no model/compressor/CUDA path was loaded, and no existing benchmark artifact was modified.

## Scope

Inputs inspected:

- `results/task50_qmsum_long_baseline_ar_n3.jsonl`
- `results/task50_qmsum_long_llmlingua_ar_r2_n3.jsonl`
- `results/task51_qmsum_long_baseline_ar_n10.jsonl`
- `results/task51_qmsum_long_dflash_r1_n10.jsonl`
- `results/task51_qmsum_long_llmlingua_ar_r2_n10.jsonl`
- `results/task51_qmsum_long_cc_dflash_r2_n10.jsonl`
- `results/task51_qmsum_long_dflash_r1_n3.jsonl`
- `results/task51_qmsum_long_cc_dflash_r2_n3.jsonl`

New audit outputs:

- `scripts/phase_1_analysis/analyze_task70_qmsum_diagnostic_audit.py`
- `tests/test_task70_qmsum_diagnostic_audit.py`
- `results/task70_qmsum_diagnostic_summary.json`
- `results/task70_qmsum_diagnostic_table.csv`
- `results/task70_qmsum_failure_samples.jsonl`

## Artifact Inventory

| Artifact | Rows | Condition | max_new_tokens | generated_text |
|---|---:|---|---:|---:|
| `results/task50_qmsum_long_baseline_ar_n3.jsonl` | 3 | Baseline-AR | 32 | 3/3 |
| `results/task50_qmsum_long_llmlingua_ar_r2_n3.jsonl` | 3 | LLMLingua-AR-R2 | 32 | 3/3 |
| `results/task51_qmsum_long_baseline_ar_n10.jsonl` | 10 | Baseline-AR | 32 | 10/10 |
| `results/task51_qmsum_long_dflash_r1_n10.jsonl` | 10 | DFlash-R1 | 32 | 10/10 |
| `results/task51_qmsum_long_llmlingua_ar_r2_n10.jsonl` | 10 | LLMLingua-AR-R2 | 32 | 10/10 |
| `results/task51_qmsum_long_cc_dflash_r2_n10.jsonl` | 10 | CC-DFlash-R2 | 32 | 10/10 |
| `results/task51_qmsum_long_dflash_r1_n3.jsonl` | 3 | DFlash-R1 | 32 | 3/3 |
| `results/task51_qmsum_long_cc_dflash_r2_n3.jsonl` | 3 | CC-DFlash-R2 | 32 | 3/3 |

## Sufficiency Decision

The Task 51 n=10 artifacts are sufficient for a read-only diagnostic because they include all four frozen conditions, generated text, output token counts, `max_new_tokens`, prefill timing, and compression timing where applicable.

They are stale for the current QMSum benchmark policy because every Task 51 row uses `max_new_tokens=32`. The GSM8K work after Task 51 showed that short output caps can cause false quality warnings. QMSum long-answer outputs are also especially sensitive to short caps, and most Task 51 QMSum rows hit the cap.

Decision: a fresh Task 71 QMSum n=30 run is recommended before drawing even directional long-context quality/speed conclusions.

## QMSum Quality Proxy Summary

| Condition | Rows | Avg answer-token overlap | Normalized containment | Hit cap | Empty | Repetition |
|---|---:|---:|---:|---:|---:|---:|
| Baseline-AR | 10 | 0.257850 | 0/10 | 10/10 | 0 | 0 |
| DFlash-R1 | 10 | 0.257850 | 0/10 | 9/10 | 0 | 0 |
| LLMLingua-AR-R2 | 10 | 0.188711 | 0/10 | 10/10 | 0 | 0 |
| CC-DFlash-R2 | 10 | 0.188711 | 0/10 | 10/10 | 0 | 0 |

The normalized containment proxy is weak for QMSum-style long answers and should remain diagnostic only. The overlap scores suggest compressed rows preserved some answer-relevant words, but the 32-token cap makes quality interpretation unreliable.

## Speed and Latency Summary

| Condition | Avg generation s | Avg e2e s | Weighted gen tok/s | Weighted e2e tok/s | Avg T_compress ms | Avg T_prefill ms |
|---|---:|---:|---:|---:|---:|---:|
| Baseline-AR | 2.532 | 2.532 | 12.64 | 12.64 | 0.00 | 700.35 |
| DFlash-R1 | 2.007 | 2.007 | 15.25 | 15.25 | 0.00 | 729.97 |
| LLMLingua-AR-R2 | 2.474 | 7.726 | 12.94 | 4.14 | 5251.99 | 421.87 |
| CC-DFlash-R2 | 1.556 | 6.778 | 20.56 | 4.72 | 5221.31 | 430.75 |

Preliminary diagnostic comparisons:

- DFlash-R1 was about 1.21x faster than Baseline-AR on weighted generation/e2e tok/s.
- CC-DFlash-R2 was about 1.59x faster than LLMLingua-AR-R2 on generation tok/s.
- CC-DFlash-R2 was about 1.14x faster than LLMLingua-AR-R2 on approximate e2e tok/s after CPU compression cost.
- CPU LLMLingua compression remained the dominant overhead in compressed QMSum rows.

These numbers are smoke-level only because the artifacts are n=10 and capped at 32 output tokens.

## GSM8K-Style Failure Assessment

No GSM8K-style arithmetic failure can be inferred from QMSum. QMSum-style meeting QA is long-answer summarization/lookup, not numeric arithmetic. It can audit long-context generation health, truncation, overlap, prefill behavior, and compression overhead, but it cannot validate GSM8K-style mathematical reasoning failures.

The existing QMSum artifacts do not show empty outputs or obvious repetition, but they do show severe output-cap pressure. This is different from the persistent GSM8K mnt384 failures, which involved a mix of remaining truncation and completed wrong numeric answers.

## Recommended Task 71 Plan

Run a fresh QMSum n=30 diagnostic before any larger long-context run:

- Dataset: `qmsum_meeting_qa_long`
- Conditions: Baseline-AR, DFlash-R1, LLMLingua-AR-R2, CC-DFlash-R2
- Use `--resume`
- Use unique `results/task71_*` artifact names
- Store generated text
- Use a larger long-answer output cap than 32, for example `--max-new-tokens 384`, unless Task 71 explicitly recalibrates another cap

Task 71 should still be preliminary. It should not claim semantic correctness without manual review or a semantic judge.

## Limitations

- Existing QMSum artifacts are n=10, not n=30 or n=100.
- Existing QMSum artifacts use `max_new_tokens=32`, which is likely too short for long-answer meeting QA.
- QMSum quality is measured by normalized containment/overlap proxies only.
- No semantic judge or manual QMSum review was run.
- No new benchmark was run in Task 70.

## Validation

Commands run:

- `PYTHONPATH=src .venv/bin/python -m pytest tests/test_task70_qmsum_diagnostic_audit.py -q`
- `PYTHONPATH=src .venv/bin/python scripts/phase_1_analysis/analyze_task70_qmsum_diagnostic_audit.py`

Full repository validation is recorded in the final Task 70 response.
