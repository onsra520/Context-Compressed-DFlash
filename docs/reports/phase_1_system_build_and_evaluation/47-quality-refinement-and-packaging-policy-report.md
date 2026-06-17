# Task 47 Quality Refinement and Packaging Policy Report


> Deprecated note: This report refers to the earlier GSM8K+Wikipedia augmented dataset branch. That branch is no longer part of the active benchmark setup. The active setup uses GSM8K short-context numeric proxy and QMSum long-context diagnostic benchmark.

Date: 2026-06-06

Status: PASS

## Purpose

Task 47 refines the deterministic quality interpretation for the audited Task 45 final artifacts and Task 46 Pareto analysis. The goal is to separate throughput claims from quality diagnostics before Task 48 paper-ready figure/report packaging.

This task did not rerun benchmarks, did not use an LLM judge, and did not modify Task 45 final artifacts.

## Input Artifacts

| Input | Purpose |
|---|---|
| `results/task45_final_artifact_audit_summary.json` | Audited final artifact paths and Task 45 diagnostic quality summary |
| `results/task46_pareto_summary.json` | Decode-only and end-to-end Pareto interpretation |
| `results/task45_final_baseline_ar_n100.jsonl` | Baseline-AR generated text rows |
| `results/task45_final_dflash_r1_n100.jsonl` | DFlash-R1 generated text rows |
| `results/task45_final_llmlingua_ar_r2_n100.jsonl` | LLMLingua-AR-R2 generated text rows |
| `results/task45_final_cc_llm_r2_n100.jsonl` | CC-LLM-R2 generated text rows |
| `data/processed/gsm8k_wikipedia_augmented_full.jsonl` | Expected-answer fallback by fixture id |

## Outputs

| Output | Purpose |
|---|---|
| `scripts/phase_1_system_build_and_evaluation/analysis/t47_quality_refinement.py` | Deterministic quality-refinement analyzer |
| `results/task47_quality_refinement_summary.json` | Machine-readable quality summary and claim policy |
| `results/task47_quality_failure_samples.jsonl` | Representative compact failure samples, up to 5 per condition |
| `results/task47_quality_table.csv` | Compact condition-level quality table |
| `tests/test_task47_quality_refinement.py` | CPU-only unit tests for extraction, classification, and summary behavior |

## Extraction Method

The analyzer uses deterministic extraction only. It does not use LLM-as-judge or semantic grading.

The extraction path:

1. Prefer explicit final-answer markers: `####`, `Final answer:`, `Answer:`, `answer is`, and therefore/so/thus answer/result patterns.
2. Normalize numeric answers by stripping currency symbols, commas, leading plus signs, and unnecessary trailing decimal zeroes.
3. Support negative numbers and decimal numbers.
4. If no final-answer marker exists, use the last standalone number in the tail of generated text as a diagnostic fallback.
5. Mark rows as `parse_ambiguous` when multiple marked final-answer candidates conflict.
6. Mark rows as `truncated_or_stopped_early` when `output_tokens >= max_new_tokens` or a long output lacks terminal punctuation.

Exact containment and numeric extraction are reported separately. Numeric extraction is a diagnostic proxy, not final EM or semantic correctness.

## Metric Table

| Condition | Rows | Generated Text Rows | Exact Matches | Numeric Matches | Extracted But Wrong | No Final Answer | Truncated / Stopped Early | Ambiguous | Numeric Match Rate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Baseline-AR | 100 | 100 | 24 | 11 | 76 | 0 | 0 | 0 | 0.11 |
| DFlash-R1 | 100 | 100 | 23 | 10 | 77 | 0 | 0 | 0 | 0.10 |
| LLMLingua-AR-R2 | 100 | 100 | 16 | 5 | 84 | 0 | 0 | 0 | 0.05 |
| CC-LLM-R2 | 100 | 100 | 18 | 6 | 81 | 0 | 1 | 0 | 0.06 |

## Failure-Mode Table

| Condition | Failure Mode Distribution |
|---|---|
| Baseline-AR | `exact_match`: 24, `extracted_but_wrong`: 76 |
| DFlash-R1 | `exact_match`: 23, `extracted_but_wrong`: 77 |
| LLMLingua-AR-R2 | `exact_match`: 16, `extracted_but_wrong`: 84 |
| CC-LLM-R2 | `exact_match`: 18, `extracted_but_wrong`: 81, `truncated_or_stopped_early`: 1 |

## Representative Failure Samples

The sample file contains 20 compact rows: 5 representative failures per condition. Samples include artifact path, row index, prompt id, fixture id, expected answer, extracted answer, candidate answers, failure type, truncation flag, and a generated-text excerpt.

Observed pattern:

| Condition | Sampled Pattern |
|---|---|
| Baseline-AR | Reasoning often starts correctly, but the deterministic fallback extracts an intermediate number from verbose reasoning instead of a final answer. |
| DFlash-R1 | Similar to Baseline-AR: outputs frequently include reasoning numbers but not a clearly marked final answer in sampled rows. |
| LLMLingua-AR-R2 | Compression path keeps generated text present but sampled failures often stop before a final numeric answer marker. |
| CC-LLM-R2 | Similar to LLMLingua-AR-R2; one row was additionally classified as truncated or stopped early. |

These samples support keeping quality as a diagnostic numeric-extraction proxy for Task 48 rather than a semantic correctness claim.

## Comparison with Task 46 Diagnostic Quality

Task 46 used the Task 45 audit quality fields:

| Condition | Task 46 Exact | Task 46 Normalized Total | Task 46 Extracted Numeric | Task 46 No Containment |
|---|---:|---:|---:|---:|
| Baseline-AR | 24 | 25 | 10 | 75 |
| DFlash-R1 | 23 | 24 | 10 | 76 |
| LLMLingua-AR-R2 | 16 | 17 | 5 | 83 |
| CC-LLM-R2 | 18 | 19 | 6 | 81 |

Task 47 keeps the same conservative interpretation but makes failure modes more explicit. The refined extractor changes Baseline-AR numeric matches from 10 to 11 and classifies CC-LLM-R2 with one truncation/stopped-early signal. It does not materially change the conclusion: quality evidence is still diagnostic and format-sensitive.

## Quality Deltas

| Comparison | Exact Rate Delta | Numeric Rate Delta | No-Answer Rate Delta | Extracted-Wrong Delta | Truncated Delta |
|---|---:|---:|---:|---:|---:|
| DFlash-R1 vs Baseline-AR | -0.01 | -0.01 | 0.00 | +1 | 0 |
| LLMLingua-AR-R2 vs Baseline-AR | -0.08 | -0.06 | 0.00 | +8 | 0 |
| CC-LLM-R2 vs LLMLingua-AR-R2 | +0.02 | +0.01 | +0.01 | -3 | +1 |
| CC-LLM-R2 vs DFlash-R1 | -0.05 | -0.04 | +0.01 | +4 | +1 |
| CC-LLM-R2 vs Baseline-AR | -0.06 | -0.05 | +0.01 | +5 | +1 |

## Allowed Claims for Task 48

Task 48 may present:

- measured decode throughput
- estimated end-to-end throughput with CPU compression
- deterministic numeric answer extraction as a diagnostic proxy
- deterministic failure-mode counts
- throughput and diagnostic quality as separate axes

## Forbidden Claims for Task 48

Task 48 must not claim:

- final semantic correctness
- final exact match as a robust benchmark result
- deployment readiness
- confirmed 8 GB deployment
- proven end-to-end compression benefit
- LLM-judge quality results

## Recommendation for Task 48

Task 48 can proceed to paper-ready figures and final report packaging if every figure labels quality as deterministic numeric extraction rather than final semantic correctness.

Recommended Task 48 wording:

- Use `measured decode throughput` for raw generation speed.
- Use `estimated e2e throughput with CPU compression` for compression-inclusive speed.
- Use `diagnostic numeric extraction match` for quality.
- Include a visible caveat that semantic correctness and human evaluation remain future work.

## Validation

Commands run:

```bash
PYTHONPATH=src .venv/bin/python scripts/phase_1_system_build_and_evaluation/analysis/t47_quality_refinement.py \
  --audit results/task45_final_artifact_audit_summary.json \
  --pareto results/task46_pareto_summary.json \
  --output results/task47_quality_refinement_summary.json \
  --samples-output results/task47_quality_failure_samples.jsonl
```

Result: PASS. The script wrote `results/task47_quality_refinement_summary.json`, `results/task47_quality_failure_samples.jsonl`, and `results/task47_quality_table.csv`.

Additional validation is recorded in the final agent response for this task.

## Limitations

- Deterministic extraction is format-sensitive.
- Fallback last-number extraction can misclassify verbose reasoning that lacks a final-answer marker.
- The output is not a semantic correctness benchmark.
- No LLM judge or human grading was used.
- These are Task 45 n=100 artifacts only; no new benchmark was run.
- Task 48 must not present these quality numbers as final EM.
