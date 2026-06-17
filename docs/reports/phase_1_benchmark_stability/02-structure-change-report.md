# Structure Change Report

Date: 2026-06-03

## Folder(s) Created

- `docs/reports/`
- `docs/paper/`
- `src/ccdf/dflash/`
- `src/ccdf/compression/`
- `src/ccdf/pipeline/`
- `src/ccdf/config/`
- `src/ccdf/utils/`
- `scripts/`
- `tests/`
- `data/`
- `data/raw/`
- `data/processed/`
- `results/`
- `results/charts/`
- `notebooks/`

## Files Created

- `config.yml`
- `requirements.txt`
- `setup.sh`
- `docs/reports/01-structure-scan-report.md`
- `docs/reports/02-structure-change-report.md`
- `docs/reports/05-next-actions.md`
- `models/.gitkeep`
- `data/raw/.gitkeep`
- `data/processed/.gitkeep`
- `results/.gitkeep`
- `results/charts/.gitkeep`
- `notebooks/explore.ipynb`
- `src/ccdf/dflash/__init__.py`
- `src/ccdf/dflash/model.py`
- `src/ccdf/dflash/attention.py`
- `src/ccdf/dflash/generate.py`
- `src/ccdf/dflash/loader.py`
- `src/ccdf/dflash/utils.py`
- `src/ccdf/compression/__init__.py`
- `src/ccdf/compression/base.py`
- `src/ccdf/compression/passthrough.py`
- `src/ccdf/compression/llmlingua.py`
- `src/ccdf/compression/gemma.py`
- `src/ccdf/compression/segmentation.py`
- `src/ccdf/pipeline/__init__.py`
- `src/ccdf/pipeline/ccdf_pipeline.py`
- `src/ccdf/pipeline/prompt_builder.py`
- `src/ccdf/config/__init__.py`
- `src/ccdf/config/loader.py`
- `src/ccdf/utils/__init__.py`
- `src/ccdf/utils/timing.py`
- `src/ccdf/utils/tokens.py`
- `src/ccdf/utils/vram.py`
- `src/ccdf/utils/logging.py`
- `src/ccdf/benchmark/__init__.py`
- `src/ccdf/benchmark/conditions.py`
- `src/ccdf/benchmark/datasets.py`
- `src/ccdf/benchmark/metrics.py`
- `src/ccdf/benchmark/runner.py`
- `scripts/synthetic_probe.py`
- `scripts/create_dataset.py`
- `scripts/run_mvp.py`
- `scripts/plot_results.py`
- `tests/test_dflash_core.py`
- `tests/test_compression.py`
- `tests/test_pipeline.py`
- `tests/test_metrics.py`

## Files Left Untouched

- `instruction.md`
- `README.md`
- `pyproject.toml`
- `docs/plans/task.md`
- `docs/researching/CC-DFlash-v3.html`
- `docs/researching/CC-DFlash-v4.html`
- `src/ccdf/model_raw.py`
- `src/ccdf/benchmark/benchmark_raw.py`

## Why These Changes

- The new module tree matches the chốt structure in `instruction.md` and keeps the package name as `ccdf`
- The raw files remain in place as reference material, so no source code was deleted or rewritten aggressively
- The new root config and script placeholders make the project layout usable without introducing new runtime assumptions

## Later Removal

- The empty placeholder `docs/paper/CC-DFlash.docx` was removed during the skeleton review pass because it did not contain source content.

## Move / Rename Status

- No files were moved or renamed in this pass
- The raw reference files stayed in place by design so the module split can be completed later without data loss

## Validation

- `python -m compileall src` passed
- `pytest` passed with 11 tests collected and 11 tests passing
