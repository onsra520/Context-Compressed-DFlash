# Task 56 — GSM8K Final-Answer Calibration Report

Date: 2026-06-11

Status: PASS, preliminary calibration

## Scope

Task 56 reran only `gsm8k_short` at `n=10` with `max_new_tokens=192` after Task 55 added the strict GSM8K final-answer prompt policy and compressed-prompt audit metadata.

This task did not run QMSum, did not run `n=100`, did not overwrite old artifacts, and does not make a final correctness or speedup claim.

Task 55 was already committed before this task:

- `1ade36a fix: enforce gsm8k final answer extraction`

## Commands Run

Prompt dry-run:

```bash
PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --prompt-source dataset --dataset gsm8k_short --n 3 --seed 42 --dry-run-prompts
```

Baseline-AR:

```bash
PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --prompt-source dataset --dataset gsm8k_short --condition Baseline-AR --n 10 --seed 42 --max-new-tokens 192 --output results/task56_gsm8k_short_baseline_ar_n10_mnt192.jsonl --resume --store-generated-text
```

DFlash-R1:

```bash
PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --prompt-source dataset --dataset gsm8k_short --condition DFlash-R1 --n 10 --seed 42 --max-new-tokens 192 --output results/task56_gsm8k_short_dflash_r1_n10_mnt192.jsonl --resume --store-generated-text
```

LLMLingua-AR-R2:

```bash
PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --prompt-source dataset --dataset gsm8k_short --condition LLMLingua-AR-R2 --n 10 --seed 42 --max-new-tokens 192 --output results/task56_gsm8k_short_llmlingua_ar_r2_n10_mnt192.jsonl --resume --store-generated-text
```

CC-DFlash-R2:

```bash
PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --prompt-source dataset --dataset gsm8k_short --condition CC-DFlash-R2 --n 10 --seed 42 --max-new-tokens 192 --output results/task56_gsm8k_short_cc_dflash_r2_n10_mnt192.jsonl --resume --store-generated-text
```

Analyzer:

```bash
PYTHONPATH=src .venv/bin/python scripts/analyze_task56_gsm8k_final_answer_calibration.py
```

## Run Completion

| Condition | Artifact | Rows | Status |
| --- | --- | ---: | --- |
| Baseline-AR | `results/task56_gsm8k_short_baseline_ar_n10_mnt192.jsonl` | 10 | PASS |
| DFlash-R1 | `results/task56_gsm8k_short_dflash_r1_n10_mnt192.jsonl` | 10 | PASS |
| LLMLingua-AR-R2 | `results/task56_gsm8k_short_llmlingua_ar_r2_n10_mnt192.jsonl` | 10 | PASS |
| CC-DFlash-R2 | `results/task56_gsm8k_short_cc_dflash_r2_n10_mnt192.jsonl` | 10 | PASS |

All real runs used `--resume`, unique Task 56 output filenames, and `--store-generated-text`. No `--overwrite` was used.

## Task 53 vs Task 56 Quality Comparison

| Stage | Condition | Rows | max_new_tokens | Exact containment | Numeric extraction match | Final-answer marker present | Final-answer parse success | Hit token cap |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Task 53 | Baseline-AR | 10 | 128 | 5 | 2 | 2 | 2 | 8 |
| Task 53 | DFlash-R1 | 10 | 128 | 5 | 2 | 2 | 2 | 8 |
| Task 53 | LLMLingua-AR-R2 | 10 | 128 | 3 | 0 | 0 | 0 | 10 |
| Task 53 | CC-DFlash-R2 | 10 | 128 | 3 | 0 | 0 | 0 | 10 |
| Task 56 | Baseline-AR | 10 | 192 | 8 | 6 | 7 | 7 | 3 |
| Task 56 | DFlash-R1 | 10 | 192 | 9 | 8 | 8 | 8 | 2 |
| Task 56 | LLMLingua-AR-R2 | 10 | 192 | 4 | 3 | 0 | 0 | 8 |
| Task 56 | CC-DFlash-R2 | 10 | 192 | 4 | 3 | 0 | 0 | 9 |

## Latency and Efficiency

| Stage | Condition | Avg output tokens | Avg generation time s | Avg e2e time s | Gen tok/s | E2E tok/s | Avg T_compress ms | Avg tau_mean |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Task 56 | Baseline-AR | 143.90 | 11.12 | 11.12 | 12.92 | 12.95 | 0.00 | 0.00 |
| Task 56 | DFlash-R1 | 139.20 | 3.23 | 3.23 | 44.01 | 43.12 | 0.00 | 5.20 |
| Task 56 | LLMLingua-AR-R2 | 189.40 | 14.87 | 16.06 | 12.95 | 11.79 | 1190.12 | 0.00 |
| Task 56 | CC-DFlash-R2 | 189.50 | 3.99 | 4.98 | 48.73 | 38.07 | 989.07 | 5.84 |

These latency values are calibration-only. They should not be read as final speedup evidence.

## Compression Audit Metadata

Compressed Task 56 artifacts contain the new audit metadata on every row:

| Condition | Complete metadata rows | Complete rate | Question preserved |
| --- | ---: | ---: | --- |
| LLMLingua-AR-R2 | 10 / 10 | 1.00 | true |
| CC-DFlash-R2 | 10 / 10 | 1.00 | true |

Fields present include `keep_rate`, `t_compress_ms`, `N_original`, `N_compressed`, `R_actual`, `original_input_tokens`, `compressed_input_tokens`, `compression_ratio`, `actual_compression_ratio`, `question_preserved`, `original_context_preview`, `compressed_context_preview`, `original_prompt_preview`, and `compressed_prompt_preview`.

## Interpretation

- `max_new_tokens=192` reduced token-cap hits for uncompressed rows: Baseline-AR dropped from 8/10 cap hits to 3/10, and DFlash-R1 dropped from 8/10 to 2/10.
- Uncompressed quality improved under the strict final-answer prompt: Baseline-AR numeric extraction rose from 2/10 to 6/10, and DFlash-R1 rose from 2/10 to 8/10.
- Compressed quality improved modestly: LLMLingua-AR-R2 and CC-DFlash-R2 rose from 0/10 to 3/10 numeric extraction matches.
- Compressed rows still did not emit the strict `Final answer:` marker in this sample, and most compressed rows still reached the 192-token cap.
- The new compressed metadata is sufficient for direct prompt/context preview triage in a follow-up task.
- CC-DFlash-R2 remains faster than LLMLingua-AR-R2 in generation and approximate end-to-end time in this tiny calibration, but this is not a final speedup claim.

## Conservative Next-Run Recommendation

Do not expand directly to `n=100`.

Recommended next task:

1. Inspect compressed prompt/context previews for the failed compressed rows to separate prompt-format failure from compression-loss risk.
2. Consider a tiny `max_new_tokens=256` calibration only if the compressed rows are still clearly truncation-dominated after preview inspection.
3. Consider a gentler compressed GSM8K keep rate such as `0.67` or `0.8` if preview inspection suggests answer-critical numbers or relations are being dropped.
4. Proceed to `n=30` only after the final-answer marker and numeric extraction path are stable enough for the target condition set.

## Validation

Validation commands and results are recorded in the final task response.

## Understand-Anything

`.understand-anything/meta.json` was read before task work. `/understand` refresh was skipped because `/understand` is not available in this environment.
