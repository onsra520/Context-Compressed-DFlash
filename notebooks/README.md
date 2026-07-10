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
2. `02_run_three_version_benchmark.ipynb`: Runs the three core conditions (Baseline-AR, DFlash-R1, CC-DFlash-R2) using the shared `DemoRunner` contract.
3. `03_compare_benchmark_charts.ipynb`: Analyzes the outputs from Notebook 2 and generates comparative charts.

## Safe Default Behavior
By default, Notebook 2 is configured to run in **dry-run** mode (`RUN_REAL_MODELS = False`), which will safely execute the schema and pipeline paths without loading real models or consuming GPU VRAM.

## Enabling Actual Model Execution
To run with real models:
1. Ensure you have an 8GB GPU.
2. In Notebook 2, change the configuration flag:
   ```python
   RUN_REAL_MODELS = True
   ```
   Or set the environment variable before launching Jupyter:
   ```bash
   CCDF_NOTEBOOK_REAL_RUN=1 jupyter notebook
   ```

## GPU Requirements
The demo executes the three conditions sequentially, explicitly collecting garbage and clearing the CUDA cache between condition loads. It is designed to fit entirely within an 8GB VRAM constraint (typically peaking around 5-6GB depending on the model context).

## Output Paths
Artifacts from the benchmark run are exported to:
`results/charts/notebook_demo/`
- `runs/`: JSONL files containing sequential execution output.
- `tables/`: CSV aggregations.
- `summaries/`: Execution summaries.
- `figures/`: Output charts from Notebook 3.

## Rerunning Safely
Notebook 2 defaults to `RESUME = True`, meaning it will continue from where it left off. If you want to force a fresh run, delete the JSONL/CSV outputs inside `results/charts/notebook_demo/` before running.

## QMSum Caveat
**Semantic correctness is not claimed for QMSum.** The target model's output quality on QMSum is a final limitation of Phase 2. Any proxy quality charts (or lack thereof) for QMSum do not prove the underlying generation is factually sound. 

## Future Extension (T113A)
These notebooks utilize the new canonical `DemoRunner` JSON contract (Task 112A). This identical interface will be leveraged by the future Three-Version Web Comparison UI (T113A).

Run All always creates a fresh benchmark run.
Existing result files do not skip execution.
Notebook 03 uses the latest completed run and regenerates all charts.
