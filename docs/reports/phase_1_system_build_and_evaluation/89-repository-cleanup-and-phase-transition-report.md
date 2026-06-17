# Task 89 — Repository Cleanup, Data Pipeline Normalization, and Phase Transition Readiness

## 1. Objective
Complete a full repository cleanup, freeze the active evaluation data pipeline, and normalize the script and results taxonomies in preparation for the Phase 1 end-to-end reproduction rerun (Task 90) and the transition to Phase 2 (System Optimization).

## 2. Why Task89 was needed
Following the completion of the controlled n=30 baseline benchmark (Task 88), the repository contained legacy ablation branches, fragmented phase definitions in the Roadmap, and inconsistent output paths for results. A strict cleanup was required to ensure that the Phase 1 final reproduction gate (Task 90) could run cleanly on a frozen, canonical pipeline without legacy distractions.

## 3. Deprecated Wikipedia/GSM8K-augmented branch
GSM8K+Wikipedia augmented was an early long-context distractor/ablation branch.
It is deprecated and removed from the active path.
Active evaluation uses GSM8K short-context numeric proxy and QMSum meeting QA long-context diagnostic benchmark.

## 4. Final data lifecycle
The final data lifecycle is strictly defined as follows:
```text
data/raw/       = fetched/source/cache data
data/processed/ = lightly processed / normalized data
data/eval/      = fixed n=100 benchmark input used by run_mvp.py
```
Row counts of the canonical datasets:
```text
data/raw/gsm8k_source.jsonl = 1319 rows
data/raw/qmsum_meeting_qa_source.jsonl = 35 rows
data/processed/gsm8k_processed.jsonl = 1319 rows
data/processed/qmsum_meeting_qa_processed.jsonl = 244 rows
data/eval/gsm8k_100.jsonl = 100 rows
data/eval/qmsum_meeting_qa_100.jsonl = 100 rows
```

## 5. Fetch pipeline consolidation
The dataset acquisition, processing, and evaluation sampling logic was consolidated into a single entry point script.
Canonical command to reproduce the data pipeline:
```bash
PYTHONPATH=src .venv/bin/python scripts/fetch_dataset.py --dataset all_active --stage all --max-samples 100 --seed 42
```

## 6. Final reports/plans structure
Reports and plans were reorganized into phase-specific directories, and the legacy task plan trackers were removed in favor of the centralized Roadmap.

## 7. Final scripts taxonomy
Scripts were reorganized to separate Phase 1 (System Build and Evaluation) from upcoming Phase 2 (System Optimization). The Phase 1 scripts are now correctly grouped into `runners`, `probes`, `analysis`, and `audits`.

## 8. Final results taxonomy
The results directory was restructured to ensure all artifacts are explicitly categorized, removing any loose files under the root `results/`.
Final structure:
* `results/phase_1_system_build_and_evaluation/final_reruns/`
* `results/phase_1_system_build_and_evaluation/repair_and_gate/`
* `results/phase_1_system_build_and_evaluation/quality_and_latency_audits/`
* `results/phase_1_system_build_and_evaluation/early_experiments/`

## 9. Roadmap synchronization
The `docs/Roadmap.html` was heavily refactored to represent the correct project phases (Phase 0 Foundation, Phase 1 System Build, Phase 2 Optimization). Task ledgers for T87, T88, T89, and T90 were synchronized to reflect current statuses.

## 10. Validation
The repository state successfully passes `compileall` and `pytest`, and all `results/` artifacts have been moved to their correct categorized locations.

## 11. Cleanup/fix commit list
* `485abbd` docs: sync roadmap task87 to task90 statuses
* `24596ad` docs: fix roadmap phase bars and artifact layout
* `c423148` docs: normalize roadmap phase gates and task phases
* `027b489` docs: sync roadmap after task89 cleanup
* `7a9ed69` fix: freeze active eval data and result output paths
* `2a5d05d` fix: normalize active data pipeline layout
* `a634d2e` fix: normalize data and results taxonomy
* `65b65fe` fix: normalize phase 1 structure and script taxonomy

## 12. Task90 readiness
Task 89 has successfully prepared the repository for Task 90. However, Task 89 did **not** run the benchmark matrix itself. Task 90 will run the end-to-end reproduction rerun.

## 13. Claim boundary
* no universal speedup claim
* no final correctness claim
* no QMSum semantic correctness claim
* no deployment readiness claim
* no confirmed 8GB claim
* no DFlash-R1 broken claim
