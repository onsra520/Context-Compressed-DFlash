# Task 32: Answer-Quality Scorer Policy Report

Date: 2026-06-04

## Result

PASS for deterministic answer-quality analysis and scorer policy definition.

This report is preliminary only. It analyzes decoded-output containment in the Task 31 artifacts and does not claim semantic correctness, final speedup, final benchmark quality, or production readiness.

## Scope

Task 32 adds a lightweight deterministic analyzer for the Task 31 decoded-output artifacts:

- `scripts/analyze_task31_answer_quality.py`
- `results/task32_answer_quality_summary.json`

The Task 31 artifacts were treated as immutable inputs:

- `results/task31_dflash_r1_longctx_text_n6.jsonl`
- `results/task31_cc_llm_r2_longctx_text_n6.jsonl`
- `results/task31_cc_llm_r3_longctx_text_n6.jsonl`
- `results/task31_llmlingua_ar_r2_longctx_text_n6.jsonl`
- `results/task31_llmlingua_ar_r3_longctx_text_n6.jsonl`

No new generation or GPU benchmark was run for this task.

## Scorer Policy

The scorer is deterministic and transparent:

| Category | Definition |
| --- | --- |
| `EXACT_CONTAINMENT` | `expected_answer` appears exactly in `generated_text`. |
| `NORMALIZED_CONTAINMENT` | Normalized `expected_answer` appears in normalized `generated_text`, but exact containment did not match. |
| `NO_CONTAINMENT` | `generated_text` exists, but `expected_answer` does not appear after normalization. |
| `NOT_EVALUABLE` | `generated_text` is missing or blank. |

Normalization lowercases text, removes punctuation, collapses whitespace, and strips surrounding whitespace, matching the existing deterministic checker policy in `scripts/check_task29_answers.py`.

The summary also reports inclusive normalized containment count and rate. That means exact matches are also counted as normalized matches because exact text remains present after normalization.

## Answer-Quality Table

| Condition | Rows | Generated text present | Exact containment | Normalized containment | Normalized-only | No containment | Not evaluable | Exact rate | Normalized rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| DFlash-R1 | 6 | 6 | 3 | 3 | 0 | 3 | 0 | 0.50 | 0.50 |
| CC-LLM-R2 | 6 | 6 | 2 | 2 | 0 | 4 | 0 | 0.33 | 0.33 |
| CC-LLM-R3 | 6 | 6 | 1 | 1 | 0 | 5 | 0 | 0.17 | 0.17 |
| LLMLingua-AR-R2 | 6 | 6 | 3 | 3 | 0 | 3 | 0 | 0.50 | 0.50 |
| LLMLingua-AR-R3 | 6 | 6 | 1 | 1 | 0 | 5 | 0 | 0.17 | 0.17 |

## Timing and Performance Context

These values are artifact-derived context from Task 31 only. They are not final benchmark claims.

| Condition | Avg generated tokens | Avg output tokens | Avg e2e time s | Avg tok/s | Avg tau | Avg R_actual |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| DFlash-R1 | 32.00 | 32.00 | 0.89 | 39.87 | 4.76 | n/a |
| CC-LLM-R2 | 32.00 | 32.00 | 1.84 | 37.57 | 3.87 | 2.03 |
| CC-LLM-R3 | 32.00 | 32.00 | 1.69 | 41.38 | 4.44 | 3.02 |
| LLMLingua-AR-R2 | 32.00 | 32.00 | 2.58 | 18.01 | 0.00 | 2.03 |
| LLMLingua-AR-R3 | 32.00 | 32.00 | 2.64 | 17.73 | 0.00 | 3.02 |

`avg_e2e_time_s` is computed as `generation_time_s + t_compress_ms / 1000` when compression metadata exists, and as `generation_time_s` otherwise.

## Task 31 vs Task 29 Drift Note

Task 31 artifacts come from a separate decoded-output capture run and may differ from Task 29 artifacts. The current analysis should not attribute drift solely to `--store-generated-text`; that would require a controlled A/B run with identical conditions and repeated measurements.

For this report, Task 31 timing values are used only as context around the answer-quality rows.

## Interpretation

Deterministic containment is useful as a first-pass proxy because it is reproducible, cheap, and avoids an LLM judge.

Low containment does not necessarily mean semantic failure. The model could paraphrase, compute an equivalent form, provide a partial answer, or answer in a format the containment rule does not recognize.

High containment does not prove full answer quality. A generated answer can contain the expected string while also including incorrect reasoning, extra contradictory text, or an answer to the wrong subquestion.

The current evidence is therefore suitable for triage and breakeven-aware filtering, not for final correctness claims.

## Validation Commands

| Command | Result |
| --- | --- |
| `PYTHONPATH=src .venv/bin/python -m pytest tests/test_task31_answer_quality_analysis.py -q` | PASS, 3 passed |
| `PYTHONPATH=src .venv/bin/python scripts/analyze_task31_answer_quality.py` | PASS, wrote `results/task32_answer_quality_summary.json` |
| `python3 -m compileall src tests scripts` | PASS |
| `PYTHONPATH=src .venv/bin/python -m pytest tests/test_compression.py tests/test_smoke_artifact_audit.py tests/test_long_context_fixture.py tests/test_task24_analysis.py tests/test_run_mvp_fixture_mode.py tests/test_task29_answer_check.py -q` | PASS |
| `PYTHONPATH=src .venv/bin/python scripts/check_task29_answers.py results/task31_dflash_r1_longctx_text_n6.jsonl results/task31_cc_llm_r2_longctx_text_n6.jsonl results/task31_cc_llm_r3_longctx_text_n6.jsonl results/task31_llmlingua_ar_r2_longctx_text_n6.jsonl results/task31_llmlingua_ar_r3_longctx_text_n6.jsonl` | PASS |

## Limitations

- n=6 is too small for final quality claims.
- The fixture is controlled and synthetic.
- Containment misses semantically correct paraphrases.
- Containment does not detect contradictory or unsupported generated text.
- No LLM judge or manual adjudication was used.
- No new benchmark run was performed.
- Existing Task 31 artifacts were not edited.

## Next Step

Task 33 should either:

- perform Phase 2 breakeven analysis with correctness included, using this deterministic scorer as a first-pass quality gate, or
- create a small manual review sample if containment remains too weak for breakeven interpretation.
