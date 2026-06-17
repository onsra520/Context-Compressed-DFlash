# Task 63 — GSM8K n=30 Stability Verification

Date: 2026-06-12

Status: PASS, preliminary

## Scope

Task 63 evaluates whether the Task 60 compressed GSM8K calibration remains directionally stable when increasing from n=10 to n=30.

This task used the Task 60 methodology unchanged:

- Dataset: `gsm8k_short`
- Conditions: `LLMLingua-AR-R2`, `CC-DFlash-R2`
- Default R2 keep rate: `0.50`
- `max_new_tokens=256`
- Protected final-answer suffix enabled
- `--resume`
- Generated text stored

No QMSum run, no n=100 run, no keep-rate override, and no prompt/compression/extraction logic change were performed.

## Commands Run

LLMLingua-AR-R2:

`PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --prompt-source dataset --dataset gsm8k_short --condition LLMLingua-AR-R2 --n 30 --seed 42 --max-new-tokens 256 --resume --store-generated-text --output results/task63_gsm8k_short_llmlingua_ar_r2_n30_mnt256.jsonl`

CC-DFlash-R2:

`PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --prompt-source dataset --dataset gsm8k_short --condition CC-DFlash-R2 --n 30 --seed 42 --max-new-tokens 256 --resume --store-generated-text --output results/task63_gsm8k_short_cc_dflash_r2_n30_mnt256.jsonl`

Analyzer:

`PYTHONPATH=src .venv/bin/python scripts/analyze_task63_n30_stability.py`

## Artifacts

| Artifact | Rows | Status |
|---|---:|---|
| `results/task63_gsm8k_short_llmlingua_ar_r2_n30_mnt256.jsonl` | 30 | Created |
| `results/task63_gsm8k_short_cc_dflash_r2_n30_mnt256.jsonl` | 30 | Created |
| `results/task63_n30_stability_summary.json` | 1 summary | Created |
| `results/task63_n30_stability_table.csv` | 4 condition-stage rows | Created |

## Quality Summary

| Condition | Stage | Rows | Numeric matches | Numeric rate | Exact containment | Final-answer markers | Hit cap |
|---|---|---:|---:|---:|---:|---:|---:|
| LLMLingua-AR-R2 | Task 60 n=10 | 10 | 8 | 0.800 | 10 | 8 | 1 |
| LLMLingua-AR-R2 | Task 63 n=30 | 30 | 22 | 0.733 | 24 | 24 | 5 |
| CC-DFlash-R2 | Task 60 n=10 | 10 | 8 | 0.800 | 10 | 9 | 1 |
| CC-DFlash-R2 | Task 63 n=30 | 30 | 23 | 0.767 | 25 | 25 | 5 |

The analyzer uses a conservative ±10 percentage point margin around the Task 60 numeric extraction rate. Under that rule:

- LLMLingua-AR-R2: `STABLE`
- CC-DFlash-R2: `STABLE`

Both conditions are stable relative to Task 60, but the n=30 run exposes more token-cap hits: 5/30 for both compressed conditions.

## Latency Summary

| Condition | Stage | Avg generation latency (s) | Avg e2e latency (s) | Avg t_compress_ms | Generation tok/s weighted | E2E tok/s weighted |
|---|---|---:|---:|---:|---:|---:|
| LLMLingua-AR-R2 | Task 60 n=10 | 8.98 | 9.93 | 951.91 | 16.86 | 15.24 |
| LLMLingua-AR-R2 | Task 63 n=30 | 8.65 | 9.44 | 791.02 | 17.98 | 16.47 |
| CC-DFlash-R2 | Task 60 n=10 | 2.62 | 3.51 | 893.97 | 59.22 | 44.14 |
| CC-DFlash-R2 | Task 63 n=30 | 2.86 | 3.67 | 810.56 | 55.55 | 43.30 |

Latency values are smoke-level and should not be used as final speedup claims.

## Stability Decision

| Condition | Numeric rate delta vs Task 60 | Classification | Rationale |
|---|---:|---|---|
| LLMLingua-AR-R2 | -0.067 | STABLE | Within ±0.10 of Task 60, but cap hits increased |
| CC-DFlash-R2 | -0.033 | STABLE | Within ±0.10 of Task 60, but cap hits increased |

## Interpretation

The Task 60 compressed quality signal remains directionally stable at n=30 under the existing methodology and default R2 keep rate. However, stability is not the same as final quality. The n=30 run reveals persistent output-length risk, with 5/30 rows hitting the token cap for each compressed condition.

Because cap hits increased, the next step should not be n=100. A focused n=30 failure/cap triage should identify whether the remaining failures are truncation, arithmetic/model failures, extraction misses, or compression evidence loss.

## Recommendation

- Keep default R2 keep rate at `0.50`.
- Do not test `keep_rate=0.80` next.
- Do not proceed to n=100 yet.
- Recommended next task: Task 64 n=30 compressed GSM8K failure and cap-hit triage.

## Validation

- Focused analyzer test: PASS
- LLMLingua-AR-R2 n=30 run: PASS, 30 rows
- CC-DFlash-R2 n=30 run: PASS, 30 rows
- Analyzer run: PASS
- JSON summary validation: PASS

Full compile/test/doc validation is recorded in the final task response.
