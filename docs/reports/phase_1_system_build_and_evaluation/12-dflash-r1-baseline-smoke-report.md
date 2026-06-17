# DFlash-R1 Baseline Smoke Report

Date: 2026-06-04

## Conclusion

**PASS**

The DFlash-R1 baseline smoke benchmark ran successfully with no compression, local Qwen target/draft models, and the raw-free split DFlash modules. The run used the current `torch.sdpa` fallback because `flash_attn` is not installed.

## Exact Command

```bash
PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --config config.yml --condition DFlash-R1 --n 3
```

Final status:

```text
PASS
```

## Model Paths

- Target: `models/Qwen3-4B`
- Draft: `models/Qwen3-4B-DFlash-b16`
- Tokenizer: `models/Qwen3-4B`

## Runtime Settings

- Condition: `DFlash-R1`
- Compression: none
- Device: `cuda:0`
- Block size: `16`
- Max new tokens: `32`
- Prompt count: `3`
- Prompt formatting: chat template with `enable_thinking=False`

## Backend Warning Status

```text
Backend warning: flash_attn not installed; using torch.sdpa fallback.
```

Classification: performance warning, non-blocking for DFlash-R1 smoke.

Action: continue baseline smoke work with `torch.sdpa`; treat flash-attn as a later optimization task.

## Per-Prompt Metrics

| prompt_id | input_tokens | output_tokens | generation_time_s | tok/s | acceptance_lengths | tau_mean |
| --- | ---: | ---: | ---: | ---: | --- | ---: |
| 1 | 19 | 2 | 0.7411 | 2.70 | `[1]` | 1.00 |
| 2 | 27 | 3 | 0.3355 | 8.94 | `[1, 2]` | 1.50 |
| 3 | 24 | 3 | 0.2192 | 13.69 | `[3]` | 3.00 |

## Summary Metrics

```text
average tok/s: 8.44
average tau_mean: 1.83
max VRAM allocated: 3.51GiB
max VRAM reserved: 3.62GiB
```

## VRAM Measurements

```text
VRAM before load: allocated=0.00GiB reserved=0.00GiB free=6.89GiB total=8.00GiB
VRAM after target load: allocated=2.49GiB reserved=2.53GiB free=4.34GiB total=8.00GiB
VRAM after draft load: allocated=3.50GiB reserved=3.51GiB free=3.36GiB total=8.00GiB
VRAM after prompt 1: allocated=3.51GiB reserved=3.61GiB free=1.57GiB total=8.00GiB
VRAM after prompt 2: allocated=3.51GiB reserved=3.62GiB free=1.56GiB total=8.00GiB
VRAM after prompt 3: allocated=3.51GiB reserved=3.62GiB free=1.56GiB total=8.00GiB
```

## Verification

```bash
python3 -m compileall src tests scripts
```

Result: **PASS**

```bash
PYTHONPATH=src .venv/bin/python scripts/synthetic_probe.py --config config.yml --dry-run
```

Result: **PASS**, final status `DRY-RUN-PASS`

```bash
PYTHONPATH=src .venv/bin/python -m pytest tests/test_dflash_core.py -q
```

Result: **PASS**

```text
7 passed, 2 warnings in 5.06s
```

```bash
PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --config config.yml --condition DFlash-R1 --n 3
```

Result: **PASS**

## Remaining Blockers Before LLMLingua Integration

- Add a repeatable baseline result artifact format before comparing compression conditions.
- Decide the fixed prompt set or small local fixture for future baseline comparisons.
- Add raw-free guard checks to any future benchmark entry points.
- Keep DFlash-R1 measurements on the current `torch.sdpa` fallback until the baseline is stable.
- Defer flash-attn installation and tuning until after the DFlash-R1 baseline path is repeatable.
- Only then wire LLMLingua as a separate condition, preserving DFlash-R1 as the no-compression control.
