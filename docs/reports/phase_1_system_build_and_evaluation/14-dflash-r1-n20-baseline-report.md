# DFlash-R1 n=20 Baseline Report

## Result

PASS

## Exact Command

```bash
PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --config config.yml --condition DFlash-R1 --n 20 --output results/_archives/early_smokes/dflash_r1_n20.jsonl
```

## Artifact

- Path: `results/_archives/early_smokes/dflash_r1_n20.jsonl`
- Line count: `20`
- Status: created successfully

## Summary Metrics

- `n`: 20
- average tok/s: 17.38
- average tau_mean: 2.52
- max VRAM allocated: 3.51 GiB
- max VRAM reserved: 3.62 GiB
- final status: PASS

## VRAM Metrics

- VRAM before load: `allocated=0.00GiB reserved=0.00GiB free=6.89GiB total=8.00GiB`
- VRAM after target load: `allocated=2.49GiB reserved=2.53GiB free=4.34GiB total=8.00GiB`
- VRAM after draft load: `allocated=3.50GiB reserved=3.51GiB free=3.36GiB total=8.00GiB`
- max VRAM during run: `allocated=3.51GiB reserved=3.62GiB`

## Backend Warning Status

- `flash_attn` is not installed.
- The run uses the current `torch.sdpa` fallback.
- This is expected for the current baseline and does not block the smoke benchmark.

## Smoke Versus Baseline

This is still a smoke-level baseline run, not a full benchmark matrix. It is repeatable and machine-readable, but it uses the fixed built-in prompt set and short generation settings rather than the full experimental sweep.

## Abnormal Prompt Rows

The run completed successfully, but two prompt patterns were notably longer than the rest:

- prompt IDs 4, 9, 14, 19:
  - output_tokens: 32
  - tau_mean: 5.00
  - acceptance_lengths: `[2, 3, 11, 4, 4, 4, 7]`
- prompt IDs 5, 10, 15, 20:
  - output_tokens: 17
  - tau_mean: 2.12
  - acceptance_lengths: `[1, 1, 4, 2, 3, 2, 1, 3]`

These are not failures; they are the expected repeated prompt groups surfacing different generation lengths.

## Verification

- `python3 -m compileall src tests scripts`: PASS
- `PYTHONPATH=src .venv/bin/python scripts/synthetic_probe.py --config config.yml --dry-run`: PASS
- `PYTHONPATH=src .venv/bin/python -m pytest tests/test_dflash_core.py -q`: PASS
- `PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --config config.yml --condition DFlash-R1 --n 20 --output results/_archives/early_smokes/dflash_r1_n20.jsonl`: PASS
- `test -s results/_archives/early_smokes/dflash_r1_n20.jsonl`: PASS
- `wc -l results/_archives/early_smokes/dflash_r1_n20.jsonl`: 20
- `head -n 3 results/_archives/early_smokes/dflash_r1_n20.jsonl`: PASS

## Next Step

Baseline audit and Week-1 closeout.

The next real expansion should compare this artifact against an LLMLingua-enabled run using the same JSONL schema, so we can measure compression impact without changing the baseline path.
