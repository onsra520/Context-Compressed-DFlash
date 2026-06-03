# Next Actions

Date: 2026-06-03

## What Still Needs Real Implementation

- Copy the upstream DFlash logic into `src/ccdf/dflash/model.py`, `src/ccdf/dflash/attention.py`, `src/ccdf/dflash/generate.py`, and `src/ccdf/dflash/loader.py` when the reference code is ready to be split for real
- Flesh out `src/ccdf/compression/llmlingua.py` and `src/ccdf/compression/gemma.py` only after the MVP path is validated
- Expand `src/ccdf/benchmark/runner.py` once the benchmark protocol is finalized
- Replace placeholder script bodies in `scripts/*.py` with thin calls into `src/ccdf/`

## Completed In This Pass

- Repo structure now matches the requested module layout
- `src/ccdf/__init__.py` exports a lightweight public API and does not load model code at import time
- `python -m compileall src` passed
- `pytest` passed with 11 tests
- Skeleton import/config check passed only. Real Gate 0 has NOT been run.

## Gate 0 Synthetic Probe

- Run the probe script from the project root after environment setup: `python scripts/synthetic_probe.py --config config.yml`
- The probe should only validate that configuration loading and package imports work; it should not download models or run the benchmark
- If the runtime is not ready, capture the failure in `docs/reports/` rather than forcing a model download

## Recommended Checks Next

1. Add upstream DFlash code into `src/ccdf/dflash/` when you are ready to replace the placeholders
2. Wire `scripts/run_mvp.py` to the final benchmark runner after the core split is copied in
3. Extend `src/ccdf/benchmark/runner.py` once the benchmark protocol is frozen

## Reference Code To Clone Later

- `src/ccdf/model_raw.py` is still the local reference for DFlash core logic
- `src/ccdf/benchmark/benchmark_raw.py` is still the local reference for benchmark behavior
- If upstream parity is required, the next copy step should compare against `z-lab/dflash` before replacing the reference stubs