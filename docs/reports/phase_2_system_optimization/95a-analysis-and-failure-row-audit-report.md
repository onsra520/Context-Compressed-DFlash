# Task 95A — Analysis and Failure Row Audit

## 1. Purpose

Task95A audits why the Task94 light-compressor GSM8K numeric proxy dropped versus the large compressor before any proxy calibration, compressor tuning, or larger benchmark.

This task is analysis only. It did not load a model, run GPU inference, run a benchmark, or run `n=30` / `n=100`.

## 2. Inputs

- Large artifact: `results/phase_2_system_optimization/compressor_comparison/task94_light_vs_large_compressor_controlled_comparison/runs/20260620_192758_cc_dflash_r2_large_n10.jsonl`
- Light artifact: `results/phase_2_system_optimization/compressor_comparison/task94_light_vs_large_compressor_controlled_comparison/runs/20260620_192904_cc_dflash_r2_light_n10.jsonl`
- Output directory: `results/phase_2_system_optimization/quality_and_latency_audits/task95a_analysis_and_failure_row_audit/`
- Pairing method: `fixture_id`

Both artifacts contain 10 rows. The raw rows include `fixture_id`, `dataset_id`, `prompt_id`, `expected_answer`, `generated_text`, compressor metadata, compression timings, prompt previews, and compressed prompt previews. They do not contain precomputed numeric/exact proxy fields, so Task95A used the existing deterministic Task47 GSM8K numeric classifier.

## 3. Row-Level Outcome Groups

| Group | Count |
| --- | ---: |
| both_correct | 3 |
| large_correct_light_wrong | 3 |
| large_wrong_light_correct | 0 |
| both_wrong | 4 |
| proxy_uncertain | 0 |

The audit uses deterministic numeric extraction as the primary GSM8K proxy. Exact containment is diagnostic only because short numeric answers can appear as intermediate numbers.

## 4. Failure Taxonomy

For the 3 `large_correct_light_wrong` rows:

| Tag | Count |
| --- | ---: |
| answer_missing | 0 |
| arithmetic_wrong | 2 |
| format_or_extraction_issue | 1 |
| truncation_or_cap_issue | 3 |
| compressed_context_loss_possible | 0 |
| generic_or_gibberish | 0 |
| proxy_uncertain | 0 |

Examples:

- `gsm8k_short_test_0015`, gold `5`: light extracted `7`; tagged `format_or_extraction_issue` and `truncation_or_cap_issue`. The light output reaches `35 / 7 =` but stops at the cap before a final numeric answer line.
- `gsm8k_short_test_0014`, gold `1430`: light extracted `130`; tagged `arithmetic_wrong` and `truncation_or_cap_issue`. The output has intermediate arithmetic but stops before the final expected answer.
- `gsm8k_short_test_0087`, gold `40`: light extracted `55`; tagged `arithmetic_wrong` and `truncation_or_cap_issue`. The light output appears to reason from a different interpretation and also hits the output cap.

Conservative interpretation: the light failures are not generic or corrupted. They mostly look like cap-limited incomplete outputs or wrong final/intermediate numeric extraction. The artifact stores compressed prompt previews, but not full compressed prompt text, so this audit cannot directly verify whether evidence deletion caused any failure.

## 5. Proxy Reliability Notes

The Task47 deterministic numeric extractor is reliable for rows with an explicit `Final answer:` marker, but Task95A found format/extraction sensitivity when outputs stop before the final line. Exact containment is not enough to rescue these rows because the expected number can appear as an intermediate or substring.

Task95B is needed to calibrate how to count cap-limited rows where reasoning may contain the right computation path but lacks a final answer marker.

## 6. Compression / Quality Notes

All paired rows preserve recorded compressor metadata:

- `local_files_only` is true in both artifacts.
- compressor paths and resolved compressor paths are present.
- `question_preserved` and `protected_suffix_preserved` are true.
- prompt and compressed prompt previews are present.

Task95A does not claim that compression caused the failures. Full compressed prompt/context text is not available, and the available previews are insufficient for direct evidence-deletion claims.

## 7. Recommendation

Recommendation: proceed to `T95B — Quality Proxy Calibration`.

Rationale: the audit found one format/extraction-sensitive light failure and three cap-limited `large_correct_light_wrong` rows. Before tuning the light compressor, the project should define how the deterministic proxy handles cap-limited outputs, exact-containment-only rows, and missing final answer markers.

`T95C — Light Compressor Parameter/Tail Policy Triage` remains conditional. It should follow only if T95B shows the quality loss is real after proxy calibration.

Do not run `n=30` yet.

## 8. Claim Boundary

Task95A makes no final quality claim, no final speedup claim, no deployment or 8GB claim, no QMSum semantic correctness claim, and no new benchmark claim.

## 9. Artifacts

- `results/phase_2_system_optimization/quality_and_latency_audits/task95a_analysis_and_failure_row_audit/task95a_failure_row_pairs.jsonl`
- `results/phase_2_system_optimization/quality_and_latency_audits/task95a_analysis_and_failure_row_audit/task95a_failure_taxonomy_summary.json`
- `results/phase_2_system_optimization/quality_and_latency_audits/task95a_analysis_and_failure_row_audit/task95a_large_vs_light_row_table.csv`
- `results/phase_2_system_optimization/quality_and_latency_audits/task95a_analysis_and_failure_row_audit/task95a_recommendation.json`

## 10. Validation

Validation commands:

- `PYTHONPATH=src .venv/bin/python -m pytest tests/test_task95a_analysis_and_failure_row_audit.py -q`
- `PYTHONPATH=src .venv/bin/python scripts/phase_2_system_optimization/analysis/task95a_analysis_and_failure_row_audit.py --large-jsonl ... --light-jsonl ... --output-dir ...`

No model inference or benchmark command was run.
