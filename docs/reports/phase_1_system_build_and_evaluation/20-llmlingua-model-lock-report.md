# LLMLingua Model Lock Report

## Result

PASS

## Locked Model

- locked model name: `microsoft/llmlingua-2-xlm-roberta-large-meetingbank`
- device map: `cpu`
- LLMLingua-2 mode: `true`
- default keep rate: `0.5`

## Reason For Choosing It

This model is now the locked MVP compressor default because it already passed the real CPU smoke path in this environment and produced a reproducible artifact at `results/llmlingua_cpu_smoke.json`. Using the model that has already been proven locally is lower risk than silently switching to a second meetingbank variant before CC-LLM-R2/R3 smoke comparison.

## Config Keys Added Or Verified

Explicit LLMLingua config is now present in `config.yml`:

- `compression.llmlingua.model_name`
- `compression.llmlingua.device_map`
- `compression.llmlingua.use_llmlingua2`
- `compression.llmlingua.default_keep_rate`

## Wrapper Status

The wrapper in [llmlingua.py](/home/quyseggs/CCDF/src/ccdf/compression/llmlingua.py) now supports both:

- explicit constructor arguments
- config-driven construction through `LLMLinguaCompressor.from_config(...)`

The config-driven path is test-covered without triggering real model download or load.

## Real Model Rerun Status

- real LLMLingua model rerun in this task: no
- reason: not necessary for model locking because the real CPU smoke had already passed and the task only required locking the choice and making it reproducible

## Tests Run And Results

- `python3 -m compileall src tests scripts`: PASS
- `PYTHONPATH=src .venv/bin/python -m pytest tests/test_compression.py -q`: `6 passed`
- `PYTHONPATH=src .venv/bin/python scripts/synthetic_probe.py --config config.yml --dry-run`: `DRY-RUN-PASS`
- `PYTHONPATH=src .venv/bin/python -m pytest tests/test_dflash_core.py -q`: `7 passed`
- `grep -n "llmlingua" config.yml src/ccdf/compression/llmlingua.py`: PASS

## DFlash Baseline Control Path

Confirmed unchanged.

- no DFlash generation logic changes
- no DFlash-R1 baseline behavior changes
- `results/dflash_r1_n20.jsonl` remains the control artifact

## Next Step

CC-LLM-R2/R3 smoke comparison using the same JSONL schema.
