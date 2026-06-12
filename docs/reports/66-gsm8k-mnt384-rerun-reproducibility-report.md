# Task 66 — GSM8K Compressed mnt384 Rerun Reproducibility

Date: 2026-06-12

Status: PASS, preliminary

## Scope

Task 66 reran the same compressed-only GSM8K `max_new_tokens=384` calibration from Task 65 using unique output paths. The goal was to determine whether Task 65's high latency was reproducible or caused by a noisy/resource-contended run.

This task did not run n=100, did not run QMSum, did not run uncompressed conditions, did not change keep rate, did not use `--overwrite`, and did not modify Task 65 artifacts.

## Task 65 Commit

Task 65 was already committed before this task:

| Commit | Message |
|---|---|
| `e2416e2` | `test: calibrate compressed gsm8k at mnt384` |

## Preflight Resource Snapshot

Preflight was saved to `results/task66_mnt384_rerun_preflight.txt`.

| Check | Observed |
|---|---|
| Date | Fri Jun 12 23:34:02 +07 2026 |
| Uptime | up 1 min, load average 0.77 / 0.31 / 0.11 |
| System memory | 54 GiB total, 51 GiB available |
| GPU | NVIDIA GeForce RTX 4070 Laptop GPU |
| GPU memory before run | 655 MiB / 8188 MiB |
| GPU process list | No running GPU processes found |
| Heavy benchmark process | No active `scripts/run_mvp.py` process before start |
| Disk | 870 GiB available on `/` |

The preflight was materially cleaner than the Task 65 run environment.

## Commands Run

| Step | Command / Summary | Result |
|---|---|---|
| Prompt dry-run | `scripts/run_mvp.py --prompt-source dataset --dataset gsm8k_short --n 3 --seed 42 --dry-run-prompts` | PASS |
| Prompt suffix check | Direct formatter check for sampled GSM8K prompts | PASS, all sampled prompts ended with `Final answer: <number>` |
| LLMLingua-AR-R2 rerun | `scripts/run_mvp.py --prompt-source dataset --dataset gsm8k_short --condition LLMLingua-AR-R2 --n 30 --seed 42 --max-new-tokens 384 --output results/task66_gsm8k_short_llmlingua_ar_r2_n30_mnt384_rerun.jsonl --resume --store-generated-text` | PASS, 30 rows |
| CC-DFlash-R2 rerun | `scripts/run_mvp.py --prompt-source dataset --dataset gsm8k_short --condition CC-DFlash-R2 --n 30 --seed 42 --max-new-tokens 384 --output results/task66_gsm8k_short_cc_dflash_r2_n30_mnt384_rerun.jsonl --resume --store-generated-text` | PASS, 30 rows |
| Analyzer | `scripts/analyze_task66_mnt384_rerun_reproducibility.py` | PASS |

## Run Completion

| Condition | Artifact | Rows | Generated text | Keep rate | Suffix preserved | Question preserved |
|---|---|---:|---:|---:|---:|---:|
| LLMLingua-AR-R2 | `results/task66_gsm8k_short_llmlingua_ar_r2_n30_mnt384_rerun.jsonl` | 30 | 30/30 | 0.50 | 30/30 | 30/30 |
| CC-DFlash-R2 | `results/task66_gsm8k_short_cc_dflash_r2_n30_mnt384_rerun.jsonl` | 30 | 30/30 | 0.50 | 30/30 | 30/30 |

Both artifacts include `t_compress_ms`, `original_input_tokens`, `compressed_input_tokens`, and compression-ratio fields in every row.

## Task 65 vs Task 66 Quality

| Condition | Task 65 numeric | Task 66 numeric | Delta | Task 65 exact containment | Task 66 exact containment |
|---|---:|---:|---:|---:|---:|
| LLMLingua-AR-R2 | 24/30 | 24/30 | 0 | 25/30 | 25/30 |
| CC-DFlash-R2 | 24/30 | 24/30 | 0 | 25/30 | 25/30 |

Changed outcomes:

| Outcome | Count |
|---|---:|
| `SAME_PASS` | 48 |
| `SAME_FAIL` | 12 |
| `FAIL_TO_PASS` | 0 |
| `PASS_TO_FAIL` | 0 |

Quality is reproducible across Task 65 and Task 66 at this n=30 size.

## Cap-Hit Comparison

| Condition | Task 65 cap hits | Task 66 cap hits | Task 65 cap-hit failures | Task 66 cap-hit failures |
|---|---:|---:|---:|---:|
| LLMLingua-AR-R2 | 3 | 3 | 3 | 3 |
| CC-DFlash-R2 | 3 | 3 | 3 | 3 |

The remaining cap-hit pattern is reproducible. Task 66 does not clear the remaining cap-hit blocker.

## Latency Reproducibility

| Condition | Task 65 avg e2e | Task 66 avg e2e | Absolute delta | Relative delta | Interpretation |
|---|---:|---:|---:|---:|---|
| LLMLingua-AR-R2 | 25.49s | 10.56s | -14.94s | -58.59% | Task 65 noisy; Task 66 lower |
| CC-DFlash-R2 | 38.94s | 4.11s | -34.83s | -89.45% | Task 65 noisy; Task 66 lower |

Weighted throughput also recovered:

| Condition | Task 65 e2e tok/s | Task 66 e2e tok/s |
|---|---:|---:|
| LLMLingua-AR-R2 | 6.78 | 16.37 |
| CC-DFlash-R2 | 4.50 | 42.67 |

Task 65 latency was not reproducible. Use Task 66, not Task 65, for `max_new_tokens=384` latency interpretation.

## Interpretation

Task 66 confirms that `max_new_tokens=384` keeps the Task 65 quality gain: both compressed conditions remain at 24/30 numeric matches with no pass-to-fail rows.

Task 66 also shows that the severe Task 65 latency jump was likely noisy/resource-related. Under a cleaner preflight, LLMLingua-AR-R2 average e2e latency fell from 25.49s to 10.56s, and CC-DFlash-R2 fell from 38.94s to 4.11s.

Even with the cleaner rerun, `max_new_tokens=384` should not become a blanket speed-benchmark default. It is best treated as a GSM8K quality-calibration setting. Three cap-hit failures remain per condition, so n=100 is not justified yet.

## Recommendation

Next task: read-only triage of Task 66 remaining failures and cap-hit rows.

The recommended Task 67 should:

- inspect the 12 `SAME_FAIL` rows,
- inspect the 3 cap-hit failures per condition,
- determine whether failures are remaining truncation, reasoning/model limits, or prompt/compression artifacts,
- decide whether n=100 is justified after this cleaner latency rerun.

Do not increase max_new_tokens again and do not run n=100 before that triage.

## Validation

Validation commands and results are recorded in the final response for this task.
