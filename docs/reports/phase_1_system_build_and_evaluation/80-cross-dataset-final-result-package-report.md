# Task 80 — Cross-Dataset Final Result Package

Date: 2026-06-14

Status: PASS_WITH_NOTES

## Scope And No-Run Statement

Task 80 packages existing GSM8K and QMSum evidence into final-report-ready summary artifacts. It does not run benchmarks, load target models, load draft models, load LLMLingua, use CUDA, run QMSum n=100, run GSM8K n=100, run `max_new_tokens=512`, or tune prompts.

Task 79B was already committed before this task:

- `d33888a docs: freeze qmsum reporting decision`

## Dataset Role Split

| Dataset | Frozen role | Quality interpretation |
| --- | --- | --- |
| `gsm8k_short` | Short-context numeric quality benchmark | Numeric exact-match proxy is the strongest available deterministic quality signal in this local setup. |
| `qmsum_meeting_qa_long` | Long-context diagnostic benchmark | Lexical/normalized-text proxy only; not final semantic correctness evidence. |

## Inputs Read

GSM8K:

- `results/task69_gsm8k_short_baseline_ar_n30_mnt384.jsonl`
- `results/task69_gsm8k_short_dflash_r1_n30_mnt384.jsonl`
- `results/task66_gsm8k_short_llmlingua_ar_r2_n30_mnt384_rerun.jsonl`
- `results/task66_gsm8k_short_cc_dflash_r2_n30_mnt384_rerun.jsonl`
- `results/task69_gsm8k_full_matrix_summary.json`

QMSum:

- `docs/reports/79-qmsum-limitation-freeze-report.md`
- `docs/reports/78-qmsum-compressed-prompt-evidence-retention-report.md`
- `docs/reports/77-qmsum-evidence-focused-policy-report.md`
- `docs/reports/75-qmsum-balanced-policy-report.md`
- `docs/reports/71-qmsum-n30-full-matrix-report.md`
- `results/task79_qmsum_reporting_decision.json`
- `results/task77_qmsum_evidence_policy_summary.json`
- `results/task78_qmsum_evidence_retention_summary.json`
- `results/task71_qmsum_n30_full_matrix_summary.json`

## Outputs Created

| Output | Purpose |
| --- | --- |
| `scripts/phase_1_system_build_and_evaluation/analysis/t80_cross_dataset_final_package.py` | Deterministic package builder |
| `tests/test_task80_cross_dataset_final_package.py` | CPU-only package tests |
| `results/task80_cross_dataset_final_summary.json` | Machine-readable cross-dataset summary |
| `results/task80_cross_dataset_final_table.csv` | Compact report/presentation result table |
| `results/task80_cross_dataset_claims_matrix.csv` | Allowed/forbidden claims matrix |
| `results/task80_final_report_key_points.json` | Conservative final-report bullet points |
| `docs/reports/80-cross-dataset-final-result-package-report.md` | Human-readable package report |

## Final GSM8K Table

| Condition | n | Numeric match | Avg e2e latency s | E2E tok/s | Avg `T_compress` ms | Compression ratio | Interpretation |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Baseline-AR | 30 | 25/30 | 9.709116 | 18.007132 | 0.000000 | 0.000000 | Strongest or near-strongest short-context numeric quality; speed is secondary. |
| DFlash-R1 | 30 | 24/30 | 2.989840 | 56.469011 | 0.000000 | 0.000000 | Fastest GSM8K n=30 condition in this local run while preserving comparable quality. |
| LLMLingua-AR-R2 | 30 | 24/30 | 10.557275 | 16.367860 | 833.989219 | 2.666667 | Compression-only attribution baseline; compression overhead dominates short-context e2e latency. |
| CC-DFlash-R2 | 30 | 24/30 | 4.109472 | 42.673769 | 869.043771 | 2.666667 | Matches compressed AR quality and improves e2e latency versus LLMLingua-AR-R2 in n=30. |

GSM8K interpretation:

- Baseline-AR gives the strongest numeric result in this n=30 package: 25/30.
- DFlash-R1 is fastest on GSM8K n=30 and remains comparable in numeric quality: 24/30.
- LLMLingua-AR-R2 does not improve e2e latency over Baseline-AR because compression overhead dominates this short-context dataset.
- CC-DFlash-R2 keeps compressed-path numeric quality comparable to LLMLingua-AR-R2 and improves e2e throughput versus LLMLingua-AR-R2.
- This does not prove universal speedup or universal quality improvement.

## Final QMSum Diagnostic Table

Task 80 carries forward Task 71 QMSum n=30 diagnostic values only. QMSum quality is lexical/normalized-text proxy quality, not semantic correctness.

| Condition | n | Avg overlap proxy | Avg e2e latency s | E2E tok/s | Avg `T_compress` ms | Compression ratio | Interpretation |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Baseline-AR | 30 | 0.232963 | 4.264360 | 14.453126 | 0.000000 | 0.000000 | Diagnostic only; not semantic correctness proof. |
| DFlash-R1 | 30 | 0.233699 | 3.096825 | 19.536136 | 0.000000 | 0.000000 | Diagnostic only; not semantic correctness proof. |
| LLMLingua-AR-R2 | 30 | 0.358644 | 26.378387 | 13.212837 | 5576.036140 | 2.066920 | Diagnostic only; not semantic correctness proof. |
| CC-DFlash-R2 | 30 | 0.357483 | 19.055571 | 18.122434 | 5928.327985 | 2.066920 | Diagnostic only; not semantic correctness proof. |

QMSum interpretation:

- QMSum remains useful for long-context latency, prefill, compression-overhead, compression-ratio, and input-reduction behavior.
- QMSum is not used as final semantic correctness proof.
- Task 73 controlled cap hits but made answers too terse.
- Task 75 recovered some lexical overlap but did not stabilize evidence quality.
- Task 77 preserved the evidence-focused suffix and kept cap hits at zero, but wrong-negative and evidence-targeting failures remained.
- Task 78 did not support broad compressed-evidence deletion as the main explanation in selected audited cases.
- Task 79B froze QMSum as diagnostic evidence only.

## Cross-Dataset Interpretation

The project partially supports the CC-DFlash hypothesis under bounded local evaluation. DFlash improves decoding speed, and CC-DFlash can recover part of that speed on compressed prompts while keeping GSM8K numeric quality comparable to compressed AR. However, LLMLingua compression overhead can dominate e2e latency, and long-context QMSum quality remains diagnostic rather than semantic. Therefore, CC-DFlash should be reported as a conditional system-level tradeoff, not as a universally faster or universally better method.

Vietnamese:

Kết quả hỗ trợ một phần giả thuyết CC-DFlash trong phạm vi đánh giá local có giới hạn. DFlash cải thiện tốc độ decoding, và CC-DFlash có thể giữ lại một phần lợi ích tốc độ đó trên compressed prompts trong khi chất lượng GSM8K tương đương compressed AR. Tuy nhiên, overhead của LLMLingua có thể chi phối latency end-to-end, và chất lượng QMSum long-context chỉ nên được xem là diagnostic chứ không phải semantic correctness. Vì vậy CC-DFlash nên được báo cáo như một tradeoff cấp hệ thống có điều kiện, không phải một phương pháp luôn nhanh hơn hoặc luôn tốt hơn.

## What The Project Can Claim

- GSM8K n=30 shows CC-DFlash-R2 improves e2e latency versus LLMLingua-AR-R2 while matching compressed-path numeric quality.
- GSM8K n=30 shows DFlash-R1 is the fastest condition in this local run.
- QMSum is useful as a long-context diagnostic benchmark.
- Task 78 did not support broad compressed-evidence deletion as the main explanation in selected audited QMSum cases.
- CC-DFlash is useful only under conditions where compression and DFlash gains outweigh compression overhead.

## What The Project Cannot Claim

- Compression always improves e2e latency.
- QMSum proves semantic correctness.
- Task 78 proves compression never deletes evidence.
- CC-DFlash is universally better than Baseline.
- The final system is deployment ready.
- 8 GB deployment is confirmed.
- Compression benefit is proven end-to-end for all settings.

## Engineering Constraint Discussion

The local target model and resource limits affect QMSum evidence grounding. QMSum failures should not be overinterpreted as pure compression deletion because Task 78 found retained/partial evidence and source/reference mismatch signals in selected reconstructed prompts.

The robust final framing is:

- GSM8K supplies deterministic short-context numeric evidence.
- QMSum supplies long-context diagnostic evidence.
- Neither dataset alone proves universal CC-DFlash superiority.

## Next Task Recommendation

Task 81 final report v2 drafting / final report structure packaging.

Task 81 should turn the Task 80 package into final report sections, figures/tables, and claim-safe narrative text. It should not launch another benchmark by default.

## Validation

Task-specific validation:

- `PYTHONPATH=src .venv/bin/python -m pytest tests/test_task80_cross_dataset_final_package.py -q`
- `PYTHONPATH=src .venv/bin/python scripts/phase_1_system_build_and_evaluation/analysis/t80_cross_dataset_final_package.py`
- `python3 -m json.tool results/task80_cross_dataset_final_summary.json >/dev/null`
- `python3 -m json.tool results/task80_final_report_key_points.json >/dev/null`

Full final validation is recorded in the Task 80 completion response.

Understand-Anything refresh was skipped because `/understand` is not available in this environment.
