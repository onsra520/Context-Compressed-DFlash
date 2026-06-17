# Task 59: Tiny Compressed GSM8K Suffix Verification Rerun

Date: 2026-06-12

Status: PASS, preliminary compressed-only verification

## Scope

Task 59 ran a tiny real GSM8K compressed-only rerun to verify that the Task 58 protected final-answer suffix survives in actual compressed artifacts.

This is not a final benchmark, not an n=100 run, and not a final correctness or speedup claim. QMSum was not run.

Task 58 commit verified before this task:

- `ba86c44 fix: protect gsm8k final-answer suffix`

## Commands Run

- `PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --prompt-source dataset --dataset gsm8k_short --n 3 --seed 42 --dry-run-prompts`
- Direct prompt-content assertion for `Final answer: <number>` in three selected GSM8K prompts.
- `PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --prompt-source dataset --dataset gsm8k_short --condition LLMLingua-AR-R2 --n 10 --seed 42 --max-new-tokens 192 --output results/task59_gsm8k_short_llmlingua_ar_r2_n10_mnt192_suffixfix.jsonl --resume --store-generated-text`
- `PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --prompt-source dataset --dataset gsm8k_short --condition CC-DFlash-R2 --n 10 --seed 42 --max-new-tokens 192 --output results/task59_gsm8k_short_cc_dflash_r2_n10_mnt192_suffixfix.jsonl --resume --store-generated-text`
- `PYTHONPATH=src .venv/bin/python scripts/phase_1_analysis/analyze_task59_suffix_verification.py`

## Run Completion

| Condition | Artifact | Rows | Resume | max_new_tokens | Status |
| --- | --- | ---: | --- | ---: | --- |
| LLMLingua-AR-R2 | `results/task59_gsm8k_short_llmlingua_ar_r2_n10_mnt192_suffixfix.jsonl` | 10 | `--resume` | 192 | PASS |
| CC-DFlash-R2 | `results/task59_gsm8k_short_cc_dflash_r2_n10_mnt192_suffixfix.jsonl` | 10 | `--resume` | 192 | PASS |

No old result artifact was overwritten. Task 56 artifacts were read only by the analyzer.

## Metadata Survival Summary

| Condition | Rows | `protected_suffix_preserved` | Tail preview has instruction | Final prompt preview has instruction | Metadata complete rows | Question preserved |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| LLMLingua-AR-R2 | 10 | 10 | 10 | 10 | 10 | 10 |
| CC-DFlash-R2 | 10 | 10 | 10 | 10 | 10 | 10 |

The protected suffix now survives in compressed artifacts. The fields proving this are:

- `protected_suffix_preserved`
- `protected_suffix_preview`
- `final_prompt_preview`
- `final_prompt_tail_preview`
- `compressed_prompt_preview`
- `question_preserved`

Compression audit metadata also includes:

- `original_input_tokens`
- `compressed_input_tokens`
- `compression_ratio`
- `actual_compression_ratio`
- `t_compress_ms`
- `keep_rate`

## Task 56 vs Task 59 Comparison

| Condition | Stage | Rows | Suffix preserved | Generated `Final answer:` marker | Numeric extraction matches | Exact containment | Hit max token cap | Avg output tokens | Avg e2e time (s) | Avg `T_compress` (ms) |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| LLMLingua-AR-R2 | Task 56 before suffix fix | 10 | 0 | 0 | 3 | 4 | 8 | 189.4 | 16.06 | 1190.12 |
| LLMLingua-AR-R2 | Task 59 after suffix fix | 10 | 10 | 7 | 6 | 8 | 3 | 139.6 | 8.24 | 810.95 |
| CC-DFlash-R2 | Task 56 before suffix fix | 10 | 0 | 0 | 3 | 4 | 9 | 189.5 | 4.98 | 989.07 |
| CC-DFlash-R2 | Task 59 after suffix fix | 10 | 10 | 7 | 7 | 9 | 3 | 144.4 | 2.93 | 753.97 |

Delta summary:

| Condition | Suffix preserved delta | Generated marker delta | Numeric extraction delta | Hit cap delta |
| --- | ---: | ---: | ---: | ---: |
| LLMLingua-AR-R2 | +10 | +7 | +3 | -5 |
| CC-DFlash-R2 | +10 | +7 | +4 | -6 |

## Interpretation

The Task 58 fix worked for the artifact contract: the protected final-answer suffix is visible in all Task 59 compressed rows, including prompt-tail preview evidence.

Compressed conditions also emitted strict `Final answer:` markers in 7/10 rows each. Numeric extraction improved from 3/10 to 6/10 for LLMLingua-AR-R2 and from 3/10 to 7/10 for CC-DFlash-R2.

This suggests the missing protected suffix was a real quality-path blocker. It does not prove final correctness, and it does not prove compression is useful end-to-end.

## Remaining Issues

- 3/10 rows in each compressed condition still did not emit a parseable final-answer marker.
- 3/10 rows in each compressed condition still hit the 192-token cap.
- Some failures may still be due to output length, compression loss, or prompt format.
- This remains a tiny n=10 GSM8K calibration only.

## Whether `max_new_tokens=256` Is Still Needed

Yes, but only as a targeted follow-up. Because 3/10 rows still hit the 192-token cap, a tiny compressed-only calibration with `max_new_tokens=256` is reasonable before larger n.

## Whether `keep_rate=0.67/0.8` Should Be Tested

Yes, but after confirming the 256-token cap result. The suffix survival issue is fixed, so a gentler keep-rate test can now diagnose whether the remaining compressed failures are compression-loss-related rather than prompt-policy-related.

## Outputs

- `scripts/phase_1_analysis/analyze_task59_suffix_verification.py`
- `tests/test_task59_suffix_verification.py`
- `results/task59_gsm8k_short_llmlingua_ar_r2_n10_mnt192_suffixfix.jsonl`
- `results/task59_gsm8k_short_cc_dflash_r2_n10_mnt192_suffixfix.jsonl`
- `results/task59_suffix_verification_summary.json`
- `results/task59_suffix_verification_table.csv`

## Validation

- Focused analyzer test: `1 passed`
- Prompt dry-run: `DRY-RUN-PASS`
- Direct prompt instruction assertion: PASS
- Row counts: 10 rows for both Task 59 artifacts
- Metadata check: suffix preserved, tail preview present, question preserved, generated text present, and compression metadata present for both artifacts
- JSON summary validation: PASS

Full compile/test/doc validation is recorded in the final task response.

## Next Recommendation

Task 60 should run a tiny compressed-only GSM8K quality calibration with the suffix fix in place, likely testing `max_new_tokens=256` first. If marker generation and numeric extraction remain incomplete, test gentler keep rates such as `0.67` or `0.8` before any larger n.
