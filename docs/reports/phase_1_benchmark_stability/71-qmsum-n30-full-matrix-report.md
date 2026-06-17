# Task 71 - QMSum n=30 Long-Context Diagnostic Full Matrix

Date: 2026-06-13

## Result

PASS_WITH_NOTES

Task 71 ran a fresh QMSum-style long-context n=30 diagnostic full matrix with `max_new_tokens=384`, `--resume`, and generated-text storage. This is preliminary diagnostic evidence only. It is not a final speedup, final correctness, or production-readiness claim.

Task 70 commit: `62024ef test: audit qmsum diagnostic artifacts`

## Commands Run

Prompt dry-run:

```bash
PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --prompt-source dataset --dataset qmsum_meeting_qa_long --n 3 --seed 42 --dry-run-prompts
```

Real runs:

```bash
PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --prompt-source dataset --dataset qmsum_meeting_qa_long --condition Baseline-AR --n 30 --seed 42 --max-new-tokens 384 --output results/task71_qmsum_long_baseline_ar_n30_mnt384.jsonl --resume --store-generated-text
PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --prompt-source dataset --dataset qmsum_meeting_qa_long --condition DFlash-R1 --n 30 --seed 42 --max-new-tokens 384 --output results/task71_qmsum_long_dflash_r1_n30_mnt384.jsonl --resume --store-generated-text
PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --prompt-source dataset --dataset qmsum_meeting_qa_long --condition LLMLingua-AR-R2 --n 30 --seed 42 --max-new-tokens 384 --output results/task71_qmsum_long_llmlingua_ar_r2_n30_mnt384.jsonl --resume --store-generated-text
PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --prompt-source dataset --dataset qmsum_meeting_qa_long --condition CC-DFlash-R2 --n 30 --seed 42 --max-new-tokens 384 --output results/task71_qmsum_long_cc_dflash_r2_n30_mnt384.jsonl --resume --store-generated-text
```

Analyzer:

```bash
PYTHONPATH=src .venv/bin/python scripts/phase_1_analysis/analyze_task71_qmsum_n30_full_matrix.py
```

## Run Completion

| Condition | Artifact | Rows | Status |
|---|---|---:|---|
| Baseline-AR | `results/task71_qmsum_long_baseline_ar_n30_mnt384.jsonl` | 30 | PASS |
| DFlash-R1 | `results/task71_qmsum_long_dflash_r1_n30_mnt384.jsonl` | 30 | PASS |
| LLMLingua-AR-R2 | `results/task71_qmsum_long_llmlingua_ar_r2_n30_mnt384.jsonl` | 30 | PASS |
| CC-DFlash-R2 | `results/task71_qmsum_long_cc_dflash_r2_n30_mnt384.jsonl` | 30 | PASS |

All real runs used `--resume`, `--store-generated-text`, unique Task 71 output filenames, and no `--overwrite`.

## Quality Proxy Table

QMSum-style quality is measured only with normalized answer containment and answer-token overlap proxies. It is not semantic correctness.

| Condition | Rows | Avg answer-token overlap | Containment | Empty | Repetition | Hit cap |
|---|---:|---:|---:|---:|---:|---:|
| Baseline-AR | 30 | 0.232963 | 0/30 | 0 | 0 | 0 |
| DFlash-R1 | 30 | 0.233699 | 0/30 | 0 | 0 | 0 |
| LLMLingua-AR-R2 | 30 | 0.358644 | 0/30 | 0 | 0 | 22 |
| CC-DFlash-R2 | 30 | 0.357483 | 0/30 | 0 | 0 | 21 |

The compressed conditions have higher token-overlap proxy values than uncompressed conditions, but they also hit the 384-token cap frequently. That means the proxy is useful for diagnosis, not a final quality decision.

## Latency and Speed Table

| Condition | Avg generation s | Avg e2e s | Gen tok/s | E2E tok/s | Avg T_compress ms | Avg T_prefill ms | Avg tau |
|---|---:|---:|---:|---:|---:|---:|---:|
| Baseline-AR | 4.264 | 4.264 | 14.45 | 14.45 | 0.00 | 687.44 | 0.00 |
| DFlash-R1 | 3.097 | 3.097 | 19.54 | 19.54 | 0.00 | 655.74 | 2.61 |
| LLMLingua-AR-R2 | 20.802 | 26.378 | 16.75 | 13.21 | 5576.04 | 375.31 | 0.00 |
| CC-DFlash-R2 | 13.127 | 19.056 | 26.31 | 18.12 | 5928.33 | 388.17 | 2.76 |

## Compression Summary

| Condition | Avg original input tokens | Avg compressed input tokens | Avg compression ratio | Compression metadata |
|---|---:|---:|---:|---|
| LLMLingua-AR-R2 | 1950.43 | 943.50 | 2.0669 | 30/30 rows |
| CC-DFlash-R2 | 1950.43 | 943.50 | 2.0669 | 30/30 rows |

Average compression overhead was about `5.58s` for LLMLingua-AR-R2 and `5.93s` for CC-DFlash-R2.

## Comparisons

- Baseline-AR vs DFlash-R1: DFlash-R1 improved e2e tok/s by about `1.35x` with nearly identical overlap proxy.
- LLMLingua-AR-R2 vs CC-DFlash-R2: CC-DFlash-R2 improved e2e tok/s by about `1.37x` and generation tok/s by about `1.57x`.
- CC-DFlash-R2 proxy quality matched LLMLingua-AR-R2 within the configured overlap tolerance: overlap delta `-0.001161`.
- Compressed conditions had much higher output lengths and overlap proxy, but also high cap pressure.

## max_new_tokens=384 Assessment

Task 70/Task 51 QMSum rows had average cap-hit rate `0.975` with `max_new_tokens=32`.

Task 71 average cap-hit rate fell to `0.358333` with `max_new_tokens=384`, so the old 32-token cap problem was improved. It was not fully fixed: compressed conditions still hit the cap in 21-22 of 30 rows.

## GSM8K-Style Failure Assessment

QMSum does not show a GSM8K-style arithmetic failure pattern because it is not a math dataset. It is better interpreted as a long-context output-length, overlap, prefill, and compression-overhead diagnostic.

## n=100 Decision

QMSum n=100 is not justified as the immediate next step. Although the n=30 matrix completed successfully and CC-DFlash-R2 beat LLMLingua-AR-R2 on e2e speed while matching proxy quality, the high compressed-condition cap-hit rate means output-length policy still needs interpretation.

Recommended next step:

- Task 72 should audit/triage QMSum cap-hit rows and long-answer proxy behavior from Task 71.
- Do not jump directly to QMSum n=100.
- Keep claims preliminary and separate QMSum proxy quality from semantic correctness.

## Validation

Task-specific validation:

- `PYTHONPATH=src .venv/bin/python -m pytest tests/test_task71_qmsum_n30_full_matrix.py -q`
- `PYTHONPATH=src .venv/bin/python scripts/phase_1_analysis/analyze_task71_qmsum_n30_full_matrix.py`

Full validation is recorded in the final Task 71 response.
