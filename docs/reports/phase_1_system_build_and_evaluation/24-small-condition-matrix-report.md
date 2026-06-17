# 24 Small Condition Matrix Report

## Task Title and Date

- Task: Small condition matrix
- Date: 2026-06-04

## Scope

This is a preliminary small-matrix run across the existing smoke paths. It is not a final benchmark, not a production readiness claim, and not a real speedup conclusion.

Conditions run:

- `DFlash-R1`
- `CC-LLM-R2`
- `CC-LLM-R3`
- `LLMLingua-AR-R2`
- `LLMLingua-AR-R3`

Settings:

- `n = 10`
- `max_new_tokens = 32`
- greedy generation from the existing runner configuration
- same fixed prompt cycle across conditions
- existing Transformers backend
- `flash_attn` not installed, so the existing torch SDPA fallback remains in use

## Exact Commands Run

Validation:

- `python3 -m compileall src tests scripts`
- `PYTHONPATH=src .venv/bin/python -m pytest tests/test_compression.py tests/test_smoke_artifact_audit.py -q`
- `PYTHONPATH=src .venv/bin/python scripts/smoke_artifacts.py`

Task-24 matrix:

- `PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --config config.yml --condition DFlash-R1 --n 10 --output results/task24_dflash_r1_n10.jsonl`
- `PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --config config.yml --condition CC-LLM-R2 --n 10 --output results/task24_cc_llm_r2_n10.jsonl`
- `PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --config config.yml --condition CC-LLM-R3 --n 10 --output results/task24_cc_llm_r3_n10.jsonl`
- `PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --config config.yml --condition LLMLingua-AR-R2 --n 10 --output results/task24_llmlingua_ar_r2_n10.jsonl`
- `PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --config config.yml --condition LLMLingua-AR-R3 --n 10 --output results/task24_llmlingua_ar_r3_n10.jsonl`

Task-24 artifact audit:

- `PYTHONPATH=src .venv/bin/python scripts/smoke_artifacts.py results/task24_dflash_r1_n10.jsonl results/task24_cc_llm_r2_n10.jsonl results/task24_cc_llm_r3_n10.jsonl results/task24_llmlingua_ar_r2_n10.jsonl results/task24_llmlingua_ar_r3_n10.jsonl`

## Artifact Table

| Artifact | Condition | Rows | Contract status |
| --- | --- | ---: | --- |
| `results/task24_dflash_r1_n10.jsonl` | `DFlash-R1` | 10 | PASS |
| `results/task24_cc_llm_r2_n10.jsonl` | `CC-LLM-R2` | 10 | PASS |
| `results/task24_cc_llm_r3_n10.jsonl` | `CC-LLM-R3` | 10 | PASS |
| `results/task24_llmlingua_ar_r2_n10.jsonl` | `LLMLingua-AR-R2` | 10 | PASS |
| `results/task24_llmlingua_ar_r3_n10.jsonl` | `LLMLingua-AR-R3` | 10 | PASS |

## Metrics Table

| Condition | Rows | Avg tok/s | Median tok/s | Avg output tokens | Avg input tokens | Avg tau_mean | Avg t_compress_ms | Avg R_actual | Max VRAM allocated | Max VRAM reserved |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| DFlash-R1 | 10 | 19.72 | 16.74 | 11.40 | 23.80 | 2.52 | n/a | n/a | 3.510836124420166 GiB | 3.619140625 GiB |
| CC-LLM-R2 | 10 | 29.28 | 33.41 | 18.00 | 51.80 | 3.86 | 893.89 | 2.20 | 3.510836124420166 GiB | 3.626953125 GiB |
| CC-LLM-R3 | 10 | 29.29 | 32.19 | 18.00 | 43.80 | 3.82 | 820.11 | 3.30 | 3.510836124420166 GiB | 3.625 GiB |
| LLMLingua-AR-R2 | 10 | 15.15 | 16.79 | 18.00 | 51.80 | 0.00 | 845.78 | 2.20 | 2.5024728775024414 GiB | 2.595703125 GiB |
| LLMLingua-AR-R3 | 10 | 15.36 | 17.47 | 18.00 | 43.80 | 0.00 | 841.26 | 3.30 | 2.5024728775024414 GiB | 2.59375 GiB |

## Comparison Notes

DFlash-R1 vs CC-LLM-R2:

- In this small matrix, `CC-LLM-R2` has higher average tok/s than `DFlash-R1` after compression has already happened: 29.28 vs 19.72.
- `CC-LLM-R2` also has higher average `tau_mean`: 3.86 vs 2.52.
- Compression overhead is visible at about 893.89 ms per prompt, so any end-to-end interpretation must include that cost.

DFlash-R1 vs CC-LLM-R3:

- `CC-LLM-R3` is similar to `CC-LLM-R2` on average tok/s in this run: 29.29.
- `CC-LLM-R3` has average compression ratio 3.30 and lower average input tokens than R2, but the small prompt set is too small for a final compression/speed conclusion.

LLMLingua-AR-R2 vs CC-LLM-R2:

- `LLMLingua-AR-R2` is target-only and does not use DFlash acceptance, so `tau_mean` is intentionally 0.00.
- Compared with `CC-LLM-R2`, AR-R2 has lower average tok/s in this run: 15.15 vs 29.28.
- AR-R2 uses less VRAM because it does not load the draft model: about 2.50 GiB max allocated vs 3.51 GiB.

LLMLingua-AR-R3 vs CC-LLM-R3:

- `LLMLingua-AR-R3` also has lower average tok/s than the DFlash-backed `CC-LLM-R3`: 15.36 vs 29.29.
- AR-R3 keeps the lower target-only VRAM profile while using the same compression ratio target as CC-LLM-R3.

Preliminary breakeven-style observation:

- The DFlash-backed CC-LLM paths show higher generation tok/s and higher tau than the no-compression DFlash control on this tiny prompt cycle, but compression costs about 0.82 to 0.89 seconds per prompt.
- Whether compression is worthwhile end-to-end depends on longer contexts, larger output budgets, and dataset-style prompts. This run is useful for plumbing and first-order behavior only.

## Warnings and Anomalies

- No artifact contract failures were found.
- No task-24 artifact contract warnings were found.
- The first prompt in every condition generates only 2 output tokens, so its tok/s is noisy and should not be overinterpreted.
- Output token counts repeat because the fixed 5-prompt smoke set is cycled twice for `n = 10`.
- `flash_attn` remains unavailable, so these numbers reflect the existing torch SDPA fallback.

## Validation Results

- `python3 -m compileall src tests scripts`: PASS
- `PYTHONPATH=src .venv/bin/python -m pytest tests/test_compression.py tests/test_smoke_artifact_audit.py -q`: PASS, 13 tests
- existing artifact audit with default paths: PASS
- task-24 explicit artifact audit: PASS for all 5 task-24 artifacts
- task-24 row count: 10 rows per artifact, 50 rows total

## Limitations

- Preliminary small-matrix only.
- Fixed tiny prompt cycle, not a dataset benchmark.
- Short generation budget, capped at `max_new_tokens = 32`.
- No full condition matrix.
- No long-context augmentation.
- No final benchmark or real speedup claim.
- Existing Transformers backend only; no vLLM, SGLang, Docker, or scale-up work.

## Next Step

Task 25: long-context/dataset augmentation mini-spec or artifact.
