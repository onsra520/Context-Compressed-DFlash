# DFlash-R1 Repeatable Artifact Report

Date: 2026-06-04

## Conclusion

**PASS**

The DFlash-R1 smoke benchmark now writes a repeatable machine-readable artifact at `results/_archives/early_smokes/dflash_r1_smoke.jsonl` while keeping the baseline path fixed and raw-free.

## Exact Command

```bash
PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --config config.yml --condition DFlash-R1 --n 3 --output results/_archives/early_smokes/dflash_r1_smoke.jsonl
```

Final status:

```text
PASS
```

## Artifact Path

```text
results/_archives/early_smokes/dflash_r1_smoke.jsonl
```

Artifact created: **yes**

## Model Paths

- Target: `models/Qwen3-4B`
- Draft: `models/Qwen3-4B-DFlash-b16`
- Tokenizer: `models/Qwen3-4B`

## JSONL Schema

Each row contains:

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

## Summary Metrics

```text
n: 3
average tok/s: 9.57
average tau_mean: 1.83
max VRAM allocated: 3.51GiB
max VRAM reserved: 3.62GiB
final status: PASS
```

## Backend Warning Status

```text
Backend warning: flash_attn not installed; using torch.sdpa fallback.
```

Classification: performance warning, non-blocking for the baseline artifact.

## Per-Prompt Snapshot

The artifact captures three prompt rows. Example rows include:

- prompt 1: `input_tokens=19`, `output_tokens=2`, `acceptance_lengths=[1]`, `tau_mean=1.00`
- prompt 2: `input_tokens=27`, `output_tokens=3`, `acceptance_lengths=[1, 2]`, `tau_mean=1.50`
- prompt 3: `input_tokens=24`, `output_tokens=3`, `acceptance_lengths=[3]`, `tau_mean=3.00`

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

```bash
PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --config config.yml --condition DFlash-R1 --n 3 --output results/_archives/early_smokes/dflash_r1_smoke.jsonl
```

Result: **PASS**

```bash
head -n 3 results/_archives/early_smokes/dflash_r1_smoke.jsonl
```

Result: **PASS**

## Next Step Toward LLMLingua Integration

Use this JSONL artifact as the no-compression control and then add a separate LLMLingua condition that writes the same schema so the two runs can be compared directly.

Before that, keep the prompt set fixed and the DFlash-R1 baseline on the current `torch.sdpa` fallback so the comparison stays repeatable.
