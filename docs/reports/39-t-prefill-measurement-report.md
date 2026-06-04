# Task 39 — T_prefill Measurement

Date: 2026-06-04

## Result

PASS, preliminary.

Task 39 added target-model prefill latency measurement to the smoke runner artifact schema. The measurement is intended for Task 40 breakeven analysis, not for final speedup claims.

## Scope

- Added per-row target prefill timing fields to `scripts/run_mvp.py`.
- Added CPU-safe helper behavior for prefill timing.
- Added lightweight tests for field presence, JSONL schema compatibility, and Baseline-AR compatibility.
- Created a new tiny smoke artifact: `results/task39_t_prefill_smoke.jsonl`.
- Updated `docs/Roadmap.html` to mark Task 39 PASS and set Task 40 as next.
- Updated `docs/CC-DFlash-Overview.html` only to replace stale "T_prefill not measured" wording with a preliminary Task 39 smoke-measurement note.

No DFlash generation logic was changed. No old result artifact was overwritten.

## Artifact Schema Additions

Each newly written smoke JSONL row now includes:

| Field | Meaning |
| --- | --- |
| `t_prefill_ms` | Target forward/prefill elapsed time in milliseconds |
| `t_prefill_mode` | Timing mode, currently `cuda_synchronized`, `cpu_timer`, or `not_measured` |
| `prefill_vram_allocated_gib` | CUDA allocated VRAM after prefill, in GiB, or `null` for CPU timing |
| `prefill_vram_reserved_gib` | CUDA reserved VRAM after prefill, in GiB, or `null` for CPU timing |

Existing fields remain unchanged, including `generation_time_s`, `tok_per_sec`, `vram_allocated_gib`, and `vram_reserved_gib`.

## Measurement Behavior

The runner measures target prefill after prompt formatting and before generation:

- If CUDA is available for the configured device, synchronize CUDA before timing.
- Run target forward with `input_ids`, an all-ones `attention_mask`, and `use_cache=True`.
- Synchronize CUDA after timing.
- Store elapsed milliseconds plus CUDA allocated/reserved VRAM.
- If CUDA is unavailable, run the same helper with CPU timing mode and emit `null` VRAM fields rather than crashing from the measurement helper.

The current smoke still uses the Transformers backend and keeps `enable_thinking=False`.

## Smoke Command

```bash
PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --config config.yml --condition Baseline-AR --n 1 --output results/task39_t_prefill_smoke.jsonl
```

## Smoke Result

| Metric | Value |
| --- | ---: |
| Rows | 1 |
| Condition | Baseline-AR |
| `t_prefill_ms` | 504.99 |
| `t_prefill_mode` | cuda_synchronized |
| `prefill_vram_allocated_gib` | 2.502471446990967 |
| `prefill_vram_reserved_gib` | 2.583984375 |
| `vram_allocated_gib` | 2.502472400665283 |
| `vram_reserved_gib` | 2.583984375 |
| `tok_per_sec` | 5.72 |
| `output_tokens` | 2 |

Baseline-AR remained target-only:

- `draft_path`: `null`
- `draft_used`: `false`
- `generation_mode`: `autoregressive`
- `compression`: `none`
- `acceptance_lengths`: `[]`
- `tau_mean`: `0.0`

The smoke run printed the existing backend warning: `flash_attn not installed; using torch.sdpa fallback.`

## Tests

Added or updated lightweight CPU-safe tests in `tests/test_run_mvp_fixture_mode.py`:

- prefill helper emits valid CPU timing metadata without CUDA
- JSONL rows include the new prefill fields
- Baseline-AR remains target-only and compatible with the new schema

## Limitations

- This is a tiny n=1 smoke artifact.
- The prefill measurement is a practical target-forward timing inside the current runner, not a final benchmark-grade latency study.
- Generation still performs its own internal prefill path; Task 40 should interpret `t_prefill_ms` as an observed standalone prefill probe for breakeven modeling.
- No final speedup, correctness, deploy readiness, confirmed 8 GB deployment, or proven end-to-end compression benefit is claimed.

## Validation

- `python3 -m compileall scripts tests src 2>&1 | tail -20`: PASS
- `PYTHONPATH=src .venv/bin/python -m pytest tests/test_run_mvp_fixture_mode.py -q`: PASS, 7 passed
- `PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --config config.yml --condition Baseline-AR --n 1 --output results/task39_t_prefill_smoke.jsonl`: PASS
- Artifact inspection confirmed `t_prefill_ms`, `t_prefill_mode`, prefill VRAM fields, and Baseline-AR target-only fields.

## Next Step

Task 40: use actual `T_prefill` and `T_compress` values to produce a preliminary breakeven curve v1. Keep the result preliminary and do not treat it as a final benchmark conclusion.
