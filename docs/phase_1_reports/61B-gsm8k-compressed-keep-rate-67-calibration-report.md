# Task 61B — GSM8K Compressed keep_rate_percent=67 Calibration

Date: 2026-06-12

Status: PASS, preliminary

## Scope

Task 61B ran the tiny compressed-only GSM8K calibration requested after Task 61A. It tested whether a gentler LLMLingua keep rate, requested with `--keep-rate-percent 67`, improves the remaining compressed GSM8K quality failures at `max_new_tokens=256`.

This is not a final benchmark, not n=100, and not evidence of final correctness or speedup.

## Precondition

Task 61A was committed before this task:

- Commit: `81e6b2c feat: add keep-rate percent cli override`

## Commands Run

Prompt dry-run:

- `PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --prompt-source dataset --dataset gsm8k_short --n 3 --seed 42 --dry-run-prompts --keep-rate-percent 67`

Prompt-text assertion:

- Verified the selected GSM8K prompts contain `Final answer: <number>`.

Compressed calibration runs:

- `PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --prompt-source dataset --dataset gsm8k_short --condition LLMLingua-AR-R2 --n 10 --seed 42 --max-new-tokens 256 --keep-rate-percent 67 --output results/task61b_gsm8k_short_llmlingua_ar_r2_n10_mnt256_k067.jsonl --resume --store-generated-text`
- `PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --prompt-source dataset --dataset gsm8k_short --condition CC-DFlash-R2 --n 10 --seed 42 --max-new-tokens 256 --keep-rate-percent 67 --output results/task61b_gsm8k_short_cc_dflash_r2_n10_mnt256_k067.jsonl --resume --store-generated-text`

Analyzer:

- `PYTHONPATH=src .venv/bin/python scripts/analyze_task61b_keep_rate67_calibration.py`

## Artifacts

| Artifact | Rows | Status |
|---|---:|---|
| `results/task61b_gsm8k_short_llmlingua_ar_r2_n10_mnt256_k067.jsonl` | 10 | Created |
| `results/task61b_gsm8k_short_cc_dflash_r2_n10_mnt256_k067.jsonl` | 10 | Created |
| `results/task61b_keep_rate67_calibration_summary.json` | 1 summary | Created |
| `results/task61b_keep_rate67_calibration_table.csv` | 4 condition-stage rows | Created |
| `results/task61b_keep_rate67_changed_outcomes.jsonl` | 20 rows | Created |

No prior Task 60 artifacts were modified.

## Metadata Verification

Both Task 61B JSONL artifacts have:

| Field / Check | LLMLingua-AR-R2 | CC-DFlash-R2 |
|---|---:|---:|
| Rows | 10 | 10 |
| `requested_keep_rate_percent` | 67.0 on all rows | 67.0 on all rows |
| `requested_keep_rate` | 0.67 on all rows | 0.67 on all rows |
| `keep_rate` | 0.67 on all rows | 0.67 on all rows |
| `protected_suffix_preserved` | 10/10 | 10/10 |
| `final_prompt_tail_preview` contains final-answer instruction | 10/10 | 10/10 |
| `question_preserved` | 10/10 | 10/10 |
| `generated_text` present | 10/10 | 10/10 |
| Hit max_new_tokens cap | 1/10 | 1/10 |

## Task 60 vs Task 61B Summary

| Condition | Stage | Numeric matches | Generated final markers | Hit cap | Avg kept-token ratio | Avg compression ratio | Avg e2e time (s) |
|---|---|---:|---:|---:|---:|---:|---:|
| LLMLingua-AR-R2 | Task 60 keep_rate=0.50 | 8/10 | 8/10 | 1/10 | 0.375 | 2.667 | 9.93 |
| LLMLingua-AR-R2 | Task 61B keep_rate=0.67 | 8/10 | 9/10 | 1/10 | 0.625 | 1.600 | 9.11 |
| CC-DFlash-R2 | Task 60 keep_rate=0.50 | 8/10 | 9/10 | 1/10 | 0.375 | 2.667 | 3.51 |
| CC-DFlash-R2 | Task 61B keep_rate=0.67 | 8/10 | 9/10 | 1/10 | 0.625 | 1.600 | 3.35 |

## Changed Outcomes

| Condition | FAIL_TO_PASS | PASS_TO_FAIL | SAME_PASS | SAME_FAIL |
|---|---:|---:|---:|---:|
| LLMLingua-AR-R2 | 1 | 1 | 7 | 1 |
| CC-DFlash-R2 | 1 | 1 | 7 | 1 |

The gentler keep rate did not improve net numeric extraction. It changed individual outcomes in both directions, so it should not be treated as monotonic quality improvement.

## Interpretation

Task 61B confirms the new CLI override works in real compressed GSM8K runs and records the requested keep-rate metadata correctly. The protected final-answer suffix survived in every row.

Quality remains 8/10 for both compressed conditions, matching Task 60. Because each condition has one `FAIL_TO_PASS` and one `PASS_TO_FAIL`, the safer interpretation is that remaining failures are prompt/model/extraction/sample sensitive rather than solved by a simple keep-rate increase from 0.50 to 0.67.

The lower average `t_compress_ms` and e2e time in this tiny run should be treated as smoke-level variability, not a speed conclusion.

## Recommendation

Do not test `--keep-rate-percent 80` yet. Do not adopt 0.67 as the default R2 keep rate. Keep the default R2 behavior at 0.50 for speed-stress comparison until larger evidence says otherwise.

Recommended next task: Task 62 should triage the remaining `SAME_FAIL` and `PASS_TO_FAIL` rows using prompt previews, compressed context previews, generated text, and extraction details. After that, a small n=30 compressed GSM8K run may be more useful than another blind keep-rate increase.

## Validation

- Focused analyzer test: PASS
- Prompt dry-run: PASS
- Prompt-text final-answer instruction assertion: PASS
- LLMLingua-AR-R2 real compressed run: PASS
- CC-DFlash-R2 real compressed run: PASS
- Metadata gate check: PASS
- Analyzer output JSON validity: PASS

Broader compile/test/doc sanity validation is recorded in the final task response.
