# Task 77 — QMSum Evidence-Focused Protected-Suffix Calibration

Date: 2026-06-14

Status: PASS_WITH_NOTES

## Scope

Task 77 replaces the active QMSum balanced protected suffix with an evidence-focused QMSum-only protected suffix, then runs bounded compressed-only QMSum calibration:

- Dataset: `qmsum_meeting_qa_long`
- Conditions: `LLMLingua-AR-R2`, `CC-DFlash-R2`
- Rows per condition: 30
- Seed: 42
- `max_new_tokens`: 384
- Resume: enabled
- Generated text: stored

This task does not run QMSum n=100, does not run mnt512, does not run GSM8K, and does not run uncompressed QMSum conditions. Results remain preliminary and are not final speedup, correctness, production-readiness, or deployment claims.

## Task 76 Commits

- Task 76 commit: `9f77bd8 test: classify qmsum evidence errors`
- Task 76-fix commit: `dd975b3 fix: refine qmsum evidence taxonomy`

## Policy Change

The active QMSum protected suffix is now evidence-focused:

- Answer only from the meeting context.
- Focus first on exact evidence that answers the question.
- Preserve concrete names, numbers, organizations, decisions, reasons, constraints, and supporting details.
- Avoid generic meeting-topic answers.
- Avoid broad summaries in place of specific evidence.
- Avoid wrong-negative “not mentioned” answers unless the context clearly lacks the answer.
- Use 3-7 concise sentences.

The suffix remains outside LLMLingua compression. GSM8K final-answer suffix behavior is unchanged.

Task 77 metadata added to compressed rows:

- `qmsum_answer_policy_enabled`
- `qmsum_answer_policy_type = "evidence_focused"`
- `qmsum_answer_policy_preserved`
- `qmsum_output_policy_preview`
- `qmsum_evidence_focus_enabled`
- `qmsum_evidence_focus_version = "task77"`
- `final_prompt_tail_preview`

## Dry-Run Prompt Check

Command:

```bash
PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --prompt-source dataset --dataset qmsum_meeting_qa_long --n 3 --seed 42 --dry-run-prompts
```

Result: `DRY-RUN-PASS`.

The dry run printed the evidence-focused suffix as the protected suffix for QMSum rows. No model, compressor, or CUDA path was loaded by the dry run.

## Real Run Commands

LLMLingua-AR-R2:

```bash
PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --prompt-source dataset --dataset qmsum_meeting_qa_long --condition LLMLingua-AR-R2 --n 30 --seed 42 --max-new-tokens 384 --output results/phase_1_system_build_and_evaluation/early_experiments/task77_qmsum_long_llmlingua_ar_r2_n30_mnt384_evidence.jsonl --resume --store-generated-text
```

CC-DFlash-R2:

```bash
PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --prompt-source dataset --dataset qmsum_meeting_qa_long --condition CC-DFlash-R2 --n 30 --seed 42 --max-new-tokens 384 --output results/phase_1_system_build_and_evaluation/early_experiments/task77_qmsum_long_cc_dflash_r2_n30_mnt384_evidence.jsonl --resume --store-generated-text
```

Analyzer:

```bash
PYTHONPATH=src .venv/bin/python scripts/phase_1_system_build_and_evaluation/analysis/t77_qmsum_evidence_policy.py
```

## Artifacts

| Artifact | Rows / status |
| --- | ---: |
| `results/phase_1_system_build_and_evaluation/early_experiments/task77_qmsum_long_llmlingua_ar_r2_n30_mnt384_evidence.jsonl` | 30 |
| `results/phase_1_system_build_and_evaluation/early_experiments/task77_qmsum_long_cc_dflash_r2_n30_mnt384_evidence.jsonl` | 30 |
| `results/phase_1_system_build_and_evaluation/early_experiments/task77_qmsum_evidence_policy_summary.json` | 60 rows summarized |
| `results/phase_1_system_build_and_evaluation/early_experiments/task77_qmsum_evidence_policy_table.csv` | 2 condition rows |
| `results/phase_1_system_build_and_evaluation/early_experiments/task77_qmsum_evidence_policy_cases.jsonl` | 60 labeled cases |

## Policy Preservation And Cap Hits

| Condition | Rows | Policy preserved | Cap hits |
| --- | ---: | ---: | ---: |
| LLMLingua-AR-R2 | 30 | 30/30 | 0 |
| CC-DFlash-R2 | 30 | 30/30 | 0 |

The evidence-focused suffix is reliably preserved. `max_new_tokens=512` is not justified by Task 77 because cap hits remain zero.

## Task 71 vs Task 73 vs Task 75 vs Task 77

| Condition | Stage | Cap hits | Avg overlap | Median overlap | Avg output tokens | Avg e2e latency s | E2E tok/s weighted |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| LLMLingua-AR-R2 | Task 71 original | 22 | 0.358644 | 0.337900 | 348.533333 | 26.378387 | 13.212837 |
| LLMLingua-AR-R2 | Task 73 terse | 0 | 0.227541 | 0.207143 | 48.500000 | 8.040080 | 6.032278 |
| LLMLingua-AR-R2 | Task 75 balanced | 0 | 0.261336 | 0.218254 | 91.000000 | 10.475600 | 8.686853 |
| LLMLingua-AR-R2 | Task 77 evidence | 0 | 0.267398 | 0.216538 | 104.533333 | 11.634044 | 8.985124 |
| CC-DFlash-R2 | Task 71 original | 21 | 0.357483 | 0.338095 | 345.333333 | 19.055571 | 18.122434 |
| CC-DFlash-R2 | Task 73 terse | 0 | 0.228499 | 0.192592 | 48.666667 | 7.575937 | 6.423848 |
| CC-DFlash-R2 | Task 75 balanced | 0 | 0.259867 | 0.236111 | 92.500000 | 9.484380 | 9.752877 |
| CC-DFlash-R2 | Task 77 evidence | 0 | 0.270660 | 0.215838 | 106.133333 | 10.572797 | 10.038341 |

Task 77 slightly improves average overlap over Task 75 for both compressed conditions, but it increases output length and e2e latency. It remains well below Task 71 original overlap while preserving the no-cap-hit benefit.

## Per-Condition Task 77 Metrics

| Condition | Rows | Avg overlap | Avg keyword overlap | Avg entity/number overlap | Avg reference coverage | Avg output tokens | Avg t_compress_ms | Avg t_prefill_ms | Avg e2e latency s | E2E tok/s weighted |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| LLMLingua-AR-R2 | 30 | 0.267398 | 0.215169 | 0.324477 | 0.290480 | 104.533333 | 5526.346972 | 393.203700 | 11.634044 | 8.985124 |
| CC-DFlash-R2 | 30 | 0.270660 | 0.216276 | 0.324477 | 0.294490 | 106.133333 | 5694.212977 | 371.749013 | 10.572797 | 10.038341 |

CC-DFlash-R2 remains faster than LLMLingua-AR-R2 on approximate e2e throughput in this small run, but this is not a final speedup claim.

## Task 76-Fix vs Task 77 Taxonomy

| Label | Task 76-fix | Task 77 |
| --- | ---: | ---: |
| `ACCEPTABLE_EVIDENCE_FOCUSED_ANSWER` | 0 | 2 |
| `PROXY_WEAKNESS` | 2 | 0 |
| `EVIDENCE_MISSING_OR_MISFOCUSED` | 28 | 22 |
| `WRONG_NEGATIVE` | 7 | 16 |
| `MISSING_ENTITY_OR_NUMBER` | 14 | 12 |
| `ANSWER_TOO_GENERAL` | 4 | 1 |
| `STILL_TOO_SHORT` | 1 | 0 |
| `UNCLEAR` | 4 | 7 |

Task 77 reduces `EVIDENCE_MISSING_OR_MISFOCUSED`, `MISSING_ENTITY_OR_NUMBER`, `ANSWER_TOO_GENERAL`, and `STILL_TOO_SHORT`, and it creates two acceptable evidence-focused rows. However, `WRONG_NEGATIVE` increases materially, so the policy is not ready to freeze.

## Per-Condition Labels

| Condition | Main Task 77 labels |
| --- | --- |
| LLMLingua-AR-R2 | `EVIDENCE_MISSING_OR_MISFOCUSED`: 11, `WRONG_NEGATIVE`: 8, `MISSING_ENTITY_OR_NUMBER`: 6, `UNCLEAR`: 3, `ACCEPTABLE_EVIDENCE_FOCUSED_ANSWER`: 1, `ANSWER_TOO_GENERAL`: 1 |
| CC-DFlash-R2 | `EVIDENCE_MISSING_OR_MISFOCUSED`: 11, `WRONG_NEGATIVE`: 8, `MISSING_ENTITY_OR_NUMBER`: 6, `UNCLEAR`: 4, `ACCEPTABLE_EVIDENCE_FOCUSED_ANSWER`: 1 |

## Shared-Failure Analysis

The dominant remaining issue is still evidence targeting, now with a stronger wrong-negative pattern. The new suffix tells the model not to say information is missing unless the context clearly lacks the answer, but both compressed conditions still produce wrong-negative answers on several prompts. This suggests prompt wording alone may not be enough; compressed-prompt/context evidence-retention audit is the safer next step.

## Specific Prompt Checks

| Prompt | Task 76-fix label | Task 77 label | Notes |
| ---: | --- | --- | --- |
| 14 | `WRONG_NEGATIVE` | `WRONG_NEGATIVE` for both | Still says latency details are not provided; misses 100 ms / 40 ms / 10 ms / LDA. |
| 20 | CC `WRONG_NEGATIVE`, AR `EVIDENCE_MISSING_OR_MISFOCUSED` | `EVIDENCE_MISSING_OR_MISFOCUSED` for both | Still shifts to neural-network generalization and misses IBM / 550 / 800 MHz compute-resource evidence. |
| 23 | `WRONG_NEGATIVE` | `WRONG_NEGATIVE` for both | Still says oil-and-gas stress is not provided, missing oil sands / federal Liberal response evidence. |
| 27 | `EVIDENCE_MISSING_OR_MISFOCUSED` | `EVIDENCE_MISSING_OR_MISFOCUSED` for both | Still discusses recording meetings/data collection rather than disk rack / 36GB disks / Aurora-Carmen-SPINE storage. |
| 28 | `WRONG_NEGATIVE` | `WRONG_NEGATIVE` for both | Still denies or misses fishing-industry support despite COVID-19 / $62.5M / CERB evidence. |
| 30 | `EVIDENCE_MISSING_OR_MISFOCUSED` | `EVIDENCE_MISSING_OR_MISFOCUSED` for both | Still gives a safety/gesture answer rather than intelligent-controller objection, speech recognition conflict, cost, and research cooperation evidence. |

## Decision

Task 77 decision:

- Do not freeze the evidence-focused suffix as the current final QMSum policy.
- Do not run QMSum n=100 yet.
- Do not run `max_new_tokens=512`; cap hits are zero.
- Do not continue prompt wording indefinitely without inspecting compressed prompt/context evidence.
- Recommended next task: Task 78 compressed-prompt evidence-retention audit.

Conservative interpretation:

Task 77 proves the evidence-focused suffix can be protected and run through both compressed QMSum paths. It does not prove that QMSum quality is stable. The policy slightly improves average lexical overlap and reduces some old taxonomy buckets, but wrong-negative and evidence-targeting failures remain too common.

## Understand-Anything

Understand-Anything refresh was skipped because `/understand` is not available in this environment.

## Validation

Validation was run after code, tests, analyzer outputs, report, and documentation updates. See final task response for command results.

## Limitations

- QMSum quality is still a lexical proxy, not semantic correctness.
- The analyzer is heuristic and sample-level.
- Rows are n=30 per condition, not n=100.
- CPU LLMLingua compression overhead is included in e2e metrics.
- No final speedup, correctness, production-readiness, deployment, or 8 GB claim is made.
