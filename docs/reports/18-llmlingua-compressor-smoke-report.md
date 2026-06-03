# LLMLingua Compressor Smoke Report

## Result

PASS

## Dependency Status

- `llmlingua` is installed in the active `.venv`
- `requirements.txt` already contains `llmlingua>=0.2.0`

## Commands Run

- `python3 -m compileall src tests scripts`
- `PYTHONPATH=src .venv/bin/python -m pytest tests/test_compression.py -q`
- `PYTHONPATH=src .venv/bin/python scripts/synthetic_probe.py --config config.yml --dry-run`
- `PYTHONPATH=src .venv/bin/python -m pytest tests/test_dflash_core.py -q`
- `git status --short`

## Compressor Wrapper Status

The LLMLingua wrapper is now implemented in [llmlingua.py](/home/quyseggs/CCDF/src/ccdf/compression/llmlingua.py).

- uses LLMLingua-2 mode via `PromptCompressor(..., use_llmlingua2=True)`
- defaults to `cpu`
- accepts `context`, `question`, and `keep_rate`
- returns merged compressed text plus an info dict
- info dict includes:
  - `t_compress_ms`
  - `R_actual`
  - `N_original`
  - `N_compressed`

## Protected-Question Behavior

PASS

- only the context is passed as compressible content
- the original `question` is passed through `question=...` to the LLMLingua API call
- the final merged prompt keeps the original question unchanged
- empty-context behavior returns the untouched question without initializing the compressor

## Sample Compression Result Summary

The unit smoke path uses a tiny synthetic compressor stub so it stays CPU-only and avoids model downloads.

- input context token count: `20`
- compressed token count: `8`
- actual ratio: `2.5`
- merged output shape: `shortened context + original question`
- question preservation: unchanged

## Tests And Results

- `tests/test_compression.py`: `5 passed`
- `tests/test_dflash_core.py`: `7 passed`
- `scripts/synthetic_probe.py --dry-run`: `DRY-RUN-PASS`
- `compileall`: PASS

## Baseline Control Path

Confirmed unchanged.

- No DFlash generation logic was modified.
- No DFlash-R1 baseline artifact was modified.
- The stable no-compression control path remains the reference for later comparison work.

## Next Step

CC-LLM-R2/R3 smoke comparison using the same JSONL schema.
