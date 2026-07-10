# T112B-R2: Always-Run Notebook UX and Complete Outputs Report

## 1. Previous Skip Behavior
Notebook 02 had boolean gates like `RUN_REAL_MODELS = False` and `RESUME = True`.

## 2. Fresh-Run Design
Replaced static paths with dynamically generated `RUN_ID`. 
Updated `latest_run.json` to track the newest run for Notebook 03.

## 3. Import Cleanup
Unused imports were cleaned up across all notebooks. Model imports were removed from Notebook 03.

## 4. Notebook 01 Behavior
Unconditionally calls the raw fetch and process modules for all datasets. No more cache skipping logic in the notebook itself.

## 5. Notebook 02 Full Output Behavior
Iterates through all rows and conditions, displaying the complete prompt, full generated output, and metrics without truncation.

## 6. Notebook 03 Chart Display Behavior
Iterates through charts generated via `yield` from the helper, saves them to `figures/<RUN_ID>`, and explicitly uses `display(figure)`.

## 7. First Execution
Successfully generated run `20260710T083207Z`.

## 8. Second Execution
Successfully generated run `20260710T083239Z`. 

## 9. Generated Artifact Paths
- `results/charts/notebook_demo/runs/<RUN_ID>/`
- `results/charts/notebook_demo/tables/<RUN_ID>/`
- `results/charts/notebook_demo/summaries/<RUN_ID>/`
- `results/charts/notebook_demo/figures/<RUN_ID>/`
- `results/charts/notebook_demo/latest_run.json`

## 10. Tests and Limitations
Regression tests in `tests/test_task112b_notebook_usage_demo.py` were updated and pass completely.
