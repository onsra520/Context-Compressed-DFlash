# Task 64 — Cap-Hit Triage on Task 63 GSM8K n=30 Results

Date: 2026-06-12

Status: PASS, read-only analysis

## Scope

Task 64 analyzes Task 63 compressed GSM8K n=30 result artifacts to identify numeric failures, token-cap hits, and the overlap between them.

This task did not run benchmarks, load models, load compressors, use CUDA, overwrite artifacts, or modify Task 63 JSONL files.

## Inputs

| Input | Purpose |
|---|---|
| `results/phase_1_system_build_and_evaluation/early_experiments/task63_gsm8k_short_llmlingua_ar_r2_n30_mnt256.jsonl` | Task 63 LLMLingua-AR-R2 n=30 artifact |
| `results/phase_1_system_build_and_evaluation/early_experiments/task63_gsm8k_short_cc_dflash_r2_n30_mnt256.jsonl` | Task 63 CC-DFlash-R2 n=30 artifact |
| `data/eval/gsm8k_100.jsonl` | Dataset metadata |

## Outputs

| Output | Description |
|---|---|
| `scripts/phase_1_system_build_and_evaluation/analysis/t64_cap_hit_triage.py` | Read-only cap-hit/failure triage analyzer |
| `tests/test_task64_cap_hit_triage.py` | Lightweight CPU-only analyzer test |
| `results/phase_1_system_build_and_evaluation/early_experiments/task64_cap_hit_triage_summary.json` | Machine-readable triage summary |
| `results/phase_1_system_build_and_evaluation/early_experiments/task64_cap_hit_cases.jsonl` | Per-case triage rows |

## Per-Condition Summary

| Condition | Total rows | Numeric matches | Numeric failures | Cap hits | Cap-hit failures | Non-cap failures |
|---|---:|---:|---:|---:|---:|---:|
| LLMLingua-AR-R2 | 30 | 22 | 8 | 5 | 5 | 3 |
| CC-DFlash-R2 | 30 | 23 | 7 | 5 | 4 | 3 |

## Label Counts

| Label | LLMLingua-AR-R2 | CC-DFlash-R2 | Total |
|---|---:|---:|---:|
| `TRUNCATION_DOMINANT` | 5 | 5 | 10 |
| `REASONING_FAIL` | 3 | 3 | 6 |
| `COMPRESSION_LOSS_POSSIBLE` | 0 | 0 | 0 |
| `EXTRACTION_ISSUE` | 0 | 0 | 0 |
| `UNCLEAR` | 0 | 0 | 0 |

The analyzer uses conservative rules. It only marks `COMPRESSION_LOSS_POSSIBLE` when compressed previews visibly omit multiple numeric tokens from the original question, and this did not occur in the Task 63 failure/cap-hit rows.

## Representative TRUNCATION_DOMINANT Examples

| Condition | Dataset row | Expected | Extracted | Evidence |
|---|---|---:|---:|---|
| LLMLingua-AR-R2 | `gsm8k_short_test_0082` | 6 | 2 | Hit 256-token cap, no final-answer marker, reasoning still in progress |
| LLMLingua-AR-R2 | `gsm8k_short_test_0076` | 4400 | 2400 | Hit cap while still enumerating movie-replacement cost components |
| LLMLingua-AR-R2 | `gsm8k_short_test_0098` | 1,600 | 1200 | Hit cap while still solving lumber/stick yield reasoning |
| LLMLingua-AR-R2 | `gsm8k_short_test_0028` | 18 | 2 | Hit cap while still reconstructing the vacuum-cleaner equation |

CC-DFlash-R2 has the same five cap-hit rows; four are numeric failures and one cap-hit row is still numerically correct.

## Representative REASONING_FAIL Examples

| Condition | Dataset row | Expected | Extracted | Evidence |
|---|---|---:|---:|---|
| LLMLingua-AR-R2 | `gsm8k_short_test_0015` | 5 | 50 | Output completes with a final-answer marker but gives the wrong daily duck-food value |
| LLMLingua-AR-R2 | `gsm8k_short_test_0089` | 170 | 140 | Output completes with final-answer marker but miscomputes land-sale total |
| LLMLingua-AR-R2 | `gsm8k_short_test_0001` | 2280 | 2180 | Output completes with final-answer marker but sums fundraiser amounts incorrectly |
| CC-DFlash-R2 | `gsm8k_short_test_0015` | 5 | 50 | Same completed wrong final answer pattern |

These are not solved by simply increasing the token cap unless the wrong final answers are downstream effects of earlier compressed reasoning drift. The artifacts do not provide enough evidence to claim compression loss.

## Theoretical Upper Bound

If every cap-hit failure became correct, the projected numeric accuracy would be:

| Condition | Current numeric matches | Cap-hit failures | Theoretical upper bound |
|---|---:|---:|---:|
| LLMLingua-AR-R2 | 22/30 | 5 | 27/30 |
| CC-DFlash-R2 | 23/30 | 4 | 27/30 |

This is a theoretical upper bound only, not a benchmark result. It assumes every cap-hit failure would become correct with a larger token budget, which may not hold.

## Recommendation

Choose option A: run a tiny Task 65 calibration with:

- `n=10`
- `max_new_tokens=384`
- GSM8K only
- compressed conditions only
- default R2 keep rate
- `--resume`
- generated text stored

Reason: cap-hit failures dominate the remaining loss pattern, and a tiny 384-token-cap run can test whether cap-hit rows finish cleanly before any n=100 move.

Do not run n=100 yet. Do not change keep rate. Do not claim final correctness.

## Validation

- Focused analyzer test: PASS
- Analyzer real artifact run: PASS
- Summary JSON validation: PASS
- No benchmark/model/compressor/CUDA execution was performed.

Full validation command output is recorded in the final response.
