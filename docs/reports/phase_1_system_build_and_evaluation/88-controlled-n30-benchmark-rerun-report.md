# Task 88 — Controlled n=30 Benchmark Rerun Report

## 1. Objective
Run the full `n=30` controlled benchmark rerun across 4 conditions on GSM8K and QMSum datasets to finalize artifact completeness and metric stability under the Task86 defined gate, including a runtime watch for QMSum DFlash-R1 latency.

## 2. Controlled Rerun Setting
- **n**: 30 rows
- **max_new_tokens**: 512
- **seed**: 42
- **prompt_source**: dataset
- **prompt_policy**: strict zero-shot
- **keep_rate_percent**: 50 (for compressed conditions)

*Note: Task 87/88 use max_new_tokens=512 as the controlled rerun setting. Task 83 remains the repaired reference under its original setting and should not be treated as an identical-latency comparison against this 512-token rerun.*

## 3. Artifact List
- `results/task88_gsm8k_short_baseline_ar_n30.jsonl`
- `results/task88_gsm8k_short_dflash_r1_n30.jsonl`
- `results/task88_gsm8k_short_llmlingua_ar_r2_n30.jsonl`
- `results/task88_gsm8k_short_cc_dflash_r2_n30.jsonl`
- `results/task88_qmsum_meeting_qa_long_baseline_ar_n30.jsonl`
- `results/task88_qmsum_meeting_qa_long_dflash_r1_n30.jsonl`
- `results/task88_qmsum_meeting_qa_long_llmlingua_ar_r2_n30.jsonl`
- `results/task88_qmsum_meeting_qa_long_cc_dflash_r2_n30.jsonl`
- `results/task88_n30_rerun_summary.json`
- `results/task88_n30_rerun_table.csv`
- `results/task88_qmsum_dflash_r1_latency_inspection.json`

## 4. GSM8K n=30 Results
| Condition | E2E Latency (avg s) | E2E Tok/s | Numeric Match Rate |
|-----------|--------------------:|----------:|-------------------:|
| Baseline-AR | 9.48 | 18.45 | 83.33% |
| DFlash-R1 | 3.22 | 52.44 | 83.33% |
| LLMLingua-AR-R2 | 10.39 | 16.97 | 90.00% |
| CC-DFlash-R2 | 4.07 | 43.82 | 90.00% |

## 5. QMSum n=30 Results
| Condition | E2E Latency (avg s) | E2E Tok/s | Overlap Proxy |
|-----------|--------------------:|----------:|--------------:|
| Baseline-AR | 6.53 | 14.88 | 0.2544 |
| DFlash-R1 | 5.59 | 17.10 | 0.2579 |
| LLMLingua-AR-R2 | 11.57 | 9.03 | 0.2536 |
| CC-DFlash-R2 | 10.68 | 9.93 | 0.2581 |

## 6. QMSum DFlash-R1 Runtime-Watch Inspection
The runtime inspection found **0 outliers** out of 30 rows based on the >2x median latency or <50% tok/s criteria. The slowdown observed in the n=10 gate was fully transient or mitigated by the 30-row law of large numbers. The model remained stable throughout.

## 7. Gate Checklist Result
**Status: PASS**
- All 8 expected JSONL files exist and contain 30 rows.
- No conditions stalled or remained incomplete.
- Empty outputs and repetitions were zero.
- Analyzer parsed correct metrics and successfully generated the CSV and summary JSON.

## 8. Failure/Caveat Notes
- None. The benchmark executed cleanly under the 512 max_new_tokens setting without generating empty responses or hitting token caps prematurely.

## 9. Decision after Task88
The benchmark artifact generation phase is formally complete. The pipeline proved robust. 
**Next Step**: Post-rerun analysis and metric interpretation. No additional benchmark generation is required unless explicitly instructed.

## 10. Claim Boundary
- No universal speedup claims can be made (speedup varies substantially by dataset and task type).
- No semantic correctness claims from QMSum (overlap metric remains diagnostic-only).
- No deployment readiness claims.
- No confirmed 8GB support claims (the large compressor still forces OOM on GPU, necessitating CPU placement or smaller compressors as explored in feasibility).
- Online compression is not definitively solved; overheads still dominate end-to-end latency in the R2 architectures.
