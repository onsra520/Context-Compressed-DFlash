# DFlash-R1 n=20 Baseline Audit Report

## Result

PASS

The artifact is valid and good enough to close the Week-1 baseline path. It should be treated as a smoke-level preliminary baseline, not as a final benchmark result.

## Artifact

- Path: `results/dflash_r1_n20.jsonl`
- Rows: 20
- Condition: `DFlash-R1`
- Backend: `torch.sdpa` fallback because `flash_attn` is not installed

## Schema Validation

PASS

- 20 JSONL rows were parsed successfully.
- Required fields exist in every row.
- Every row has `condition == "DFlash-R1"`.
- No compression or LLMLingua fields are present.
- Model paths are local:
  - target: `models/Qwen3-4B`
  - draft: `models/Qwen3-4B-DFlash-b16`
  - tokenizer: `models/Qwen3-4B`
- Every row has non-empty `acceptance_lengths`.

Required fields checked:

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

## Recomputed Summary Metrics

Computed from `results/dflash_r1_n20.jsonl`, not copied from the previous report.

- average tok/s: 17.38
- median tok/s: 13.52
- min tok/s: 2.91
- max tok/s: 42.02
- average tau_mean: 2.52
- median tau_mean: 2.12
- min tau_mean: 1.00
- max tau_mean: 5.00
- average output_tokens: 11.40
- min output_tokens: 2
- max output_tokens: 32
- max VRAM allocated: 3.510836124420166 GiB
- max VRAM reserved: 3.619140625 GiB

## Abnormal Row Analysis

No unusable rows were found.

- Empty `acceptance_lengths`: none
- `tau_mean == 0`: none
- Missing required fields: none
- Compression fields accidentally present: none

Rows worth tracking:

- Low tok/s:
  - prompt ID 1: 2.91 tok/s
- Very short outputs:
  - prompt IDs 1, 6, 11, 16: 2 output tokens
- Long outputs:
  - prompt IDs 4, 9, 14, 19: 32 output tokens
- Higher generation time:
  - prompt IDs 4, 5, 9, 10, 14, 15, 19, 20

These patterns are explainable from the repeated fixed prompt set and short smoke settings. They do not make the artifact invalid.

## Interpretation

The 17.38 tok/s value should be treated as a smoke-level preliminary baseline. It is useful for Week-1 control tracking and for comparing the next LLMLingua-enabled run under the same script and JSONL schema, but it is not a final benchmark number.

Likely reasons this is below paper-level expectations:

- `flash_attn` is not installed, so attention uses the current `torch.sdpa` fallback.
- The prompt set is tiny and built in.
- Generation length is short, so setup and Python overhead have a large effect.
- The measurement includes script-level smoke overhead.
- This is not a warmed, repeated, full benchmark matrix.

The tau values are healthy for a smoke path: no zero-tau rows, non-empty acceptance lengths throughout, and repeated prompt groups show stable acceptance patterns.

## Week-1 Closeout Decision

PASS for Week-1 baseline closeout.

The artifact is machine-readable, schema-valid, locally reproducible, raw-free, no-compression, and sufficient as the DFlash-R1 control run before adding LLMLingua.

## Verification

- `python3 -m compileall src tests scripts`: PASS
- `PYTHONPATH=src .venv/bin/python scripts/synthetic_probe.py --config config.yml --dry-run`: PASS
- `PYTHONPATH=src .venv/bin/python -m pytest tests/test_dflash_core.py -q`: PASS
- Artifact summary one-liner: PASS

## Next Step

Week-1 closeout report.
