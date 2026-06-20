# Task 95B — Quality Proxy Calibration

## 1. Purpose

Task95B calibrated the deterministic GSM8K quality proxy after Task95A found cap-limited and format/extraction-sensitive rows in the Task94 light-vs-large compressor comparison.

This was analysis only. No model was loaded, no GPU inference was run, no benchmark was run, no `n=30` or `n=100` run was launched, and no LLM judge was used.

## 2. Inputs

- Task94 large run: `results/phase_2_system_optimization/compressor_comparison/task94_light_vs_large_compressor_controlled_comparison/runs/20260620_192758_cc_dflash_r2_large_n10.jsonl`
- Task94 light run: `results/phase_2_system_optimization/compressor_comparison/task94_light_vs_large_compressor_controlled_comparison/runs/20260620_192904_cc_dflash_r2_light_n10.jsonl`
- Task95A audit artifacts: `results/phase_2_system_optimization/quality_and_latency_audits/task95a_analysis_and_failure_row_audit/`
- Existing strict extractor: `scripts.phase_1_system_build_and_evaluation.analysis.t47_quality_refinement.classify_row`

Rows were paired by `fixture_id`.

## 3. Proxy Policy

Task47 deterministic numeric extraction remains the strict numeric proxy reference. Task95B adds calibrated auxiliary labels so cap-limited and format-sensitive rows can be separated from ordinary wrong numeric answers.

Policy:

- Strict numeric correctness remains the primary deterministic metric.
- Exact containment is diagnostic only and is not used by itself as correctness.
- Cap-limited or unfinished rows without a final-answer marker are not counted as correct, even if the historical last-number fallback lands on the expected answer.
- Format/extraction-sensitive rows are flagged separately when the expected answer appears plausibly in the text but strict extraction fails.
- No semantic correctness claim is made.

## 4. Calibrated Categories

| Label | Counted as strict correct | Meaning |
| --- | --- | --- |
| `strict_correct` | yes | Task47 strict numeric extraction matches the normalized expected answer and the row is not an unfinished no-marker cap case. |
| `strict_wrong_numeric` | no | A usable final/extracted numeric answer exists, but it differs from expected. |
| `cap_limited_incomplete` | no | The output appears truncated, unfinished, or cap-limited without a final-answer marker. |
| `format_or_extraction_sensitive` | no | Expected answer appears plausibly in text, but strict extraction does not match. |
| `answer_missing` | no | No generated text or no usable numeric answer exists. |
| `proxy_uncertain` | no | Deterministic evidence is insufficient or ambiguous. |

## 5. Results

Historical Task47 strict numeric extraction, before the no-final-marker cap calibration:

| Profile | Raw Task47 strict correct |
| --- | ---: |
| large | 6/10 |
| light | 3/10 |

Calibrated strict score:

| Profile | Calibrated strict correct | Final-answer markers | Exact containment | Cap-limited incomplete |
| --- | ---: | ---: | ---: | ---: |
| large | 5/10 | 5/10 | 7/10 | 5/10 |
| light | 2/10 | 3/10 | 4/10 | 7/10 |

Calibrated category counts:

| Profile | `strict_correct` | `strict_wrong_numeric` | `cap_limited_incomplete` | `format_or_extraction_sensitive` | `answer_missing` | `proxy_uncertain` |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| large | 5 | 0 | 5 | 0 | 0 | 0 |
| light | 2 | 1 | 7 | 0 | 0 | 0 |

Examples:

- `gsm8k_short_test_0015`, expected `5`: the large output reaches `35 / 7 = 5` but has no final-answer marker and is cap-limited; the light output stops at `35 / 7 =`. Both are calibrated as incomplete rather than rescued by containment or fallback.
- `gsm8k_short_test_0014`, expected `1430`: the light output stops after `1300 + 130 =`; calibrated as `cap_limited_incomplete`.
- `gsm8k_short_test_0087`, expected `40`: the light output emits `Final answer: 55`; calibrated as `strict_wrong_numeric`.

## 6. Interpretation

The light-profile quality gap remains after calibration. The calibrated strict score is `5/10` for large and `2/10` for light, a gap of 3 rows. Proxy uncertainty does not explain the gap because `proxy_uncertain=0` for both profiles.

The main calibrated auxiliary signal is cap pressure: light has 7 cap-limited incomplete rows versus 5 for large. This supports treating the Task94 light quality issue as a real bounded concern before any larger sample-size move, with max-new-token/tail-policy behavior as the first triage target.

This does not prove semantic correctness or compression causality. Task95B only separates deterministic proxy outcomes.

## 7. Recommendation

Decision: **A — Proceed to T95C Light Compressor Parameter/Tail Policy Triage**.

Rationale: the calibrated strict large-vs-light gap remains, light has more cap-limited incomplete rows, and light also has one completed wrong-numeric row. Do not run `n=30` yet.

## 8. Claim Boundary

Task95B makes no final quality claim, no final speedup claim, no deployment or 8GB claim, no QMSum semantic correctness claim, and no new benchmark claim.

## 9. Artifacts

- `results/phase_2_system_optimization/quality_and_latency_audits/task95b_quality_proxy_calibration/task95b_calibrated_row_labels.jsonl`
- `results/phase_2_system_optimization/quality_and_latency_audits/task95b_quality_proxy_calibration/task95b_calibrated_quality_summary.json`
- `results/phase_2_system_optimization/quality_and_latency_audits/task95b_quality_proxy_calibration/task95b_proxy_policy_table.csv`
- `results/phase_2_system_optimization/quality_and_latency_audits/task95b_quality_proxy_calibration/task95b_recommendation.json`

## 10. Validation

Validation commands:

- `PYTHONPATH=src .venv/bin/python -m pytest tests/test_task95b_quality_proxy_calibration.py -q`
- `PYTHONPATH=src .venv/bin/python scripts/phase_2_system_optimization/analysis/task95b_quality_proxy_calibration.py --large-jsonl ... --light-jsonl ... --task95a-pairs-jsonl ... --output-dir ...`

No model inference, benchmark, GPU run, LLM judge, or model download was performed.
