# Task 60: Tiny Compressed-Only GSM8K max_new_tokens=256 Calibration

Date: 2026-06-12

Status: PASS, preliminary compressed-only calibration

## Scope

Task 60 ran a tiny compressed-only GSM8K calibration at `max_new_tokens=256` to determine whether the remaining Task 59 failures were mainly output-budget or truncation related.

This is not a final benchmark, not an n=100 run, not a QMSum run, and not a final correctness or speedup claim.

Task 59 commit verified before this task:

- `564d090 test: verify gsm8k compressed suffix preservation`

## Commands Run

- `PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --prompt-source dataset --dataset gsm8k_short --n 3 --seed 42 --dry-run-prompts`
- Direct prompt-content assertion for `Final answer: <number>` in three selected GSM8K prompts.
- `PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --prompt-source dataset --dataset gsm8k_short --condition LLMLingua-AR-R2 --n 10 --seed 42 --max-new-tokens 256 --output results/task60_gsm8k_short_llmlingua_ar_r2_n10_mnt256_suffixfix.jsonl --resume --store-generated-text`
- `PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --prompt-source dataset --dataset gsm8k_short --condition CC-DFlash-R2 --n 10 --seed 42 --max-new-tokens 256 --output results/task60_gsm8k_short_cc_dflash_r2_n10_mnt256_suffixfix.jsonl --resume --store-generated-text`
- `PYTHONPATH=src .venv/bin/python scripts/phase_1_analysis/analyze_task60_mnt256_calibration.py`

## Run Completion

| Condition | Artifact | Rows | Resume | max_new_tokens | Status |
| --- | --- | ---: | --- | ---: | --- |
| LLMLingua-AR-R2 | `results/task60_gsm8k_short_llmlingua_ar_r2_n10_mnt256_suffixfix.jsonl` | 10 | `--resume` | 256 | PASS |
| CC-DFlash-R2 | `results/task60_gsm8k_short_cc_dflash_r2_n10_mnt256_suffixfix.jsonl` | 10 | `--resume` | 256 | PASS |

No old result artifact was overwritten. Task 59 artifacts were read only by the analyzer.

## Metadata Survival Summary

| Condition | Rows | `protected_suffix_preserved` | Tail preview has instruction | Metadata complete rows | Question preserved |
| --- | ---: | ---: | ---: | ---: | ---: |
| LLMLingua-AR-R2 | 10 | 10 | 10 | 10 | 10 |
| CC-DFlash-R2 | 10 | 10 | 10 | 10 | 10 |

The Task 58 suffix-protection contract remains intact under `max_new_tokens=256`.

## Task 59 vs Task 60 Comparison

| Condition | Stage | Rows | max_new_tokens | Generated `Final answer:` marker | Numeric extraction matches | Exact containment | Hit max token cap | Avg output tokens | Avg e2e time (s) | Avg `T_compress` (ms) |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| LLMLingua-AR-R2 | Task 59 suffix fix | 10 | 192 | 7 | 6 | 8 | 3 | 139.6 | 8.24 | 810.95 |
| LLMLingua-AR-R2 | Task 60 mnt256 | 10 | 256 | 8 | 8 | 10 | 1 | 151.3 | 9.93 | 951.91 |
| CC-DFlash-R2 | Task 59 suffix fix | 10 | 192 | 7 | 7 | 9 | 3 | 144.4 | 2.93 | 753.97 |
| CC-DFlash-R2 | Task 60 mnt256 | 10 | 256 | 9 | 8 | 10 | 1 | 154.9 | 3.51 | 893.97 |

Delta summary:

| Condition | Marker delta | Numeric extraction delta | Hit-cap delta | Avg e2e latency delta |
| --- | ---: | ---: | ---: | ---: |
| LLMLingua-AR-R2 | +1 | +2 | -2 | +1.68 s |
| CC-DFlash-R2 | +2 | +1 | -2 | +0.58 s |

## Changed Outcomes

| Condition | FAIL_TO_PASS | SAME_PASS | SAME_FAIL | PASS_TO_FAIL |
| --- | ---: | ---: | ---: | ---: |
| LLMLingua-AR-R2 | 2 | 6 | 2 | 0 |
| CC-DFlash-R2 | 1 | 7 | 2 | 0 |

No row regressed from numeric pass to numeric fail in this tiny sample.

## Interpretation

`max_new_tokens=256` reduced remaining cap hits from 3/10 to 1/10 for both compressed conditions and improved numeric extraction:

- LLMLingua-AR-R2: 6/10 to 8/10
- CC-DFlash-R2: 7/10 to 8/10

This supports using `max_new_tokens=256` as the compressed GSM8K calibration default for the next tiny runs.

The larger output cap increased latency:

- LLMLingua-AR-R2 average e2e time rose from 8.24 s to 9.93 s.
- CC-DFlash-R2 average e2e time rose from 2.93 s to 3.51 s.

The latency cost is expected because some rows produce more tokens. The run remains a tiny n=10 calibration and does not support final speed or quality claims.

## Remaining Issues

- 2/10 rows remain numeric failures in both compressed conditions.
- 1/10 rows still hit the 256-token cap in both compressed conditions.
- One persistent failure extracts `50` for expected answer `5`, suggesting prompt/extraction or compression-sensitive reasoning still needs review.
- One persistent cap-hit row still does not emit a correct final answer even at 256 tokens.

## Decision

Use `max_new_tokens=256` for compressed GSM8K calibration by default until a later report supersedes it. Do not increase beyond 256 without inspecting the remaining failures.

Test a tiny gentler keep-rate next, starting with `keep_rate=0.67`; only test `0.8` if 0.67 still leaves evidence of compression-related failures.

## Outputs

- `scripts/phase_1_analysis/analyze_task60_mnt256_calibration.py`
- `tests/test_task60_mnt256_calibration.py`
- `results/task60_gsm8k_short_llmlingua_ar_r2_n10_mnt256_suffixfix.jsonl`
- `results/task60_gsm8k_short_cc_dflash_r2_n10_mnt256_suffixfix.jsonl`
- `results/task60_mnt256_calibration_summary.json`
- `results/task60_mnt256_calibration_table.csv`
- `results/task60_mnt256_changed_outcomes.jsonl`

## Validation

- Focused analyzer test: `1 passed`
- Prompt dry-run: `DRY-RUN-PASS`
- Direct prompt instruction assertion: PASS
- Row counts: 10 rows for both Task 60 artifacts
- Metadata check: suffix preserved, tail preview present, question preserved, generated text present, and compression metadata present for both artifacts
- JSON summary validation: PASS

Full compile/test/doc validation is recorded in the final task response.

## Next Recommendation

Task 61 should run a tiny compressed-only GSM8K keep-rate calibration at `max_new_tokens=256`, starting with `keep_rate=0.67`, before any larger n or QMSum run.
