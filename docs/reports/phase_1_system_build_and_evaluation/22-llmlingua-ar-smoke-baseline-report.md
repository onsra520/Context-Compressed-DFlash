# 22 LLMLingua-AR Smoke Baseline Report

## Result

PASS for LLMLingua-AR smoke baseline.

This is a target-only autoregressive baseline with LLMLingua compression. It is a smoke comparison only, not a final benchmark claim.

## Commands Run

- `PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --config config.yml --condition LLMLingua-AR-R2 --n 3 --output results/_archives/early_smokes/llmlingua_ar_r2_smoke.jsonl`
- `PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --config config.yml --condition LLMLingua-AR-R3 --n 3 --output results/_archives/early_smokes/llmlingua_ar_r3_smoke.jsonl`

## Artifact Paths

- `results/_archives/early_smokes/llmlingua_ar_r2_smoke.jsonl`
- `results/_archives/early_smokes/llmlingua_ar_r3_smoke.jsonl`

Both artifacts were created and contain 3 JSONL rows.

## Schema Status

The AR artifacts reuse the DFlash-R1 JSONL fields where applicable:

- `timestamp`
- `condition`
- `prompt_id`
- `prompt_hash`
- `input_tokens`
- `output_tokens`
- `generation_time_s`
- `tok_per_sec`
- `acceptance_lengths`
- `tau_mean`
- `max_new_tokens`
- `block_size`
- `device`
- `target_path`
- `draft_path`
- `tokenizer_path`
- `backend_warning`
- `vram_allocated_gib`
- `vram_reserved_gib`

Compression fields added for LLMLingua:

- `t_compress_ms`
- `R_actual`
- `N_original`
- `N_compressed`
- `keep_rate`
- `compressor_model`
- `question_preserved`

AR-specific fields:

- `generation_mode: autoregressive`
- `draft_used: false`

For LLMLingua-AR, DFlash acceptance metrics are not applicable. Rows intentionally store `acceptance_lengths: []` and `tau_mean: 0.0`.

## Compressor Model

Locked compressor model:

- `microsoft/llmlingua-2-xlm-roberta-large-meetingbank`

Device:

- `cpu`

## Draft Model Not Used

The AR branch loaded the tokenizer and target model only, then printed:

- `Draft model: not loaded for autoregressive LLMLingua baseline.`

Every AR artifact row includes:

- `generation_mode: autoregressive`
- `draft_used: false`

The DFlash generation function is not used for the LLMLingua-AR conditions.

## Per-Condition Summary

| Condition | Rows | keep_rate | Avg tok/s | Avg t_compress_ms | Avg R_actual | Max VRAM allocated | Max VRAM reserved | Question preserved |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| LLMLingua-AR-R2 | 3 | 0.50 | 11.86 | 886.45 | 2.20 | 2.5024728775024414 GiB | 2.591796875 GiB | yes |
| LLMLingua-AR-R3 | 3 | 0.33 | 11.23 | 916.01 | 3.30 | 2.502472400665283 GiB | 2.591796875 GiB | yes |

Output tokens for both AR smoke runs:

- `[2, 11, 13]`

The first prompt has low tok/s because it generated only 2 tokens; this is expected for the tiny fixed smoke prompt and is not treated as a benchmark anomaly.

## Smoke-Only Comparison

| Condition | Artifact | Rows | Avg tok/s | Avg tau_mean | Max VRAM allocated | Notes |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| DFlash-R1 | `results/_archives/early_smokes/dflash_r1_n20.jsonl` | 20 | 17.38 | 2.52 | 3.510836124420166 GiB | no compression control, smoke-level preliminary baseline |
| CC-LLM-R2 | `results/_archives/early_smokes/cc_llm_r2_smoke.jsonl` | 3 | 27.70 | 4.33 | 3.510836124420166 GiB | LLMLingua + DFlash, smoke only |
| CC-LLM-R3 | `results/_archives/early_smokes/cc_llm_r3_smoke.jsonl` | 3 | 23.19 | 3.72 | 3.510836124420166 GiB | LLMLingua + DFlash, smoke only |
| LLMLingua-AR-R2 | `results/_archives/early_smokes/llmlingua_ar_r2_smoke.jsonl` | 3 | 11.86 | n/a | 2.5024728775024414 GiB | LLMLingua + target-only AR, smoke only |
| LLMLingua-AR-R3 | `results/_archives/early_smokes/llmlingua_ar_r3_smoke.jsonl` | 3 | 11.23 | n/a | 2.502472400665283 GiB | LLMLingua + target-only AR, smoke only |

These numbers are not directly comparable as final benchmark results because the prompt count is tiny, generation length is short, and `flash_attn` is not installed. They are sufficient to prove the LLMLingua-AR path runs and emits comparable smoke artifacts.

## Failures Or Abnormal Rows

No failed rows were observed.

Validation confirmed:

- 3 rows in each AR artifact.
- Every row has the requested condition.
- Every row has `question_preserved: true`.
- Every row has `R_actual >= 1.0`.
- Every row has `generation_mode: autoregressive`.
- Every row has `draft_used: false`.

Low tok/s on the first row in each condition is explained by very short output length, not by a runtime failure.

## DFlash-R1 Baseline Status

The DFlash-R1 baseline behavior and artifact were not changed. Existing control remains:

- `results/_archives/early_smokes/dflash_r1_n20.jsonl`

## Verification

- `python3 -m compileall src tests scripts`: PASS
- `PYTHONPATH=src .venv/bin/python -m pytest tests/test_compression.py -q`: PASS, 9 tests
- `PYTHONPATH=src .venv/bin/python scripts/synthetic_probe.py --config config.yml --dry-run`: PASS, `DRY-RUN-PASS`
- `PYTHONPATH=src .venv/bin/python -m pytest tests/test_dflash_core.py -q`: PASS, 7 tests
- `wc -l results/_archives/early_smokes/llmlingua_ar_r2_smoke.jsonl results/_archives/early_smokes/llmlingua_ar_r3_smoke.jsonl`: PASS, 3 rows each
- JSONL validation for condition, question preservation, compression ratio, and `draft_used`: PASS

## Next Step

Next step: audit all smoke artifacts together, then run a small condition matrix only after the smoke artifact contracts are accepted.
