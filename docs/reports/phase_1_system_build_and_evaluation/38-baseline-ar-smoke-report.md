# Task 38: Baseline-AR Smoke Report

Date: 2026-06-04

## Result

PASS, preliminary.

## Command

```bash
PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --config config.yml --condition Baseline-AR --n 3 --output results/_archives/early_smokes/baseline_ar_smoke.jsonl
```

## Artifact

Artifact path:

- `results/_archives/early_smokes/baseline_ar_smoke.jsonl`

Row count: 3

## Runtime Summary

- Average tok/s: 11.51
- Average output tokens: 2.67
- Average tau_mean: 0.00
- Max VRAM allocated: 2.50 GiB
- Max VRAM reserved: 2.59 GiB
- Backend warning: `flash_attn` not installed; torch SDPA fallback used.

These are smoke-only measurements and are not final speedup or deployment claims.

## Artifact Audit Summary

- Conditions: `Baseline-AR`
- `compression`: `none`
- `keep_rate`: `1.0`
- `generation_mode`: `autoregressive`
- `draft_used`: `false`
- `draft_path`: `null`
- `acceptance_lengths`: `[]`
- `tau_mean`: `0.0`
- `target_path`: `models/Qwen3-4B`
- `tokenizer_path`: `models/Qwen3-4B`

The artifact includes output token, generation time, and tok/s fields for each row.

## Baseline-AR Behavior

Baseline-AR used no compression.

Baseline-AR used no DFlash speculative decoding. Its rows have empty `acceptance_lengths` and `tau_mean == 0.0`, so DFlash acceptance metrics are not used.

Baseline-AR did not require or load the draft model. The smoke log printed:

```text
Draft model path: not used for autoregressive baseline
Draft model: not loaded for autoregressive baseline.
```

## Limitations

- Smoke only.
- Tiny n=3.
- Not final speedup.
- Not final correctness.
- No full normalization yet.
- No final deployment or 8 GB fit claim.

## Next Step

Task 39 should measure `T_prefill` so later breakeven analysis can separate prefill cost, compression overhead, and generation throughput.
