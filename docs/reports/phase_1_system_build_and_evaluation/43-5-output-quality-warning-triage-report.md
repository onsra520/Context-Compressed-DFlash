# Task 43.5 — Output Quality Warning Triage


> Deprecated note: This report refers to the earlier GSM8K+Wikipedia augmented dataset branch. That branch is no longer part of the active benchmark setup. The active setup uses GSM8K short-context numeric proxy and QMSum long-context diagnostic benchmark.

Date: 2026-06-04

## Result

PASS, preliminary quality-path triage.

Task 43.5 investigated why all 15 Task 43 generated-text rows were scored `NO_CONTAINMENT`. The warning is explained by the 32-token output cap plus a containment-only scorer. The original Task 43 outputs were all truncated at `max_new_tokens=32`, often started reasoning, and did not reach final answers. A DFlash-R1 calibration rerun with `--max-new-tokens 128` produced 5/5 exact containment matches and 5/5 extracted-answer matches on the same sample-mode dataset.

This is not a final correctness claim. It only establishes that the Task 43 warning is not sufficient evidence of true model failure for DFlash-R1, and that Task 44 can freeze a matrix with a safer output-length and extraction-aware answer-quality policy.

## Scope

- Inspected Task 43 generated-text artifacts.
- Added numeric final-answer extraction while keeping containment as a diagnostic signal.
- Added an output inspection utility.
- Added tests for final-answer extraction and runner token-budget override.
- Added a `--max-new-tokens` calibration override to the smoke runner without changing existing default behavior.
- Ran one tiny DFlash-R1 calibration rerun on the audited sample-mode dataset.

No final benchmark was run.

## Artifacts Inspected

- `results/task43_dflash_r1_sample_n5.jsonl`
- `results/task43_llmlingua_ar_r2_sample_n5.jsonl`
- `results/task43_cc_llm_r2_sample_n5.jsonl`
- `results/task43_answer_quality_summary.json`

## New Artifacts

| Artifact | Purpose |
| --- | --- |
| `results/task43_5_original_output_inspection_summary.json` | Inspection summary for original Task 43 outputs |
| `results/task43_5_dflash_r1_calibration_n5.jsonl` | DFlash-R1 n=5 calibration with `max_new_tokens=128` |
| `results/task43_5_output_inspection_summary.json` | Inspection summary for calibration output |
| `results/task43_5_answer_quality_summary.json` | Extraction-aware answer-quality summary |

## Commands

```bash
PYTHONPATH=src .venv/bin/python scripts/t43_outputs.py results/task43_dflash_r1_sample_n5.jsonl results/task43_llmlingua_ar_r2_sample_n5.jsonl results/task43_cc_llm_r2_sample_n5.jsonl --output results/task43_5_original_output_inspection_summary.json
```

```bash
PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --config config.yml --condition DFlash-R1 --n 5 --prompt-source fixture --fixture data/processed/gsm8k_wikipedia_augmented_smoke.jsonl --store-generated-text --max-new-tokens 128 --output results/task43_5_dflash_r1_calibration_n5.jsonl
```

```bash
PYTHONPATH=src .venv/bin/python scripts/t43_outputs.py results/task43_5_dflash_r1_calibration_n5.jsonl --output results/task43_5_output_inspection_summary.json
```

```bash
PYTHONPATH=src .venv/bin/python scripts/phase_1_system_build_and_evaluation/analysis/t31_answer_quality.py results/task43_5_dflash_r1_calibration_n5.jsonl --output results/task43_5_answer_quality_summary.json
```

## Original Task 43 Inspection

| Condition | Rows | Truncated | Containment matches | Extracted matches | Final answer anywhere | Reasoning without answer |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| DFlash-R1 | 5 | 5 | 0 | 0 | 0 | 3 |
| LLMLingua-AR-R2 | 5 | 5 | 0 | 0 | 0 | 3 |
| CC-LLM-R2 | 5 | 5 | 0 | 0 | 0 | 3 |

Interpretation: the original warning is consistent with short-output truncation. It does not by itself prove prompt failure or true model failure.

## Calibration Result

Calibration condition: `DFlash-R1`

Settings:

- `n=5`
- sample-mode dataset
- `--store-generated-text`
- `--max-new-tokens 128`
- existing `torch.sdpa` fallback

| Metric | Value |
| --- | ---: |
| Rows | 5 |
| Exact containment matches | 5 |
| Normalized containment matches | 5 |
| Extracted-answer matches | 5 |
| `NO_CONTAINMENT` rows | 0 |
| Not evaluable rows | 0 |
| Average output tokens | 112.60 |
| Average generated-token count | 112.60 |
| Average tok/s | 7.85 |
| Average tau_mean | 6.02 |
| Max VRAM allocated | 3.5108423233032227 GiB |
| Max VRAM reserved | 3.8671875 GiB |

Inspection result:

- truncated rows: 1/5
- final answer found anywhere: 5/5
- reasoning without answer: 0/5

## Answer Extraction Policy

The answer-quality scorer now keeps containment as diagnostic and additionally reports numeric final-answer extraction:

- `Final answer: 42`
- `Answer: 42`
- `#### 42`
- comma-formatted numbers such as `1,234`
- negative and decimal numbers
- last standalone number fallback when no explicit final-answer marker is present

This is still not semantic correctness and not standard Exact Match. It is a better diagnostic for generated reasoning text than containment alone.

## Triage Decision

Status: PASS.

The Task 43 warning is explained and mitigated enough to proceed to Task 44 matrix freeze, with these constraints:

- freeze a safer output length, at least 128 tokens for long-context sample/final runs unless Task 44 gives a documented reason otherwise
- keep generated text stored for quality tasks
- use extraction-aware answer-quality fields in addition to containment diagnostics
- treat compressed-condition quality as still preliminary until rerun under the frozen Task 44 settings

## Limitations

- Calibration reran only `DFlash-R1`, as the minimum targeted path.
- The dataset is still sample-mode, not full GSM8K + Wikipedia source-mode.
- Extraction-aware scoring is numeric and diagnostic; it is not semantic correctness.
- No final speedup, final correctness, deploy readiness, confirmed 8 GB fit, or proven compression benefit is claimed.

## Validation

- Focused extractor tests: PASS
- Runner override test: PASS
- Original output inspection: PASS
- DFlash-R1 calibration rerun: PASS
- Calibration output inspection: PASS
- Extraction-aware answer-quality check: PASS

## Next Step

Task 44: freeze the final matrix and schema with explicit output length, answer extraction, generated-text retention, dataset mode, and quality-gate decisions.
