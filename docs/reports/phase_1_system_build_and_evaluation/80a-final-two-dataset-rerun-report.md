# Task 80A — Final Two-Dataset Rerun / Recompute Package

Date: 2026-06-14

Status: BLOCKED / PASS_WITH_NOTES

## Scope

Task 80A attempted a final n=30 verification rerun on the frozen two-dataset setup before final report drafting:

- GSM8K short-context numeric QA: four frozen conditions, `max_new_tokens=384`.
- QMSum meeting QA long-context diagnostic: four frozen conditions, `max_new_tokens=384`.

This was a real run task. It loaded target model weights, draft model weights for DFlash paths, LLMLingua for compressed paths, and CUDA. It did not run n=100, did not run `max_new_tokens=512`, did not tune prompts, did not create datasets, and did not overwrite old artifacts.

## Commit Before Rerun

Task 80 was already committed before Task 80A work began:

| Commit | Message |
| --- | --- |
| `e9779e2` | `docs: package cross-dataset final results` |

## Commands

All real run commands used `--resume`, unique `results/task80a_*` output paths, and `--store-generated-text`. Full command strings are recorded in:

- `results/task80a_run_manifest.json`

## Run Completion

| Dataset | Condition | Artifact | Rows | Status | Notes |
| --- | --- | --- | ---: | --- | --- |
| GSM8K | Baseline-AR | `results/task80a_gsm8k_short_baseline_ar_n30_mnt384.jsonl` | 30 | completed | real CUDA target run |
| GSM8K | DFlash-R1 | `results/task80a_gsm8k_short_dflash_r1_n30_mnt384.jsonl` | 30 | completed | target + draft |
| GSM8K | LLMLingua-AR-R2 | `results/task80a_gsm8k_short_llmlingua_ar_r2_n30_mnt384.jsonl` | 30 | completed | target + LLMLingua |
| GSM8K | CC-DFlash-R2 | `results/task80a_gsm8k_short_cc_dflash_r2_n30_mnt384.jsonl` | 30 | completed | target + draft + LLMLingua |
| QMSum | Baseline-AR | `results/task80a_qmsum_long_baseline_ar_n30_mnt384.jsonl` | 30 | completed | real CUDA target run |
| QMSum | DFlash-R1 | `results/task80a_qmsum_long_dflash_r1_n30_mnt384.jsonl` | 2 | failed_partial | stopped at prompt_id=3 after prolonged no-progress interval with GPU active and near-full VRAM |
| QMSum | LLMLingua-AR-R2 | not created | 0 | skipped | skipped after QMSum DFlash-R1 safety stop |
| QMSum | CC-DFlash-R2 | not created | 0 | skipped | skipped after QMSum DFlash-R1 safety stop |

## Final GSM8K Rerun Summary

| Condition | Rows | Numeric matches | Accuracy | Avg e2e latency s | e2e tok/s | Avg T_compress ms | Cap hits | Peak reserved GiB |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Baseline-AR | 30 | 25/30 | 0.833333 | 15.958343 | 10.955607 | 0.000000 | 0 | 2.656250 |
| DFlash-R1 | 30 | 24/30 | 0.800000 | 10.494549 | 16.087717 | 0.000000 | 1 | 3.841797 |
| LLMLingua-AR-R2 | 30 | 24/30 | 0.800000 | 11.309493 | 15.279200 | 913.919936 | 3 | 2.679688 |
| CC-DFlash-R2 | 30 | 24/30 | 0.800000 | 4.696341 | 37.341127 | 909.659668 | 3 | 3.847656 |

GSM8K interpretation:

- GSM8K quality counts reproduce the Task 80 package pattern: Baseline-AR 25/30, DFlash-R1 24/30, LLMLingua-AR-R2 24/30, and CC-DFlash-R2 24/30.
- CC-DFlash-R2 remains faster end-to-end than LLMLingua-AR-R2 in this rerun.
- DFlash-R1 is slower than its Task 80 reference due to runtime noise/outliers, but still faster than Baseline-AR in the Task80A GSM8K rerun.
- These remain n=30 local evidence, not final correctness or universal speedup claims.

## Final QMSum Diagnostic Summary

| Condition | Rows | Avg overlap proxy | Avg e2e latency s | e2e tok/s | Avg T_compress ms | Cap hits | Peak reserved GiB | Status |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Baseline-AR | 30 | 0.260169 | 7.832210 | 12.406035 | 0.000000 | 0 | 4.351562 | completed |
| DFlash-R1 | 2 | 0.435216 | 8.950561 | 11.563521 | 0.000000 | 0 | 4.689453 | failed_partial |
| LLMLingua-AR-R2 | 0 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0 | 0.000000 | skipped |
| CC-DFlash-R2 | 0 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0 | 0.000000 | skipped |

QMSum interpretation:

- QMSum remains diagnostic only and does not support semantic correctness claims.
- QMSum Baseline-AR completed at n=30.
- QMSum DFlash-R1 stopped after 2 rows; prompt_id=3 had prolonged no-progress with GPU active and near-full VRAM.
- Because the safety rule required stopping after the QMSum DFlash issue, QMSum LLMLingua-AR-R2 and CC-DFlash-R2 were skipped.

## Delta vs Task 80 Package

Machine-readable delta table:

- `results/task80a_condition_delta_vs_task80.csv`

Summary:

| Severity | Count | Meaning |
| --- | ---: | --- |
| `major_shift` | 3 | QMSum row-count incompleteness for DFlash-R1, LLMLingua-AR-R2, and CC-DFlash-R2 |
| `watch` | 9 | Mostly timing shifts, including GSM8K DFlash/Baseline runtime noise and skipped QMSum timing deltas |
| `ok` | remaining rows | Quality counts and many scalar metrics remain within expected bounds |

Major-shift items:

- QMSum DFlash-R1 row count: 30 reference rows vs 2 Task80A rows.
- QMSum LLMLingua-AR-R2 row count: 30 reference rows vs 0 Task80A rows.
- QMSum CC-DFlash-R2 row count: 30 reference rows vs 0 Task80A rows.

## Assessment

Task80A should not be treated as a clean full rerun package. It is useful because it confirms the GSM8K n=30 story under a fresh run, but it also exposes a QMSum DFlash runtime/VRAM issue that blocks clean final consistency audit.

Major-shift / watch / ok assessment:

- GSM8K quality: ok.
- GSM8K timing: watch due to runtime noise, especially Baseline-AR and DFlash-R1.
- QMSum Baseline-AR: ok as a completed diagnostic rerun, with timing shift watch.
- QMSum DFlash/CC/compressed matrix: major_shift / blocked because the rerun did not complete.

## Claim Reminder

This report does not support:

- universal speedup claims,
- QMSum semantic correctness claims,
- deployment readiness claims,
- confirmed 8 GB deployment claims,
- or a claim that compression is proven useful end-to-end.

## Next Task

Task 80B should analyze the QMSum DFlash/runtime issue and decide whether final consistency audit can proceed, whether QMSum DFlash needs a lower-risk diagnostic rerun shape, or whether the final package should rely on the already-completed Task 71/79B QMSum diagnostic evidence instead of Task80A QMSum rerun completion.

## Validation

Validation commands run:

| Check | Result |
| --- | --- |
| `python3 -m compileall src tests scripts 2>&1 | tail -20` | PASS |
| `PYTHONPATH=src .venv/bin/python -m pytest tests/ -x -q 2>&1 | tail -30` | PASS, 167 tests passed, 2 warnings |
| `python3 -m json.tool results/task80a_final_two_dataset_rerun_summary.json >/dev/null` | PASS |
| `python3 -m json.tool results/task80a_run_manifest.json >/dev/null` | PASS |
| `wc -l results/task80a_final_two_dataset_rerun_table.csv` | 9 lines |
| `wc -l results/task80a_condition_delta_vs_task80.csv` | 61 lines |
| Task80A GSM8K JSONL row counts | 4 files, 30 rows each |
| Task80A QMSum JSONL row counts | Baseline-AR 30 rows, DFlash-R1 2 rows |
| Markdown fence balance for this report | PASS |
| HTML sanity for docs | PASS |

Understand-Anything refresh: skipped in this environment because `/understand` slash command is not available to this agent runtime.
