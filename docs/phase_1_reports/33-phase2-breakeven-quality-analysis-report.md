# Task 33: Phase 2 Breakeven Quality Analysis Report

Date: 2026-06-04

## Result

PASS for preliminary Phase 2 breakeven analysis with deterministic answer containment included.

This is a planning analysis only. It does not claim final speedup, final correctness, semantic answer quality, or production readiness.

## Scope

This task combines immutable Task 31 timing/performance artifacts with the Task 32 deterministic answer-quality summary. No new generation, GPU benchmark, model loading, or artifact overwrite was performed.

Inputs used:

- `results/task31_dflash_r1_longctx_text_n6.jsonl`
- `results/task31_cc_llm_r2_longctx_text_n6.jsonl`
- `results/task31_cc_llm_r3_longctx_text_n6.jsonl`
- `results/task31_llmlingua_ar_r2_longctx_text_n6.jsonl`
- `results/task31_llmlingua_ar_r3_longctx_text_n6.jsonl`
- `results/task32_answer_quality_summary.json`

Outputs created:

- `scripts/analyze_phase2_breakeven_with_quality.py`
- `results/task33_phase2_breakeven_quality_summary.json`
- `docs/reports/33-phase2-breakeven-quality-analysis-report.md`

## Breakeven Method

The analyzer computes both generation-only and approximate end-to-end context:

- Generation-only speed uses artifact `tok_per_sec`.
- Approximate e2e time uses `generation_time_s + t_compress_ms / 1000` when compression exists.
- Compression overhead is reported separately as average `t_compress_ms`.
- Task 32 normalized containment is used as the deterministic quality gate.
- Quality-gated e2e is the average e2e time over rows with normalized containment.
- Containment per second is `normalized_containment_count / total_e2e_time_s`.

The quality gate is deterministic string containment only. It is useful for triage, but it is not a semantic correctness judge.

## Main Metrics

| Condition | Rows | Avg tok/s | Median tok/s | Avg gen time s | Avg e2e s | Avg tau | Avg compression ms | Avg R_actual | Max VRAM alloc GiB | Max VRAM reserved GiB | Normalized rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| DFlash-R1 | 6 | 39.87 | 36.53 | 0.89 | 0.89 | 4.76 | n/a | n/a | 3.51 | 3.73 | 0.50 |
| CC-LLM-R2 | 6 | 37.57 | 30.15 | 0.94 | 1.84 | 3.87 | 891.10 | 2.03 | 3.51 | 3.67 | 0.33 |
| CC-LLM-R3 | 6 | 41.38 | 39.62 | 0.87 | 1.69 | 4.44 | 826.25 | 3.02 | 3.51 | 3.65 | 0.17 |
| LLMLingua-AR-R2 | 6 | 18.01 | 18.22 | 1.78 | 2.58 | 0.00 | 797.86 | 2.03 | 2.50 | 2.61 | 0.50 |
| LLMLingua-AR-R3 | 6 | 17.73 | 18.16 | 1.82 | 2.64 | 0.00 | 822.23 | 3.02 | 2.50 | 2.60 | 0.17 |

## Quality-Gated Metrics

| Condition | Exact containment | Normalized containment | No containment | Quality-gated avg e2e s | Normalized containment/s |
| --- | ---: | ---: | ---: | ---: | ---: |
| DFlash-R1 | 3/6 | 3/6 | 3/6 | 0.77 | 0.56 |
| CC-LLM-R2 | 2/6 | 2/6 | 4/6 | 1.93 | 0.18 |
| CC-LLM-R3 | 1/6 | 1/6 | 5/6 | 1.58 | 0.10 |
| LLMLingua-AR-R2 | 3/6 | 3/6 | 3/6 | 2.53 | 0.19 |
| LLMLingua-AR-R3 | 1/6 | 1/6 | 5/6 | 2.62 | 0.06 |

## Carry-Forward Policy

Labels are conservative and intended to be easy to revise:

- `KEEP_BASELINE`: required control or strongest current baseline.
- `KEEP_LOW_VRAM_BASELINE`: useful low-VRAM comparison path with competitive containment.
- `WATCHLIST`: plausible path, but not yet beneficial enough to promote.
- `DEPRIORITIZE_FOR_NOW`: weak current evidence; do not expand before targeted follow-up.

| Condition | Label | Reason |
| --- | --- | --- |
| DFlash-R1 | `KEEP_BASELINE` | No-compression DFlash control remains the required baseline artifact. |
| CC-LLM-R2 | `WATCHLIST` | Speculative path has DFlash acceptance data, but current CPU compression overhead prevents an e2e win. |
| CC-LLM-R3 | `WATCHLIST` | Speculative path has DFlash acceptance data, but current CPU compression overhead prevents an e2e win. |
| LLMLingua-AR-R2 | `KEEP_LOW_VRAM_BASELINE` | Matches baseline containment in this fixture while using materially lower VRAM. |
| LLMLingua-AR-R3 | `DEPRIORITIZE_FOR_NOW` | Lower containment than R2/baseline without a stronger low-VRAM advantage. |

## Interpretation

DFlash-R1 is the current strongest baseline in this tiny long-context fixture because it has the best approximate e2e time and the highest containment-per-second value while preserving DFlash acceptance data.

LLMLingua-AR-R2 remains useful as a low-VRAM baseline. It matches DFlash-R1 normalized containment in this fixture and uses materially lower VRAM, but it is slower end-to-end.

CC-LLM-R2 and CC-LLM-R3 are not yet proven beneficial end-to-end under current CPU compression overhead. They remain on the watchlist because they preserve DFlash speculative decoding and have nonzero containment, but they should not be treated as wins.

R3 compression reduces input tokens more aggressively, but in this tiny fixture it has lower containment than R2. That suggests R3 needs targeted review before expansion.

## What This Does Not Prove

- No final speedup conclusion.
- No final answer-quality conclusion.
- No semantic correctness claim.
- No production readiness claim.
- No statement that compression is or is not broadly worthwhile.
- No conclusion about larger datasets or longer output budgets.

## Recommended Next Task

Task 34 should be targeted, not broad:

- either manually review a small sample of no-containment rows to separate true failures from paraphrase/format misses,
- or run a controlled longer-context/larger-output follow-up only for kept conditions: DFlash-R1, LLMLingua-AR-R2, and at most one CC-LLM watchlist condition.

## Validation Commands

| Command | Result |
| --- | --- |
| `PYTHONPATH=src .venv/bin/python -m pytest tests/test_phase2_breakeven_with_quality.py -q` | PASS, 5 passed |
| `PYTHONPATH=src .venv/bin/python scripts/analyze_phase2_breakeven_with_quality.py` | PASS, wrote `results/task33_phase2_breakeven_quality_summary.json` |
| `python3 -m compileall src tests scripts` | PASS |
| `PYTHONPATH=src .venv/bin/python -m pytest tests/test_compression.py tests/test_smoke_artifact_audit.py tests/test_long_context_fixture.py tests/test_task24_analysis.py tests/test_run_mvp_fixture_mode.py tests/test_task29_answer_check.py tests/test_task31_answer_quality_analysis.py -q` | PASS |
| `PYTHONPATH=src .venv/bin/python scripts/check_task29_answers.py results/task31_dflash_r1_longctx_text_n6.jsonl results/task31_cc_llm_r2_longctx_text_n6.jsonl results/task31_cc_llm_r3_longctx_text_n6.jsonl results/task31_llmlingua_ar_r2_longctx_text_n6.jsonl results/task31_llmlingua_ar_r3_longctx_text_n6.jsonl` | PASS |
| `PYTHONPATH=src .venv/bin/python scripts/analyze_task31_answer_quality.py` | PASS |

## Limitations

- n=6 is too small for final benchmark interpretation.
- The fixture is synthetic and controlled.
- Containment is deterministic and misses paraphrases.
- Quality-gated throughput is a planning metric, not a real user-facing quality metric.
- CPU compression overhead dominates the compressed paths in this environment.
- Existing Transformers backend and torch SDPA fallback remain unchanged.
- No LLM judge, human review, or semantic scoring was used.
