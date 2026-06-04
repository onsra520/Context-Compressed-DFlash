# 23 Smoke Artifact Contract Audit Report

## Task Title and Date

- Task: Smoke artifact contract audit
- Date: 2026-06-04

## Scope

This task audits existing smoke JSONL artifacts only.

In scope:

- `results/dflash_r1_n20.jsonl`
- `results/cc_llm_r2_smoke.jsonl`
- `results/cc_llm_r3_smoke.jsonl`
- `results/llmlingua_ar_r2_smoke.jsonl`
- `results/llmlingua_ar_r3_smoke.jsonl`
- `scripts/audit_smoke_artifacts.py`
- lightweight CPU-only audit tests

Out of scope:

- rerunning GPU smoke benchmarks
- modifying model/runtime behavior
- final benchmark conclusions

## Artifact Audit Table

| Artifact | Condition | Rows | Status |
| --- | --- | ---: | --- |
| `results/dflash_r1_n20.jsonl` | `DFlash-R1` | 20 | PASS |
| `results/cc_llm_r2_smoke.jsonl` | `CC-LLM-R2` | 3 | PASS |
| `results/cc_llm_r3_smoke.jsonl` | `CC-LLM-R3` | 3 | PASS |
| `results/llmlingua_ar_r2_smoke.jsonl` | `LLMLingua-AR-R2` | 3 | PASS |
| `results/llmlingua_ar_r3_smoke.jsonl` | `LLMLingua-AR-R3` | 3 | PASS |

## Contract Fields Checked

Common required fields:

- `prompt_id`
- `input_tokens`
- `output_tokens`
- `generation_time_s`
- `tok_per_s`
- `acceptance_lengths`
- `tau_mean`
- `vram_allocated_gib`
- `vram_reserved_gib`

Common validation rules:

- each non-empty line must be valid JSON
- each row must be a JSON object
- `input_tokens > 0`
- `output_tokens >= 0`
- `generation_time_s >= 0`
- `tok_per_s >= 0`
- `tau_mean >= 0`
- `acceptance_lengths` must be a list

## Condition-Specific Checks

`DFlash-R1`:

- compression fields may be absent
- rows with `output_tokens > 0` must have non-empty `acceptance_lengths`

`CC-LLM-R2` and `CC-LLM-R3`:

- require `t_compress_ms`
- require `R_actual`
- require `N_original`
- require `N_compressed`
- require `keep_rate`
- require `compressor_model`
- require `question_preserved`
- require `R_actual >= 1`
- require `N_original >= N_compressed > 0`
- require `question_preserved == true`

`LLMLingua-AR-R2` and `LLMLingua-AR-R3`:

- require the same compression fields as `CC-LLM`
- require `acceptance_lengths == []`
- require `tau_mean == 0.0`
- if `generation_mode` exists, it must be `autoregressive`
- if `draft_used` exists, it must be `false`

## Audit Utility

Added:

- `scripts/audit_smoke_artifacts.py`

Behavior:

- prints compact `PASS/WARN/FAIL` summary per artifact
- exits non-zero only if any artifact has `FAIL`
- keeps `WARN` non-fatal

## Verification Commands and Results

Required commands:

- `python3 -m compileall src tests scripts`
- `PYTHONPATH=src .venv/bin/python -m pytest tests/test_compression.py -q`
- `PYTHONPATH=src .venv/bin/python scripts/audit_smoke_artifacts.py`

Additional lightweight test run:

- `PYTHONPATH=src .venv/bin/python -m pytest tests/test_smoke_artifact_audit.py -q`

Results:

- `compileall`: PASS
- `tests/test_compression.py`: PASS
- `tests/test_smoke_artifact_audit.py`: PASS
- `scripts/audit_smoke_artifacts.py`: PASS for all 5 artifacts

Compact audit output:

- `PASS results/dflash_r1_n20.jsonl condition=DFlash-R1 rows=20 issues=0`
- `PASS results/cc_llm_r2_smoke.jsonl condition=CC-LLM-R2 rows=3 issues=0`
- `PASS results/cc_llm_r3_smoke.jsonl condition=CC-LLM-R3 rows=3 issues=0`
- `PASS results/llmlingua_ar_r2_smoke.jsonl condition=LLMLingua-AR-R2 rows=3 issues=0`
- `PASS results/llmlingua_ar_r3_smoke.jsonl condition=LLMLingua-AR-R3 rows=3 issues=0`

## Limitations

- This is a schema and contract audit only.
- It does not validate semantic quality of generations.
- It does not rerun smoke benchmarks.
- It does not support final speed or benchmark claims.
- Any speed numbers implied by these artifacts remain smoke-level or preliminary only.

## Next Step

Task 24: small condition matrix with larger `n` and output length.
