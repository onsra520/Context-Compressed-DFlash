# CC-DFlash Demo Notebooks

This folder contains a three-notebook teaching and demonstration workflow for the CC-DFlash benchmark.

## Environment Activation
Ensure you are running the notebooks from the repository root using the project's virtual environment:
```bash
source .venv/bin/activate
jupyter notebook notebooks/
```

## Notebook Order
1. `01_fetch_and_process_datasets.ipynb`: Downloads and prepares the raw data into evaluation jsonl.
2. `02_run_three_version_benchmark.ipynb`: Runs the three core conditions (Baseline-AR, DFlash-R1, CC-DFlash-R2) sequentially using the shared `DemoRunner` contract.
3. `03_compare_benchmark_charts.ipynb`: Analyzes the outputs from Notebook 2 and generates comparative charts.

## Notebook Restructuring (T112B-R3)
- **Notebook 02** splits the execution of the three models (Baseline-AR, DFlash-R1, CC-DFlash-R2 Light GPU) into separate cells so each run and result can be inspected independently.
- **Notebook 03** reads the latest completed run ID and produces a single unified `three_version_comparison_dashboard.png` composite dashboard.
- **`utils.py` Helper**: Handles repository root detection, system path configuration, and clean notebook environment initialization.

## Simplified Result Layout
Each run generates a unique `RUN_ID` and stores its outputs under:
`results/charts/notebook_demo/<RUN_ID>/`
- `results.jsonl`: The canonical execution record.
- `comparison.csv`: Human-readable summary table.
- `summary.json`: High-level summary.
- `manifest.json`: Configuration metadata and paths.
- `charts/three_version_comparison_dashboard.png`: Unified composite chart.

Latest execution metadata is kept in:
`results/charts/notebook_demo/latest_run.json`

## Rerunning Safely
Every "Run All" execution creates a fresh `RUN_ID`. Existing output files do not cause execution to be skipped.

## QMSum Caveat
**Semantic correctness is not claimed for QMSum.** The target model's output quality on QMSum is a final limitation of Phase 2.
