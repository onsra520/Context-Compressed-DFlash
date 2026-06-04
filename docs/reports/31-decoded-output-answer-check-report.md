# Task 31: Decoded Output Capture and Answer Check Report

Date: 2026-06-04

## Result

PASS for decoded-output capture, Task 31 artifact generation, schema audit, and deterministic expected-answer containment checking.

This is still a preliminary long-context pilot. The answer checks are exact/normalized string containment checks only; they are not final correctness judgments and do not use an LLM judge.

## Scope

Task 31 added opt-in generated text capture to the existing `scripts/run_mvp.py` smoke runner and reran the n=6 long-context fixture pilot across the five existing conditions:

| Condition | Artifact |
| --- | --- |
| DFlash-R1 | `results/task31_dflash_r1_longctx_text_n6.jsonl` |
| CC-LLM-R2 | `results/task31_cc_llm_r2_longctx_text_n6.jsonl` |
| CC-LLM-R3 | `results/task31_cc_llm_r3_longctx_text_n6.jsonl` |
| LLMLingua-AR-R2 | `results/task31_llmlingua_ar_r2_longctx_text_n6.jsonl` |
| LLMLingua-AR-R3 | `results/task31_llmlingua_ar_r3_longctx_text_n6.jsonl` |

No Task 21, 22, 24, or 29 artifacts were overwritten.

## CLI Change

Added `--store-generated-text` to `scripts/run_mvp.py`.

When omitted, JSONL rows keep the previous behavior and do not include decoded text fields. When enabled, rows include:

| Field | Meaning |
| --- | --- |
| `generated_text` | Decoded newly generated tokens only, using `tokenizer.decode(..., skip_special_tokens=True)` |
| `generated_token_count` | Number of decoded generated token ids before special-token skipping |

DFlash rows decode from `dflash_generate(..., return_stats=True).output_ids`. Autoregressive rows decode `output_ids[:, input_len:]`.

## Commands Run

| Purpose | Command | Result |
| --- | --- | --- |
| Compile | `python3 -m compileall src tests scripts` | PASS |
| CPU tests | `PYTHONPATH=src .venv/bin/python -m pytest tests/test_compression.py tests/test_smoke_artifact_audit.py tests/test_long_context_fixture.py tests/test_task24_analysis.py tests/test_run_mvp_fixture_mode.py tests/test_task29_answer_check.py -q` | PASS, 27 passed |
| DFlash-R1 | `PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --config config.yml --condition DFlash-R1 --n 6 --prompt-source fixture --fixture tests/fixtures/long_context_smoke.jsonl --store-generated-text --output results/task31_dflash_r1_longctx_text_n6.jsonl` | PASS |
| CC-LLM-R2 | `PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --config config.yml --condition CC-LLM-R2 --n 6 --prompt-source fixture --fixture tests/fixtures/long_context_smoke.jsonl --store-generated-text --output results/task31_cc_llm_r2_longctx_text_n6.jsonl` | PASS |
| CC-LLM-R3 | `PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --config config.yml --condition CC-LLM-R3 --n 6 --prompt-source fixture --fixture tests/fixtures/long_context_smoke.jsonl --store-generated-text --output results/task31_cc_llm_r3_longctx_text_n6.jsonl` | PASS |
| LLMLingua-AR-R2 | `PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --config config.yml --condition LLMLingua-AR-R2 --n 6 --prompt-source fixture --fixture tests/fixtures/long_context_smoke.jsonl --store-generated-text --output results/task31_llmlingua_ar_r2_longctx_text_n6.jsonl` | PASS |
| LLMLingua-AR-R3 | `PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --config config.yml --condition LLMLingua-AR-R3 --n 6 --prompt-source fixture --fixture tests/fixtures/long_context_smoke.jsonl --store-generated-text --output results/task31_llmlingua_ar_r3_longctx_text_n6.jsonl` | PASS |
| Answer check | `PYTHONPATH=src .venv/bin/python scripts/check_task29_answers.py results/task31_dflash_r1_longctx_text_n6.jsonl results/task31_cc_llm_r2_longctx_text_n6.jsonl results/task31_cc_llm_r3_longctx_text_n6.jsonl results/task31_llmlingua_ar_r2_longctx_text_n6.jsonl results/task31_llmlingua_ar_r3_longctx_text_n6.jsonl` | PASS |
| Artifact audit | `PYTHONPATH=src .venv/bin/python scripts/audit_smoke_artifacts.py results/task31_dflash_r1_longctx_text_n6.jsonl results/task31_cc_llm_r2_longctx_text_n6.jsonl results/task31_cc_llm_r3_longctx_text_n6.jsonl results/task31_llmlingua_ar_r2_longctx_text_n6.jsonl results/task31_llmlingua_ar_r3_longctx_text_n6.jsonl` | PASS |

## Artifact Metrics

| Condition | Rows | Avg tok/s | Median tok/s | Avg input tokens | Avg output tokens | Avg tau | Avg compress ms | Avg R_actual | Max VRAM allocated GiB | Max VRAM reserved GiB |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| DFlash-R1 | 6 | 13.29 | 11.95 | 207.17 | 32.00 | 4.76 | n/a | n/a | 3.5108389854431152 | 3.7265625 |
| CC-LLM-R2 | 6 | 11.40 | 8.99 | 120.67 | 32.00 | 3.87 | 1593.43 | 2.03 | 3.510838031768799 | 3.666015625 |
| CC-LLM-R3 | 6 | 13.37 | 12.54 | 91.67 | 32.00 | 4.44 | 1378.04 | 3.02 | 3.5108370780944824 | 3.650390625 |
| LLMLingua-AR-R2 | 6 | 7.91 | 7.97 | 120.67 | 32.00 | 0.00 | 1321.58 | 2.03 | 2.5024752616882324 | 2.61328125 |
| LLMLingua-AR-R3 | 6 | 7.71 | 7.82 | 91.67 | 32.00 | 0.00 | 1430.47 | 3.02 | 2.502474308013916 | 2.603515625 |

These speed and VRAM numbers are preliminary pilot measurements only.

## Generated Text and Answer Check

All five artifacts include `generated_text` and `generated_token_count` for every row.

| Condition | Rows | Generated text present | Missing generated text | Exact matches | Normalized matches | Issues |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| DFlash-R1 | 6 | 6 | 0 | 3 | 3 | 0 |
| CC-LLM-R2 | 6 | 6 | 0 | 2 | 2 | 0 |
| CC-LLM-R3 | 6 | 6 | 0 | 1 | 1 | 0 |
| LLMLingua-AR-R2 | 6 | 6 | 0 | 3 | 3 | 0 |
| LLMLingua-AR-R3 | 6 | 6 | 0 | 1 | 1 | 0 |

Interpretation:

- The runner now captures generated text successfully.
- The checker can evaluate deterministic expected-answer containment.
- Mixed containment counts show that this is not yet a robust correctness benchmark.
- Task 31 does not prove compression quality, final answer accuracy, or speedup.

## Artifact Contract Status

`scripts/audit_smoke_artifacts.py` returned PASS for all five Task 31 artifacts.

The AR artifacts preserved the expected target-only contract:

- `acceptance_lengths == []`
- `tau_mean == 0.0`
- `generation_mode == "autoregressive"`
- `draft_used == false`

CC-LLM and AR compressed artifacts include:

- `t_compress_ms`
- `R_actual`
- `N_original`
- `N_compressed`
- `keep_rate`
- `compressor_model`
- `question_preserved`

## Tests Added

Added lightweight CPU-only coverage in `tests/test_run_mvp_fixture_mode.py` for generated text capture:

- decode uses only newly generated token ids
- `skip_special_tokens=True` is passed to tokenizer decode
- generated text fields are opt-in
- no generated text metadata is produced when the flag is omitted

## Limitations

- n=6 is too small for final conclusions.
- The long-context fixture is controlled and synthetic.
- Answer checking is deterministic string containment only.
- No semantic judge or task-specific grading is used.
- The current backend remains Transformers with torch SDPA fallback.
- Compression overhead is CPU-bound in this setup.
- No production readiness or final speedup claim is made.

## Next Step

Task 32 should add a small answer-quality analysis layer or scorer policy decision that distinguishes exact containment, normalized containment, and cases needing manual/semantic review, while keeping the existing Task 31 artifacts immutable.
