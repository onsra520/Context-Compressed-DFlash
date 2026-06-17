# 30 Answer Preservation and Correctness Check Report

## Task Title and Date

- Task: Answer preservation and expected-answer correctness checks
- Date: 2026-06-04

## Scope

This task adds a lightweight deterministic checker for Task 29 long-context pilot artifacts. It is not an LLM judge, not a semantic correctness evaluator, and not a final quality benchmark.

The checker validates fixture metadata and compression/AR contracts. It can also evaluate exact and normalized expected-answer containment when a future artifact includes a generated text field.

## Input Artifacts

- `results/task29_dflash_r1_longctx_n6.jsonl`
- `results/task29_cc_llm_r2_longctx_n6.jsonl`
- `results/task29_cc_llm_r3_longctx_n6.jsonl`
- `results/task29_llmlingua_ar_r2_longctx_n6.jsonl`
- `results/task29_llmlingua_ar_r3_longctx_n6.jsonl`
- `tests/fixtures/long_context_smoke.jsonl`

## Checker Behavior

Added:

- `scripts/check_task29_answers.py`

The checker:

- reads explicit artifact paths or defaults to the five Task 29 artifacts
- parses JSONL rows
- validates fixture metadata fields
- validates `prompt_source == "fixture"`
- validates non-empty `expected_answer` and `evidence`
- validates `expected_answer` appears in fixture evidence or fixture context
- validates `question_preserved == true` when present
- validates AR rows have `acceptance_lengths == []`
- validates AR rows have `tau_mean == 0.0`
- validates AR rows have `generation_mode == "autoregressive"`
- validates AR rows have `draft_used == false`
- checks generated output fields when present
- reports missing generated output as WARN, not FAIL

Generated text field names recognized:

- `generated_text`
- `output_text`
- `decoded_text`

Normalization is deterministic:

- lowercase
- trim whitespace
- collapse repeated spaces
- strip simple punctuation

## Generated Text Availability

Task 29 artifacts do not contain generated text fields.

Observed generated text fields:

| Artifact | Generated text field present |
| --- | --- |
| `results/task29_dflash_r1_longctx_n6.jsonl` | no |
| `results/task29_cc_llm_r2_longctx_n6.jsonl` | no |
| `results/task29_cc_llm_r3_longctx_n6.jsonl` | no |
| `results/task29_llmlingua_ar_r2_longctx_n6.jsonl` | no |
| `results/task29_llmlingua_ar_r3_longctx_n6.jsonl` | no |

## Answer Correctness Result

Generated-answer correctness cannot yet be evaluated from the current Task 29 artifacts because decoded generated text is not stored.

Checker output summary:

| Condition | Rows | Generated text present | Missing generated text | Exact matches | Normalized matches | Status |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| DFlash-R1 | 6 | 0 | 6 | 0 | 0 | WARN |
| CC-LLM-R2 | 6 | 0 | 6 | 0 | 0 | WARN |
| CC-LLM-R3 | 6 | 0 | 6 | 0 | 0 | WARN |
| LLMLingua-AR-R2 | 6 | 0 | 6 | 0 | 0 | WARN |
| LLMLingua-AR-R3 | 6 | 0 | 6 | 0 | 0 | WARN |

The WARN status is expected and non-fatal for Task 30. It means correctness is not evaluable from the artifact, not that generated answers are incorrect.

## Metadata Preservation Result

PASS

Every Task 29 row includes:

- `prompt_source`
- `fixture_id`
- `domain`
- `expected_answer`
- `evidence`
- `approximate_context_words`

Every row has:

- `prompt_source == "fixture"`
- non-empty `expected_answer`
- non-empty `evidence`
- `expected_answer` recoverable from fixture evidence or fixture context

## Compression Question-Preserved Result

PASS for rows where `question_preserved` is present.

Compressed artifacts include `question_preserved`, and the checker found no `question_preserved == false` failures in Task 29 artifacts.

## AR Contract Result

PASS

For `LLMLingua-AR-R2` and `LLMLingua-AR-R3`, the checker validates:

- `acceptance_lengths == []`
- `tau_mean == 0.0`
- `generation_mode == "autoregressive"`
- `draft_used == false`

No AR contract failures were found.

## Validation Commands and Results

Commands:

- `python3 -m compileall src tests scripts`
- `PYTHONPATH=src .venv/bin/python -m pytest tests/test_compression.py tests/test_smoke_artifact_audit.py tests/test_long_context_fixture.py tests/test_task24_analysis.py tests/test_run_mvp_fixture_mode.py -q`
- `PYTHONPATH=src .venv/bin/python -m pytest tests/test_task29_answer_check.py -q`
- `PYTHONPATH=src .venv/bin/python scripts/check_task29_answers.py`

Results:

- `compileall`: PASS
- existing lightweight pytest suite: PASS
- Task 30 checker tests: PASS
- `scripts/check_task29_answers.py`: WARN only for missing generated text; no FAIL

## Limitations

- Current artifacts do not store decoded generated text.
- Answer correctness cannot be evaluated until generated text is captured.
- Matching is deterministic containment only, not semantic grading.
- No LLM judge is used.
- No new benchmark was run.
- No Task 29 artifacts were modified.
- No final correctness, speedup, or production-readiness claim is supported.

## Next Step

Task 31 should add decoded output capture or rerun a minimal pilot with decoded output, then repeat this deterministic checker with generated text available.
