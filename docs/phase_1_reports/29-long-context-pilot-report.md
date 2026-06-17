# 29 Long-Context Pilot Report

## Task Title and Date

- Task: Run n=6 long-context pilot across DFlash, CC-LLM, and AR paths
- Date: 2026-06-04

## Scope

This is a preliminary long-context pilot using the controlled Task 25 fixture through the Task 28 fixture runner mode. It is not a final benchmark, not a production-readiness claim, and not proof that compression is worthwhile end to end.

Settings:

- `n = 6`
- `prompt_source = fixture`
- fixture: `tests/fixtures/long_context_smoke.jsonl`
- existing `max_new_tokens = 32` runner behavior
- greedy generation
- existing Transformers backend with torch SDPA fallback

## Commands Run

- `PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --config config.yml --condition DFlash-R1 --n 6 --prompt-source fixture --fixture tests/fixtures/long_context_smoke.jsonl --output results/task29_dflash_r1_longctx_n6.jsonl`
- `PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --config config.yml --condition CC-LLM-R2 --n 6 --prompt-source fixture --fixture tests/fixtures/long_context_smoke.jsonl --output results/task29_cc_llm_r2_longctx_n6.jsonl`
- `PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --config config.yml --condition CC-LLM-R3 --n 6 --prompt-source fixture --fixture tests/fixtures/long_context_smoke.jsonl --output results/task29_cc_llm_r3_longctx_n6.jsonl`
- `PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --config config.yml --condition LLMLingua-AR-R2 --n 6 --prompt-source fixture --fixture tests/fixtures/long_context_smoke.jsonl --output results/task29_llmlingua_ar_r2_longctx_n6.jsonl`
- `PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --config config.yml --condition LLMLingua-AR-R3 --n 6 --prompt-source fixture --fixture tests/fixtures/long_context_smoke.jsonl --output results/task29_llmlingua_ar_r3_longctx_n6.jsonl`

## Artifact Table

| Artifact | Condition | Rows | Contract status |
| --- | --- | ---: | --- |
| `results/task29_dflash_r1_longctx_n6.jsonl` | `DFlash-R1` | 6 | PASS |
| `results/task29_cc_llm_r2_longctx_n6.jsonl` | `CC-LLM-R2` | 6 | PASS |
| `results/task29_cc_llm_r3_longctx_n6.jsonl` | `CC-LLM-R3` | 6 | PASS |
| `results/task29_llmlingua_ar_r2_longctx_n6.jsonl` | `LLMLingua-AR-R2` | 6 | PASS |
| `results/task29_llmlingua_ar_r3_longctx_n6.jsonl` | `LLMLingua-AR-R3` | 6 | PASS |

Existing Task 21, 22, and 24 artifacts were not overwritten. Task 29 used new filenames only.

## Metrics Table

| Condition | Rows | Avg tok/s | Median tok/s | Avg input tokens | Avg output tokens | Avg tau_mean | Avg t_compress_ms | Avg R_actual | Avg context words | Avg generation time s | Avg e2e time s | Max VRAM allocated | Max VRAM reserved |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| DFlash-R1 | 6 | 41.21 | 37.06 | 207.17 | 32.00 | 4.76 | n/a | n/a | 134.17 | 0.85 | 0.85 | 3.5108389854431152 GiB | 3.7265625 GiB |
| CC-LLM-R2 | 6 | 35.89 | 29.64 | 120.67 | 32.00 | 3.87 | 873.77 | 2.03 | 134.17 | 0.98 | 1.86 | 3.510838031768799 GiB | 3.666015625 GiB |
| CC-LLM-R3 | 6 | 41.37 | 40.27 | 91.67 | 32.00 | 4.44 | 785.21 | 3.02 | 134.17 | 0.85 | 1.64 | 3.5108370780944824 GiB | 3.650390625 GiB |
| LLMLingua-AR-R2 | 6 | 18.25 | 18.92 | 120.67 | 32.00 | 0.00 | 736.26 | 2.03 | 134.17 | 1.77 | 2.50 | 2.5024752616882324 GiB | 2.61328125 GiB |
| LLMLingua-AR-R3 | 6 | 10.55 | 9.65 | 91.67 | 32.00 | 0.00 | 892.54 | 3.02 | 134.17 | 3.37 | 4.27 | 2.502474308013916 GiB | 2.603515625 GiB |

Approximate e2e time is:

- `generation_time_s` for `DFlash-R1`
- `generation_time_s + t_compress_ms / 1000` for compressed conditions

## Fixture Metadata Validation

Every Task 29 artifact row includes:

- `prompt_source`
- `fixture_id`
- `domain`
- `expected_answer`
- `evidence`
- `approximate_context_words`

Validation confirmed:

- every artifact has 6 JSONL rows
- every row has `prompt_source == "fixture"`
- every condition uses the same six fixture IDs in fixture order
- CC-LLM and AR artifacts include compression fields
- AR artifacts have `acceptance_lengths == []`
- AR artifacts have `tau_mean == 0.0`
- AR artifacts have `generation_mode == "autoregressive"`
- AR artifacts have `draft_used == false`

## Comparison Notes

DFlash-R1 vs CC-LLM-R2/R3:

- `DFlash-R1` average tok/s: 41.21 with average tau 4.76 and no compression overhead.
- `CC-LLM-R2` average tok/s: 35.89 with average tau 3.87 and average compression overhead 873.77 ms.
- `CC-LLM-R3` average tok/s: 41.37 with average tau 4.44 and average compression overhead 785.21 ms.
- In approximate e2e time, `DFlash-R1` remains lower in this pilot because compression overhead is material.

CC-LLM-R2/R3 vs LLMLingua-AR-R2/R3:

- DFlash-backed CC-LLM paths have higher generation-only tok/s than the target-only AR paths in this run.
- AR paths use less VRAM, about 2.50 GiB allocated versus about 3.51 GiB for DFlash-backed paths.
- AR paths have no DFlash acceptance metric, so tau remains intentionally 0.00.

Generation-only vs approximate end-to-end:

- Generation-only numbers are useful for seeing DFlash speculative behavior after prompt preparation.
- Approximate e2e numbers include compression overhead and are more relevant for breakeven.
- In this pilot, compression is not proven beneficial end to end.

## Answer Correctness Note

`expected_answer` is carried as artifact metadata for every fixture row.

Task 29 does not judge generated-answer correctness. It only verifies that the pilot can run, produce metadata-rich artifacts, and preserve the contract needed for future answer checks.

Task 30 should add answer preservation and expected-answer correctness checks.

## Warnings and Anomalies

- The first `DFlash-R1` attempt exposed a summary-only runner bug: fixture metadata existed without compression fields, and `_print_summary` tried to read `t_compress_ms`.
- A regression test was added and the runner summary now ignores fixture metadata unless compression timing fields are present.
- `DFlash-R1` was rerun successfully after the fix, and the accepted artifact is from the passing rerun.
- `LLMLingua-AR-R3` was notably slower than AR-R2 in this pilot; this is an observation only, not a final conclusion.
- `flash_attn` remains unavailable, so all runs use the existing torch SDPA fallback.

## Validation Commands and Results

Commands:

- `python3 -m compileall src tests scripts`
- `PYTHONPATH=src .venv/bin/python -m pytest tests/test_compression.py tests/test_smoke_artifact_audit.py tests/test_long_context_fixture.py tests/test_task24_analysis.py tests/test_run_mvp_fixture_mode.py -q`
- five Task 29 pilot commands listed above
- `PYTHONPATH=src .venv/bin/python scripts/audit_smoke_artifacts.py results/task29_dflash_r1_longctx_n6.jsonl results/task29_cc_llm_r2_longctx_n6.jsonl results/task29_cc_llm_r3_longctx_n6.jsonl results/task29_llmlingua_ar_r2_longctx_n6.jsonl results/task29_llmlingua_ar_r3_longctx_n6.jsonl`
- inline JSONL metadata validation for fixture fields, compression fields, and AR fields

Results:

- `compileall`: PASS
- pytest suite: PASS
- all five Task 29 pilot commands: PASS
- explicit artifact audit: PASS for all five Task 29 artifacts
- fixture metadata validation: PASS

## Limitations

- Preliminary pilot only.
- `n = 6` is too small for final benchmark claims.
- Fixture is synthetic and controlled, not a broad dataset.
- Generated-answer correctness is not evaluated yet.
- Compression is not proven worthwhile.
- No production-readiness conclusion is supported.
- Existing Transformers backend only; no vLLM, SGLang, Docker, or scale-up work.

## Next Step

Task 30: answer preservation and expected-answer correctness checks.
