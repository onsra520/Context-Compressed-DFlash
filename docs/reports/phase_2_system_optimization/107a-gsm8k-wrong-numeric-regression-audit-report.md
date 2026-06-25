# Task107A — GSM8K Wrong-Numeric Regression Audit

## 1. Purpose

Task107A audits why strict wrong numeric rows increased after the Task106B concise final-answer policy for optimized `CC-DFlash-R2` Light GPU.

This task is static audit/reporting only. It did not run a benchmark, model inference, GPU job, GSM8K rerun, QMSum rerun, full matrix, n1000/full dataset, Large CPU, LLMLingua-AR-R2, query-aware compression, keep-rate tuning, LLM judge, human scoring, default switch, or download.

## 2. Why T107A Is Needed After T106B/T106C

Task106B fixed the intended GSM8K cap/finalization failure mode:

| Metric | T105A optimized | T106B fixed | Delta |
| --- | ---: | ---: | ---: |
| strict proxy | `79/100` | `88/100` | `+9` |
| cap-limited incomplete | `15/100` | `2/100` | `-13` |
| final-answer marker | `85/100` | `98/100` | `+13` |
| average e2e | `2.896622s` | `2.145689s` | `-0.750933s` |
| average `T_compress_ms` | `17.249677ms` | `17.457620ms` | `+0.207943ms` |

However, strict wrong numeric increased:

- before: `6/100`
- after: `10/100`
- delta: `+4`

Task106C therefore kept the optimized path as `SCOPED_GSM8K_CANDIDATE` with `default_switch=NO`. T107A checks whether the wrong-numeric increase is mostly a policy side effect, cap-fix exposure, reference-shared target arithmetic behavior, extractor/proxy issue, or compression/context issue.

## 3. Inputs

Primary artifacts:

- `results/phase_2_system_optimization/final_reruns/task105a_gsm8k_controlled_speed_matrix/runs/cc_dflash_r2_light_gpu_gsm8k_short_seed42_n100_mnt256.jsonl`
- `results/phase_2_system_optimization/final_reruns/task106b_gsm8k_cap_limited_fix/runs/cc_dflash_r2_light_gpu_gsm8k_seed42_n100_mnt256_concise_final_answer.jsonl`
- `results/phase_2_system_optimization/final_reruns/task105a_gsm8k_controlled_speed_matrix/runs/baseline_ar_gsm8k_short_seed42_n100_mnt256.jsonl`
- `results/phase_2_system_optimization/final_reruns/task105a_gsm8k_controlled_speed_matrix/runs/dflash_r1_gsm8k_short_seed42_n100_mnt256.jsonl`

The audit reuses the Task95B deterministic GSM8K calibration policy.

## 4. Wrong-Numeric Before/After Comparison

| Metric | T105A optimized | T106B fixed | Delta |
| --- | ---: | ---: | ---: |
| row count | `100` | `100` | `0` |
| strict correct | `79` | `88` | `+9` |
| strict wrong numeric | `6` | `10` | `+4` |
| cap-limited incomplete | `15` | `2` | `-13` |
| final-answer marker | `85` | `98` | `+13` |
| average output tokens | `168.01` | `110.50` | shorter |
| average `T_compress_ms` | `17.249677` | `17.457620` | near unchanged |

Interpretation: T106B improved strict correctness overall, but the wrong-numeric set churned. The net increase of `+4` hides `8` newly wrong rows and `4` formerly wrong rows that were no longer wrong after T106B.

## 5. Fixture Overlap With References

Wrong-numeric overlap:

| Category | Count |
| --- | ---: |
| wrong in both T105A optimized and T106B fixed | `2` |
| newly wrong only after T106B | `8` |
| fixed wrong rows from T105A | `4` |
| wrong shared with `Baseline-AR` | `5` |
| wrong shared with `DFlash-R1` | `5` |
| wrong shared with any reference | `5` |
| CC-only wrong numeric after T106B | `5` |
| new wrong from previously cap-limited rows | `3` |

Persistent wrong rows:

- `gsm8k_short_test_0001`
- `gsm8k_short_test_0061`

Newly wrong after T106B:

- `gsm8k_short_test_0004`
- `gsm8k_short_test_0020`
- `gsm8k_short_test_0034`
- `gsm8k_short_test_0043`
- `gsm8k_short_test_0045`
- `gsm8k_short_test_0068`
- `gsm8k_short_test_0089`
- `gsm8k_short_test_0098`

Previously wrong rows fixed after T106B:

- `gsm8k_short_test_0011`
- `gsm8k_short_test_0057`
- `gsm8k_short_test_0070`
- `gsm8k_short_test_0087`

## 6. Row-Level Attribution

Primary attribution counts over the `10` T106B wrong-numeric rows:

| Primary attribution | Count |
| --- | ---: |
| `reference_also_wrong` | `3` |
| `resolved_cap_but_wrong_number` | `3` |
| `compressed_context_missing_needed_detail` | `2` |
| `expected_answer_appears_but_final_wrong` | `1` |
| `policy_overcompressed_reasoning` | `1` |

Attribution tag counts:

| Attribution tag | Count |
| --- | ---: |
| `compressed_context_missing_needed_detail` | `10` |
| `arithmetic_error_in_reasoning` | `9` |
| `reference_also_wrong` | `5` |
| `policy_overcompressed_reasoning` | `5` |
| `compression_path_specific_wrong_numeric` | `4` |
| `answer_changed_after_cap_fix` | `3` |
| `resolved_cap_but_wrong_number` | `3` |
| `persistent_wrong_numeric` | `2` |
| `expected_answer_appears_but_final_wrong` | `1` |
| `wrong_final_despite_correct_intermediate` | `1` |

The row audit does not prove semantic causality. It records deterministic evidence from the generated text, final extracted number, output length, pre/post label, reference labels, and prompt/context previews.

## 7. Likely Causes

The wrong-numeric regression is mixed:

- Some rows are reference-shared target arithmetic failures: `5/10` T106B wrong rows overlap at least one reference, and `3/10` are primarily classified as `reference_also_wrong`.
- Some rows are cap-fix exposure: `3/10` T106B wrong rows were cap-limited before T106B and became strict wrong numeric after final-answer completion.
- Some rows look policy/compression-path specific: `5/10` are CC-only wrong after T106B, and `5/10` carry a `policy_overcompressed_reasoning` tag.
- One row contains the expected answer in text but emits a wrong final number, suggesting a final-answer/extractor-or-policy audit target rather than a simple missing-context story.

This supports a narrow optional T107B policy refinement, not a default switch.

## 8. T107B Fix Options

T107A recommends T107B as a small optional GSM8K policy refinement because the attribution is mixed but policy/cap-fix-related evidence is present.

Candidate T107B policy idea:

> Show only the necessary arithmetic. Verify the calculation once. End with exactly one line: Final answer: `<number>`. Do not continue after the final answer.

Scope guards for T107B:

- GSM8K only
- optimized `CC-DFlash-R2` Light GPU only unless explicitly expanded
- no default switch
- no QMSum rerun by default
- no full matrix
- no n1000/full dataset
- no LLM judge or human scoring

If T107B is run, it should test whether minimal arithmetic verification reduces wrong numeric without reintroducing cap/final-marker failures.

## 9. Claim Update

Allowed wording:

- T107A audits the wrong-numeric regression after the T106B concise final-answer policy.
- The audit attributes wrong-numeric increase using existing T105A/T106B artifacts only.
- T106B remains a cap/finalization improvement, but wrong-numeric behavior requires caveated interpretation.

Blocked wording:

- the wrong-numeric issue is fixed
- quality is fully preserved
- optimized `CC-DFlash` should become default
- T107A validates a new policy
- QMSum semantic risk is resolved

## 10. Roadmap Update

Roadmap status after Task107A:

- T106C remains `PASS_WITH_CAVEAT`.
- T107A is `PASS_WITH_CAVEAT`.
- T107B is the conditional next task: optional GSM8K policy refinement fix.
- T108A is planned after the GSM8K wrong-numeric branch for QMSum targeted recheck/fix feasibility.
- Phase 2 closure pack moves to T109.
- T103B remains deferred/reserved.
- Final report integration remains deferred outside active Phase 2.

## 11. Artifacts

Generated artifacts:

- `results/phase_2_system_optimization/final_reruns/task107a_gsm8k_wrong_numeric_regression_audit/summary/task107a_audit_summary.json`
- `results/phase_2_system_optimization/final_reruns/task107a_gsm8k_wrong_numeric_regression_audit/summary/task107a_wrong_numeric_before_after.json`
- `results/phase_2_system_optimization/final_reruns/task107a_gsm8k_wrong_numeric_regression_audit/summary/task107a_wrong_numeric_fixture_overlap.json`
- `results/phase_2_system_optimization/final_reruns/task107a_gsm8k_wrong_numeric_regression_audit/summary/task107a_wrong_numeric_row_audit.jsonl`
- `results/phase_2_system_optimization/final_reruns/task107a_gsm8k_wrong_numeric_regression_audit/summary/task107a_attribution_counts.json`
- `results/phase_2_system_optimization/final_reruns/task107a_gsm8k_wrong_numeric_regression_audit/summary/task107a_t107b_fix_options.json`
- `results/phase_2_system_optimization/final_reruns/task107a_gsm8k_wrong_numeric_regression_audit/summary/task107a_claim_update.json`
- `results/phase_2_system_optimization/final_reruns/task107a_gsm8k_wrong_numeric_regression_audit/summary/task107a_next_task_decision.json`
- `results/phase_2_system_optimization/final_reruns/task107a_gsm8k_wrong_numeric_regression_audit/tables/task107a_wrong_numeric_regression_table.csv`

Analyzer:

- `scripts/phase_2_system_optimization/analysis/task107a_gsm8k_wrong_numeric_regression_audit.py`

Tests:

- `tests/test_task107a_gsm8k_wrong_numeric_regression_audit.py`

## 12. Decision

Decision: `PASS_WITH_CAVEAT`.

T107A supports a conditional T107B policy-refinement check. It does not validate a new policy, does not authorize a default switch, and does not change QMSum claim boundaries.

## 13. Scope Confirmation

Task107A is static audit/reporting only.

It did not run a benchmark, model inference, GPU job, GSM8K rerun, QMSum rerun, full matrix, n1000/full dataset, Large CPU, LLMLingua-AR-R2, query-aware compression, keep-rate tuning, LLM judge, human scoring, default switch, or download.
