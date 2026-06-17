# Task 78 — QMSum Compressed-Prompt Evidence-Retention Audit

Date: 2026-06-14

Status: PASS_WITH_NOTES

## Scope And Constraints

Task 78 audited whether answer-critical QMSum evidence survives LLMLingua compression after Task 77. This was an evidence-retention audit, not a benchmark run.

No target model, draft model, CUDA generation, QMSum n=100, GSM8K run, Baseline-AR run, or DFlash-R1 run was performed. Existing Task 71/73/75/76/77 artifacts were not modified.

Task 77 was already committed before this task. Current relevant commit:

- `761c2f2 test: calibrate qmsum evidence-focused policy`

## Why Task 78 Exists

Task 77 showed that the evidence-focused QMSum suffix was preserved and cap hits stayed at zero, but wrong-negative and evidence-targeting failures remained common. Task 78 checks whether those failures are better explained by compression removing evidence, by source/reference mismatch, or by model failure despite retained compressed evidence.

## Audit Mode

Mode: bounded compressor-only reconstruction.

The Task 77 artifacts contained prompt/context previews, not full original/compressed context. The audit therefore reconstructed selected QMSum compressed prompts with the same bounded settings:

- dataset: `qmsum_meeting_qa_long`
- seed: `42`
- n: `30`
- keep_rate: `0.5`
- policy: evidence-focused protected suffix

Only the LLMLingua compressor was loaded for prompt reconstruction. Target/draft models were not loaded and no generation was run.

## Inputs

| Input | Rows |
| --- | ---: |
| `results/task77_qmsum_evidence_policy_cases.jsonl` | 60 |
| `results/task77_qmsum_long_llmlingua_ar_r2_n30_mnt384_evidence.jsonl` | 30 |
| `results/task77_qmsum_long_cc_dflash_r2_n30_mnt384_evidence.jsonl` | 30 |
| `results/task76_qmsum_evidence_error_cases.jsonl` | 60 |
| `data/eval/qmsum_meeting_qa_100.jsonl` | 100 |

## Outputs

| Output | Rows |
| --- | ---: |
| `results/task78_qmsum_evidence_retention_summary.json` | JSON summary |
| `results/task78_qmsum_evidence_retention_table.csv` | 4 label rows |
| `results/task78_qmsum_evidence_retention_cases.jsonl` | 29 |
| `results/task78_qmsum_reconstructed_prompt_previews.jsonl` | 29 |
| `results/task78_qmsum_selected_evidence_spans.jsonl` | 29 |

The audit uses one shared compressed-prompt case per selected prompt because LLMLingua-AR-R2 and CC-DFlash-R2 share the same compression path.

## Method

The analyzer extracted important evidence terms from each expected answer:

- numbers and numeric units
- acronyms and technical terms
- named entities and organizations
- domain phrases such as `oil sands`, `Bill C-69`, `disk rack`, and `speech recognition`

It filtered noisy discourse words such as `Plus`, `Therefore`, `These`, `Beyond`, `For`, `It`, `More`, and `User`.

For each selected prompt, the analyzer compared expected-answer evidence terms against:

- reconstructed original context
- reconstructed compressed context

It then assigned one evidence-retention label per prompt-level case.

## Aggregate Results

| Metric | Value |
| --- | ---: |
| Audited prompt-level cases | 29 |
| Priority prompts audited | 6 |
| Secondary prompts audited | 4 |
| Rows with full reconstruction | 29 |
| Artifact-only rows | 0 |
| Question preserved | 29 |
| Protected suffix preserved | 29 |
| Average original evidence hit rate | 0.449632 |
| Average compressed evidence hit rate | 0.449632 |
| Average evidence retention ratio | 0.620690 |

| Evidence-retention label | Count |
| --- | ---: |
| `EVIDENCE_PRESENT_IN_COMPRESSED_PROMPT_MODEL_FAILED` | 10 |
| `EVIDENCE_PARTIALLY_PRESENT_IN_COMPRESSED_PROMPT` | 6 |
| `EVIDENCE_MISSING_FROM_ORIGINAL_CONTEXT_OR_SOURCE_MISMATCH` | 6 |
| `UNCLEAR` | 7 |

No audited case was labeled `EVIDENCE_MISSING_FROM_COMPRESSED_PROMPT`.

## Priority Prompt Analysis

| Prompt | Expected focus | Label | Original hit rate | Compressed hit rate | Interpretation |
| ---: | --- | --- | ---: | ---: | --- |
| 14 | latency details, `100ms`, `40ms`, `10ms`, `LDA` | `EVIDENCE_MISSING_FROM_ORIGINAL_CONTEXT_OR_SOURCE_MISMATCH` | 0.000000 | 0.000000 | The expected terms were not found by the heuristic in the reconstructed original context. Treat as possible source/reference mismatch or extraction limitation. |
| 20 | `IBM`, `550`, `800 MHz` computational resources | `EVIDENCE_MISSING_FROM_ORIGINAL_CONTEXT_OR_SOURCE_MISMATCH` | 0.200000 | 0.200000 | Only a small part of the expected evidence was found before compression, so the audit cannot blame compression. |
| 23 | oil and gas, anti-oil lobby, oil sands, federal Liberal response | `EVIDENCE_PARTIALLY_PRESENT_IN_COMPRESSED_PROMPT` | 0.461538 | 0.461538 | Some expected evidence terms survive compression, but the heuristic finds only partial support even in the original context. |
| 27 | disk rack, `36GB` disks, `Aurora`, `Carmen`, `SPINE` | `UNCLEAR` | 0.333333 | 0.333333 | Some terms are present after compression, but the heuristic support is too weak for a confident label. |
| 28 | fishing support, COVID-19, `$62.5M`, `CERB`, `EI` | `EVIDENCE_PARTIALLY_PRESENT_IN_COMPRESSED_PROMPT` | 0.400000 | 0.400000 | Evidence is partly retained; remaining failure is not explained by obvious compressed-term loss alone. |
| 30 | speech recognition conflict, cost, research cooperation | `EVIDENCE_PRESENT_IN_COMPRESSED_PROMPT_MODEL_FAILED` | 1.000000 | 1.000000 | The expected evidence terms are retained after compression, but Task 77 still failed. |

## Secondary Prompt Analysis

| Prompt | Expected focus | Label | Original hit rate | Compressed hit rate |
| ---: | --- | --- | ---: | ---: |
| 4 | solar energy alimentation, remote areas, ecologists, production cost | `EVIDENCE_MISSING_FROM_ORIGINAL_CONTEXT_OR_SOURCE_MISMATCH` | 0.000000 | 0.000000 |
| 8 | Welsh Government, police, crime commissioners | `EVIDENCE_PARTIALLY_PRESENT_IN_COMPRESSED_PROMPT` | 0.600000 | 0.600000 |
| 13 | OAS, GIS, `$300`, `$200`, `$500` | `EVIDENCE_PARTIALLY_PRESENT_IN_COMPRESSED_PROMPT` | 0.600000 | 0.600000 |
| 21 | GGT, KL, JRASTRA, VTS | `EVIDENCE_MISSING_FROM_ORIGINAL_CONTEXT_OR_SOURCE_MISMATCH` | 0.000000 | 0.000000 |

## Interpretation

The audit does not support a broad claim that LLMLingua compression is deleting the answer-critical evidence in the selected QMSum failures. Across reconstructed prompt-level cases, original and compressed evidence hit rates were equal on average, and no case received the strongest compression-loss label.

The dominant interpretable signal is: some failures appear to be model failure despite retained evidence, while others are partial/source-mismatch/unclear under the current lexical heuristic.

This does not prove semantic correctness or prove that compression is safe. It only means that, for these selected reconstructed prompts, obvious evidence deletion is not the primary supported explanation.

## Policy Decision

Current Task 77 evidence-focused policy should remain non-final. It preserved the protected suffix and avoided cap hits, but it did not solve QMSum answer quality.

QMSum should remain a long-context speed/prefill/compression-overhead diagnostic with lexical/normalized-text proxy quality. It should not be treated as an exact semantic correctness benchmark without manual review or a semantic judge.

## Next Task Recommendation

Recommended next task: Task 79B final QMSum limitation freeze / reporting decision.

Decision flags:

- mnt512 needed: false
- QMSum n=100 justified now: false
- more suffix prompt-tuning justified now: false

The next step should freeze how QMSum limitations will be reported or define a more semantic/manual review path. It should not blindly continue suffix tuning or jump to QMSum n=100.

## Validation

Commands run:

- `PYTHONPATH=src .venv/bin/python -m pytest tests/test_task78_qmsum_evidence_retention.py -q`
- `PYTHONPATH=src .venv/bin/python scripts/phase_1_analysis/analyze_task78_qmsum_evidence_retention.py`
- `python3 -m json.tool results/task78_qmsum_evidence_retention_summary.json >/dev/null`

Full final validation is recorded in the task completion response.
