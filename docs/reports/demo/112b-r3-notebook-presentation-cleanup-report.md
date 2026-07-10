# T112B-R3: Notebook Cell Structure and Presentation Cleanup Report

## 1. Purpose
The purpose of this patch is to improve the notebook presentation layer and clean up the structure of the demo results without altering the underlying T112A execution semantics.

## 2. Previous Notebook Structure Issue
Previously, Notebook 02 executed all three conditions in a single giant loop, hiding the model executions and outputs in one massive block. Notebook 03 generated several individual PNG images for metrics, which made it tedious for a reader to consume. Additionally, the notebook helper was named `notebook_setup.py`, which needed renaming to `utils.py`.

## 3. Helper Rename
- Git moved `notebooks/notebook_setup.py` to `notebooks/utils.py`.
- Updated all references in notebooks (01, 02, 03) and test files.
- The new helper uses the standard `from utils import setup_root` style.

## 4. Notebook 02 Cell Structure
Notebook 02 was restructured into exactly 18 distinct cells:
1. Title and purpose (Markdown)
2. Environment and repository setup (Code)
3. Demo configuration (Code)
4. Load selected dataset row(s) (Code)
5. Show selected prompt/reference (Code)
6. Initialize shared DemoRunner (Code)
7. Baseline-AR section (Markdown)
8. Run Baseline-AR (Code)
9. Display Baseline-AR result (Code)
10. DFlash-R1 section (Markdown)
11. Run DFlash-R1 (Code)
12. Display DFlash-R1 result (Code)
13. CC-DFlash-R2 section (Markdown)
14. Run CC-DFlash-R2 (Code)
15. Display CC-DFlash-R2 result (Code)
16. Three-version comparison (Code)
17. Save JSONL/CSV/summary/manifest (Code)
18. Final artifact paths and interpretation notes (Markdown)

## 5. Notebook 02 Model-by-Model Presentation
Each condition section runs sequentially, displaying its results independently. It shows the untruncated output text, latency values, VRAM, and a clean tabular summary.

## 6. Notebook 03 Composite Dashboard
- Replaced the multiple PNG files with a single composite dashboard: `three_version_comparison_dashboard.png`.
- The dashboard aligns three columns (Baseline-AR, DFlash-R1, and CC-DFlash-R2 Light GPU) across seven rows representing metric groups.
- The dashboard is saved to `results/charts/notebook_demo/<RUN_ID>/charts/` and explicitly displayed in the notebook using `display()`.

## 7. Simplified External Result Structure
For each run, we export:
- `results.jsonl`: The canonical contract result.
- `comparison.csv`: Human-readable summary table.
- `summary.json`: High-level summary.
- `manifest.json`: Configuration settings and paths.
- `charts/three_version_comparison_dashboard.png`: Visual dashboard.

## 8. Import Cleanup
Unused, duplicate, and wildcard imports were cleaned up across all notebooks. No model runtimes are loaded in Notebook 03.

## 9. Execution Validation
The entire sequence was validated under venv:
- Notebook 01: executed successfully.
- Notebook 02: executed successfully, producing run `20260710T085831Z`.
- Notebook 03: executed successfully, displaying the composite dashboard.
- Pytest suite: `31 passed in 3.88s`.

## 10. Remaining Limitations
- Semantic correctness is not claimed on QMSum.
- The execution relies on dry_run/mock modes under test mode.

## 11. Next Task
The notebooks and demo runner core are clean and presentation-ready. Next phase is T113A (Frontend integration).
