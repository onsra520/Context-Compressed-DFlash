# Real Synthetic Probe Implementation Report

Date: 2026-06-04

## Conclusion

**PASS**

Gate 0 is now passed. Dry-run validation passed, and the real local-model probe loaded the target and draft models, validated `H_target`, and completed minimal DFlash generation.

## Files Changed

- `scripts/synthetic_probe.py`
- `tests/test_dflash_core.py`
- `docs/reports/11-real-synthetic-probe-implementation-report.md`

No compression, benchmark matrix, dataset, plotting, CCDF pipeline, DFlash logic, or flash-attn installation work was performed.

## Environment

- GPU: `NVIDIA GeForce RTX 4070 Laptop GPU`
- CUDA available: `True`
- torch: `2.12.0+cu126`
- bitsandbytes: `0.49.2`

## Model Paths Used

- Target: `models/Qwen3-4B`
- Draft: `models/Qwen3-4B-DFlash-b16`
- Tokenizer: `models/Qwen3-4B`

`config.yml` already contained these paths, so no config rewrite was needed.

## Dry-Run Result

Command:

```bash
PYTHONPATH=src .venv/bin/python scripts/synthetic_probe.py --config config.yml --dry-run
```

Result: **DRY-RUN-PASS**

Dry-run checks completed:

- Parsed `config.yml`.
- Printed target, draft, and tokenizer paths.
- Confirmed local model directories exist.
- Confirmed target `config.json`.
- Confirmed target tokenizer files.
- Confirmed target safetensors/index files.
- Confirmed draft `config.json`.
- Confirmed draft `modeling_dflash.py` or `dflash.py`.
- Confirmed draft `model.safetensors`.
- Ran DFlash split raw import guard: `[]`.
- Checked CUDA availability.

## Real Model Execution Result

Command:

```bash
PYTHONPATH=src .venv/bin/python scripts/synthetic_probe.py --config config.yml
```

Result: **PASS**

Final status:

```text
PASS
```

## VRAM Measurements

```text
VRAM before load: allocated=0.00GiB reserved=0.00GiB free=6.89GiB total=8.00GiB
VRAM after target load: allocated=2.49GiB reserved=2.53GiB free=4.34GiB total=8.00GiB
VRAM after draft load: allocated=3.50GiB reserved=3.51GiB free=3.36GiB total=8.00GiB
VRAM after generation: allocated=3.52GiB reserved=3.62GiB free=3.23GiB total=8.00GiB
```

## H_target Validation Result

```text
H_target shape: (1, 19, 2560)
H_target dtype: torch.bfloat16
H_target device: cuda:0
H_target norm: 672.000000
```

Validation status: **PASS**

The hidden state has the expected rank, bfloat16 dtype, CUDA placement, no reported NaN failure, and positive norm.

## Generation Result

```text
Generation output shape: (1, 21)
Generation new tokens: 2
Generation acceptance lengths: [1]
```

Generation status: **PASS**

The probe completed minimal DFlash generation.

## Raw Import Guard Result

Requested raw import guard:

```text
raw imports: []
```

Dry-run internal raw import guard:

```text
Raw import guard: []
```

No `*_raw.py` module was imported or called by the probe.

## Warning Classification

HF transfer env warning:

- Warning: `HF_HUB_ENABLE_HF_TRANSFER` is deprecated.
- Classification: environment cleanup, non-blocking.
- Action: use `HF_XET_HIGH_PERFORMANCE=1` or unset the old variable. No code patch is required for Gate 0.

bitsandbytes FutureWarning:

- Warning: `_check_is_size` will be removed in a future PyTorch release.
- Classification: benign upstream library warning, non-blocking.
- Action: do not patch vendored/library code. Track through normal dependency updates.

flash-attn missing:

- Warning: `flash_attn` is not installed, so execution falls back to `torch.sdpa`.
- Classification: performance warning, non-blocking for Gate 0.
- Action: keep `flash-attn` as a later optimization task. Do not add it to `requirements.txt` yet.

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
7 passed, 2 warnings
```

## Requirements Check

`requirements.txt` already includes:

```text
bitsandbytes>=0.43.0
```

No requirements change was needed. `flash-attn` was intentionally not added.

## Next Step

Proceed to the DFlash-R1 baseline using the current `torch.sdpa` fallback before attempting flash-attn optimization.

The flash-attn path should be treated as a later performance improvement, not a Gate 0 blocker.
