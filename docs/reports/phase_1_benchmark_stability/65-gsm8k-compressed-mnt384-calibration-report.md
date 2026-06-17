# Task 65 — GSM8K Compressed max_new_tokens=384 Calibration

Date: 2026-06-12

Status: PASS, preliminary

## Scope

Task 65 ran a compressed-only GSM8K calibration at `max_new_tokens=384` to test whether the Task 64 truncation-dominant failures improve when the output cap increases from 256 to 384.

This task did not run n=100, did not run QMSum, did not run uncompressed conditions, did not change keep rate, did not use `--overwrite`, and did not modify old artifacts.

## Task 64 Commit

Task 64 was committed before Task 65:

| Commit | Message |
|---|---|
| `99f09b4` | `test: triage gsm8k cap-hit failures` |

## Commands Run

| Step | Command / Summary | Result |
|---|---|---|
| Prompt dry-run | `scripts/run_mvp.py --prompt-source dataset --dataset gsm8k_short --n 3 --seed 42 --dry-run-prompts` | PASS |
| Prompt suffix check | Direct formatter check for sampled GSM8K prompts | PASS, all sampled prompts ended with `Final answer: <number>` |
| LLMLingua-AR-R2 | `scripts/run_mvp.py --prompt-source dataset --dataset gsm8k_short --condition LLMLingua-AR-R2 --n 30 --seed 42 --max-new-tokens 384 --output results/task65_gsm8k_short_llmlingua_ar_r2_n30_mnt384.jsonl --resume --store-generated-text` | PASS, 30 rows |
| CC-DFlash-R2 | `scripts/run_mvp.py --prompt-source dataset --dataset gsm8k_short --condition CC-DFlash-R2 --n 30 --seed 42 --max-new-tokens 384 --output results/task65_gsm8k_short_cc_dflash_r2_n30_mnt384.jsonl --resume --store-generated-text` | PASS, 30 rows |
| Analyzer | `scripts/phase_1_analysis/analyze_task65_mnt384_calibration.py` | PASS |

## Run Completion

| Condition | Artifact | Rows | Resume | Generated text | Keep rate | Suffix preserved | Question preserved |
|---|---|---:|---|---:|---:|---:|---:|
| LLMLingua-AR-R2 | `results/task65_gsm8k_short_llmlingua_ar_r2_n30_mnt384.jsonl` | 30 | yes | 30/30 | 0.50 | 30/30 | 30/30 |
| CC-DFlash-R2 | `results/task65_gsm8k_short_cc_dflash_r2_n30_mnt384.jsonl` | 30 | yes | 30/30 | 0.50 | 30/30 | 30/30 |

Both compressed artifacts include `t_compress_ms`, `original_input_tokens`, `compressed_input_tokens`, and compression-ratio fields in all rows.

## Task 63 vs Task 65 Quality

| Condition | Task 63 cap | Task 63 numeric | Task 65 cap | Task 65 numeric | Delta |
|---|---:|---:|---:|---:|---:|
| LLMLingua-AR-R2 | 256 | 22/30 | 384 | 24/30 | +2 |
| CC-DFlash-R2 | 256 | 23/30 | 384 | 24/30 | +1 |

Changed outcomes:

| Outcome | Count |
|---|---:|
| `FAIL_TO_PASS` | 3 |
| `PASS_TO_FAIL` | 0 |
| `SAME_PASS` | 45 |
| `SAME_FAIL` | 12 |

## Cap-Hit Comparison

| Condition | Task 63 cap hits | Task 65 cap hits | Task 63 cap-hit failures | Task 65 cap-hit failures |
|---|---:|---:|---:|---:|
| LLMLingua-AR-R2 | 5 | 3 | 5 | 3 |
| CC-DFlash-R2 | 5 | 3 | 4 | 3 |

Task 64 truncation-dominant case resolution:

| Condition | Task 64 truncation cases | Previous numeric failures | Fixed by Task 65 | Still hit cap at 384 | Final-answer marker at 384 |
|---|---:|---:|---:|---:|---:|
| LLMLingua-AR-R2 | 5 | 5 | 2 | 3 | 1 |
| CC-DFlash-R2 | 5 | 4 | 1 | 3 | 1 |

## Latency Cost

| Condition | Task 63 avg gen latency | Task 65 avg gen latency | Delta | Task 63 avg e2e latency | Task 65 avg e2e latency | Delta |
|---|---:|---:|---:|---:|---:|---:|
| LLMLingua-AR-R2 | 8.65s | 24.38s | +15.73s | 9.44s | 25.49s | +16.06s |
| CC-DFlash-R2 | 2.86s | 37.69s | +34.83s | 3.67s | 38.94s | +35.26s |

Weighted throughput fell sharply:

| Condition | Task 63 gen tok/s | Task 65 gen tok/s | Task 63 e2e tok/s | Task 65 e2e tok/s |
|---|---:|---:|---:|---:|
| LLMLingua-AR-R2 | 17.98 | 7.09 | 16.47 | 6.78 |
| CC-DFlash-R2 | 55.55 | 4.65 | 43.30 | 4.50 |

## Interpretation

`max_new_tokens=384` reduces cap hits and improves numeric extraction for both compressed conditions without producing any `PASS_TO_FAIL` rows in this n=30 calibration.

The improvement is real but modest: +2 numeric matches for LLMLingua-AR-R2 and +1 for CC-DFlash-R2. Three cap hits remain in each condition, and non-cap failures remain unchanged at 3 per condition.

The latency cost is large, especially for CC-DFlash-R2 in this run. Because the calibration is preliminary and small, `max_new_tokens=384` should not become a blanket speed-benchmark default. It is better treated as a compressed GSM8K quality-calibration setting when answer completion matters more than throughput.

## Decision

`max_new_tokens=384` should not be blindly promoted as the compressed GSM8K default for all benchmark purposes.

Use it for compressed GSM8K quality calibration or final-answer-completion checks, but keep reporting its latency cost explicitly. Do not run n=100 immediately: Task 65 still has 3 cap hits per condition and 12 unchanged failures across the two compressed conditions.

## Recommendation

Next task: inspect Task 65 remaining failures and cap-hit rows before n=100.

The recommended Task 66 should be read-only:

- analyze remaining `SAME_FAIL` rows,
- inspect the three cap-hit rows per condition at 384,
- distinguish remaining truncation from completed reasoning failure,
- decide whether n=100 is justified or whether prompt/reasoning investigation is still needed.

Do not increase max_new_tokens again without targeted output inspection.

## Validation

Validation commands and results are recorded in the final response for this task.
