# Task 53 — GSM8K Quality Calibration Report

Date: 2026-06-11

Status: PASS, preliminary calibration

## Scope

Task 53 reran only `gsm8k_short` at `n=10` with `max_new_tokens=128` to test whether the weak Task 51 GSM8K quality under `max_new_tokens=32` was mainly truncation-related.

No QMSum run was performed. No n=100 run was performed. Existing result artifacts were not overwritten.

Task 52 was already committed before this task:

- `86ef280 test: summarize two-dataset smoke metrics`

## Commands Run

Baseline-AR:

```bash
PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --prompt-source dataset --dataset gsm8k_short --condition Baseline-AR --n 10 --seed 42 --max-new-tokens 128 --output results/task53_gsm8k_short_baseline_ar_n10_mnt128.jsonl --resume --store-generated-text
```

DFlash-R1:

```bash
PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --prompt-source dataset --dataset gsm8k_short --condition DFlash-R1 --n 10 --seed 42 --max-new-tokens 128 --output results/task53_gsm8k_short_dflash_r1_n10_mnt128.jsonl --resume --store-generated-text
```

LLMLingua-AR-R2:

```bash
PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --prompt-source dataset --dataset gsm8k_short --condition LLMLingua-AR-R2 --n 10 --seed 42 --max-new-tokens 128 --output results/task53_gsm8k_short_llmlingua_ar_r2_n10_mnt128.jsonl --resume --store-generated-text
```

CC-DFlash-R2:

```bash
PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --prompt-source dataset --dataset gsm8k_short --condition CC-DFlash-R2 --n 10 --seed 42 --max-new-tokens 128 --output results/task53_gsm8k_short_cc_dflash_r2_n10_mnt128.jsonl --resume --store-generated-text
```

Analyzer:

```bash
PYTHONPATH=src .venv/bin/python scripts/phase_1_analysis/analyze_task53_gsm8k_quality.py
```

## Run Completion

| Condition | Artifact | Rows | Status |
| --- | --- | ---: | --- |
| Baseline-AR | `results/task53_gsm8k_short_baseline_ar_n10_mnt128.jsonl` | 10 | PASS |
| DFlash-R1 | `results/task53_gsm8k_short_dflash_r1_n10_mnt128.jsonl` | 10 | PASS |
| LLMLingua-AR-R2 | `results/task53_gsm8k_short_llmlingua_ar_r2_n10_mnt128.jsonl` | 10 | PASS |
| CC-DFlash-R2 | `results/task53_gsm8k_short_cc_dflash_r2_n10_mnt128.jsonl` | 10 | PASS |

All real runs used `--resume`, unique Task 53 output filenames, and `--store-generated-text`. No `--overwrite` was used.

## Quality Comparison

| Stage | Condition | Rows | max_new_tokens | Exact containment | Numeric extraction match | Truncated / stopped early | Avg output tokens |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Task 51 | Baseline-AR | 10 | 32 | 2 | 0 | 10 | 32.0 |
| Task 51 | DFlash-R1 | 10 | 32 | 2 | 0 | 10 | 32.0 |
| Task 51 | LLMLingua-AR-R2 | 10 | 32 | 3 | 1 | 10 | 32.0 |
| Task 51 | CC-DFlash-R2 | 10 | 32 | 3 | 1 | 10 | 32.0 |
| Task 53 | Baseline-AR | 10 | 128 | 5 | 2 | 10 | 120.7 |
| Task 53 | DFlash-R1 | 10 | 128 | 5 | 2 | 10 | 120.7 |
| Task 53 | LLMLingua-AR-R2 | 10 | 128 | 3 | 0 | 10 | 128.0 |
| Task 53 | CC-DFlash-R2 | 10 | 128 | 3 | 0 | 10 | 128.0 |

## Latency Impact

| Stage | Condition | Avg generation time s | Avg e2e time s | Gen tok/s | E2E tok/s | Avg T_compress ms |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Task 51 | Baseline-AR | 1.92 | 1.92 | 16.72 | 16.70 | 0.00 |
| Task 51 | DFlash-R1 | 0.83 | 0.83 | 40.85 | 38.46 | 0.00 |
| Task 51 | LLMLingua-AR-R2 | 1.99 | 2.76 | 16.17 | 11.60 | 771.69 |
| Task 51 | CC-DFlash-R2 | 0.74 | 1.48 | 45.61 | 21.64 | 735.00 |
| Task 53 | Baseline-AR | 6.87 | 6.87 | 17.58 | 17.57 | 0.00 |
| Task 53 | DFlash-R1 | 2.34 | 2.34 | 52.89 | 51.53 | 0.00 |
| Task 53 | LLMLingua-AR-R2 | 7.10 | 8.01 | 18.05 | 15.97 | 915.67 |
| Task 53 | CC-DFlash-R2 | 2.31 | 3.11 | 57.47 | 41.19 | 801.98 |

Increasing `max_new_tokens` to 128 increased generation time by about 2.8–3.6× depending on condition. CC-DFlash-R2 still had higher generation-only and e2e tok/s than the AR conditions, but this remains a small n=10 calibration, not a final speedup claim.

## Interpretation

- `max_new_tokens=32` was likely too short for GSM8K-style answer extraction.
- `max_new_tokens=128` improved uncompressed Baseline-AR and DFlash-R1 exact containment from 2/10 to 5/10 and numeric extraction from 0/10 to 2/10.
- `max_new_tokens=128` did not improve LLMLingua-AR-R2 or CC-DFlash-R2 extraction in this n=10 sample; both stayed at 3/10 exact containment and moved from 1/10 to 0/10 numeric extraction matches.
- All Task 53 rows still triggered the truncation / stopped-early heuristic, mostly because outputs often reached the 128-token cap. This means 128 is safer than 32 but not conclusively sufficient.
- Compressed-condition quality needs focused prompt/compression triage before larger GSM8K quality runs.

## Conservative Next-Run Recommendation

Do not expand directly to n=100 from this calibration.

Recommended next task:

1. Inspect compressed GSM8K failures manually or with targeted failure samples.
2. Decide whether prompt formatting should require a short final-answer line.
3. Consider a tiny `max_new_tokens=192` or `256` calibration only after reviewing whether the remaining misses are truncation, compression loss, or answer-extraction limitations.
4. Keep DFlash-R1 as the clean speed/control baseline.

## Validation

Commands run:

- `PYTHONPATH=src .venv/bin/python scripts/phase_1_analysis/analyze_task53_gsm8k_quality.py`
- `python3 -m json.tool results/task53_gsm8k_quality_calibration_summary.json`
- `python3 -m compileall src tests scripts 2>&1 | tail -20`
- `PYTHONPATH=src .venv/bin/python -m pytest tests/ -x -q 2>&1 | tail -30`
- `find docs -name "*.html" -exec grep -L "<!DOCTYPE html>" {} \;`
- `find docs -name "*.html" -exec grep -L "</html>" {} \;`
- Markdown fence balance for `instruction.md` and this report

Validation results are recorded in the final task response.

## Understand-Anything

`.understand-anything/meta.json` was read before task completion. `/understand` refresh was skipped because `/understand` is not available in this environment.
