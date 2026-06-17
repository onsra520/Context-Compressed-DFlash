# Task 72 - QMSum Cap-Hit and Proxy Triage

Date: 2026-06-13

## Result

PASS_WITH_NOTES.

Task 72 completed a read-only triage of Task 71 QMSum n=30 artifacts. No benchmark was run, no model/compressor/CUDA path was loaded, and no existing Task 71 artifacts were modified.

The main finding is that compressed QMSum rows still show strong output-budget pressure at `max_new_tokens=384`: LLMLingua-AR-R2 hit the cap in 22/30 rows and CC-DFlash-R2 hit the cap in 21/30 rows. The failure mode is not analogous to GSM8K numeric-answer failure; it is mostly long-answer generation/proxy behavior under compressed long-context prompts.

## Inputs

| Artifact | Condition | Rows | Notes |
|---|---:|---:|---|
| `results/task71_qmsum_long_baseline_ar_n30_mnt384.jsonl` | Baseline-AR | 30 | Read-only |
| `results/task71_qmsum_long_dflash_r1_n30_mnt384.jsonl` | DFlash-R1 | 30 | Read-only |
| `results/task71_qmsum_long_llmlingua_ar_r2_n30_mnt384.jsonl` | LLMLingua-AR-R2 | 30 | Read-only |
| `results/task71_qmsum_long_cc_dflash_r2_n30_mnt384.jsonl` | CC-DFlash-R2 | 30 | Read-only |
| `results/task71_qmsum_n30_full_matrix_summary.json` | Summary | 4 conditions | Read-only reference |
| `results/task71_qmsum_n30_full_matrix_table.csv` | Summary table | 4 rows | Read-only reference |
| `results/task71_qmsum_n30_failure_samples.jsonl` | Warning samples | 86 rows | Read-only reference |

Task 71 commit: `4998ff7 test: run qmsum n30 full matrix`.

## Outputs

| Artifact | Purpose |
|---|---|
| `scripts/phase_1_analysis/analyze_task72_qmsum_cap_hit_proxy_triage.py` | Read-only analyzer |
| `tests/test_task72_qmsum_cap_hit_proxy_triage.py` | CPU-only analyzer tests |
| `results/task72_qmsum_cap_hit_proxy_summary.json` | Machine-readable summary |
| `results/task72_qmsum_cap_hit_proxy_cases.jsonl` | Cap-hit case labels and snippets |
| `results/task72_qmsum_cap_hit_proxy_table.csv` | Compact metric table |

## Cap-Hit Overlap

| Metric | Value |
|---|---:|
| LLMLingua-AR-R2 cap-hit rows | 22/30 |
| CC-DFlash-R2 cap-hit rows | 21/30 |
| Shared compressed cap-hit prompt IDs | 21 |
| LLMLingua-only cap-hit prompt IDs | 1 |
| CC-DFlash-only cap-hit prompt IDs | 0 |

Shared cap-hit prompt IDs:

`1, 5, 6, 9, 10, 11, 12, 13, 15, 16, 17, 18, 19, 21, 23, 24, 26, 27, 28, 29, 30`

LLMLingua-only cap-hit prompt ID:

`4`

## Cap-Hit vs Non-Cap Proxy Summary

| Condition | Cap Hits | Non-Cap Rows | Cap Avg Overlap | Non-Cap Avg Overlap | Natural End Count | Cut Mid-Sentence |
|---|---:|---:|---:|---:|---:|---:|
| LLMLingua-AR-R2 | 22 | 8 | 0.356 | 0.365 | 3 | 19 |
| CC-DFlash-R2 | 21 | 9 | 0.361 | 0.350 | 0 | 21 |

The normalized-overlap proxy is similar for cap-hit and non-cap compressed rows. That means the cap itself is not the only quality signal. However, most cap-hit rows end mid-thought or inside a list, so the current QMSum generation format is still not stable enough for n=100.

## Label Counts

| Label | Count |
|---|---:|
| TRUNCATION_LIKELY | 38 |
| LONG_ANSWER_CAP_PRESSURE | 2 |
| PROXY_WEAKNESS | 1 |
| ACCEPTABLE_DESPITE_CAP | 1 |
| UNCLEAR | 1 |

By condition:

| Condition | Label Counts |
|---|---|
| LLMLingua-AR-R2 | TRUNCATION_LIKELY 18; LONG_ANSWER_CAP_PRESSURE 1; PROXY_WEAKNESS 1; ACCEPTABLE_DESPITE_CAP 1; UNCLEAR 1 |
| CC-DFlash-R2 | TRUNCATION_LIKELY 20; LONG_ANSWER_CAP_PRESSURE 1 |

## Representative Examples

| Label | Condition | Prompt ID | Summary |
|---|---|---:|---|
| TRUNCATION_LIKELY | LLMLingua-AR-R2 | 1 | Expected answer discusses why an intelligent controller was convenient and attractive; output is a long structured explanation and cuts off inside a reason about brand identity. |
| TRUNCATION_LIKELY | CC-DFlash-R2 | 15 | Expected answer includes project plan and target revenue; output reaches useful revenue details but cuts off at "Market Strategy:". |
| LONG_ANSWER_CAP_PRESSURE | LLMLingua-AR-R2 | 28 | Expected answer concerns COVID impact on fish/seafood and support measures; output drifts into a long list of petitions and cuts off. |
| PROXY_WEAKNESS | LLMLingua-AR-R2 | 16 | Output ends naturally but overlap with the reference answer is low, so normalized overlap alone is weak for this long-answer prompt. |
| ACCEPTABLE_DESPITE_CAP | LLMLingua-AR-R2 | 18 | Output reaches related tourism-sector content despite hitting the cap; still not treated as semantic correctness. |
| UNCLEAR | LLMLingua-AR-R2 | 21 | Output discusses spectral-subtraction context but proxy evidence is insufficient to label the row confidently. |

## Interpretation

This does not resemble the GSM8K failure pattern. GSM8K failures are numeric-answer and reasoning/extraction failures. QMSum failures are long-answer cap pressure, verbosity, and normalized-overlap proxy limitations.

The compressed paths appear to generate much longer answers than the uncompressed paths:

| Condition | Avg Output Tokens | Cap Hits | Avg E2E Latency (s) | Weighted E2E tok/s |
|---|---:|---:|---:|---:|
| Baseline-AR | 61.63 | 0 | 4.26 | 14.45 |
| DFlash-R1 | 60.50 | 0 | 3.10 | 19.54 |
| LLMLingua-AR-R2 | 348.53 | 22 | 26.38 | 13.21 |
| CC-DFlash-R2 | 345.33 | 21 | 19.06 | 18.12 |

CC-DFlash-R2 remains faster end-to-end than LLMLingua-AR-R2 in the Task 71 QMSum n=30 artifacts, but both compressed paths are not ready for n=100 quality interpretation because their long answers often run into the cap.

## Decision

| Question | Decision |
|---|---|
| Is QMSum n=100 justified next? | No |
| Is mnt512 compressed-only calibration justified? | Yes, but only as a bounded compressed-only diagnostic |
| Is prompt refinement recommended? | Yes |
| Is final report synthesis ready? | No |

Recommended next task:

Task 73 should run a bounded QMSum compressed-only follow-up, preferably combining prompt-style refinement with a tiny `max_new_tokens=512` diagnostic before any QMSum n=100 move. The goal should be to reduce verbose list-style answers and verify whether cap-hit rows can finish naturally, not to claim final semantic correctness.

## Limitations

- QMSum quality is only measured by normalized overlap / containment proxy here.
- No manual semantic review or LLM judge was used.
- Cap-hit labels are heuristic and conservative.
- This is n=30 smoke/diagnostic evidence, not a final benchmark.
- No final speedup, correctness, deployment, or 8 GB claim is supported.

## Validation

Commands run:

- `PYTHONPATH=src .venv/bin/python -m pytest tests/test_task72_qmsum_cap_hit_proxy_triage.py -q`
- `PYTHONPATH=src .venv/bin/python scripts/phase_1_analysis/analyze_task72_qmsum_cap_hit_proxy_triage.py`

Full validation was run after documentation updates and is summarized in the final task response.
