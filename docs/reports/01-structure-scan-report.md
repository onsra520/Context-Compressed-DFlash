# Structure Scan Report

Date: 2026-06-03

## Current Repo Tree

```text
CCDF/
├── README.md
├── instruction.md
├── pyproject.toml
├── docs/
│   ├── plans/
│   │   └── task.md
│   └── researching/
│       ├── CC-DFlash-v3.html
│       └── CC-DFlash-v4.html
└── src/
    └── ccdf/
        ├── __init__.py
        ├── benchmark/
        │   ├── __init__.py
        │   └── benchmark_raw.py
        └── model_raw.py
```

## Files Already Present

- Root: `instruction.md`, `pyproject.toml`, `README.md`
- Docs: `docs/plans/task.md`, `docs/researching/CC-DFlash-v3.html`, `docs/researching/CC-DFlash-v4.html`
- Package: `src/ccdf/__init__.py`, `src/ccdf/model_raw.py`, `src/ccdf/benchmark/__init__.py`, `src/ccdf/benchmark/benchmark_raw.py`

## Mismatches With Target Structure

- Missing root files: `config.yml`, `requirements.txt`, `setup.sh`
- Missing docs folders/files: `docs/reports/`, `docs/paper/`, `docs/paper/CC-DFlash.docx`
- Missing top-level folders: `scripts/`, `tests/`, `data/`, `results/`, `notebooks/`
- Missing package modules under `src/ccdf/`: `dflash/`, `compression/`, `pipeline/`, `config/`, `utils/`
- Current package exports in `src/ccdf/__init__.py` still point at `model_raw.py` and a non-existent `benchmark` module path
- `src/ccdf/benchmark/__init__.py` is empty, so the benchmark package has no public surface yet

## Role Overlap / Risk Areas

- `src/ccdf/model_raw.py` overlaps with the planned `src/ccdf/dflash/` split and should be treated as reference source until the split is complete
- `src/ccdf/benchmark/benchmark_raw.py` overlaps with the planned `src/ccdf/benchmark/` package and should remain reference-only for now
- `README.md` is empty, so it currently does not document the new package/module layout
- There are no `config/`, `compression/`, or `pipeline/` modules yet, so import paths for the planned MVP will fail until skeletons exist

## Suggested Move / Create Actions

- Create all missing directories from the target tree
- Create skeleton files for the new package modules and scripts
- Keep `model_raw.py` and `benchmark_raw.py` in place as temporary reference code rather than deleting them
- Update package exports to use the new module paths and avoid importing heavy model code at import time
- Add `docs/reports/` reports describing the structural delta and next actions