# Task106A — GSM8K Cap-Limited Attribution Audit

## 1. Purpose

Task106A audits why optimized `CC-DFlash-R2` Light GPU trails the GSM8K strict numeric proxy in Task105A.

This task is attribution/reporting only. It did not run a benchmark, model inference, GPU job, QMSum run, GSM8K rerun, n1000, full dataset, Large CPU, LLMLingua-AR-R2, keep-rate tuning, prompt change, default switch, LLM judge, human scoring, or download.

## 2. Inputs

Primary Task105A inputs:

- `results/phase_2_system_optimization/final_reruns/task105a_gsm8k_controlled_speed_matrix/runs/baseline_ar_gsm8k_short_seed42_n100_mnt256.jsonl`
- `results/phase_2_system_optimization/final_reruns/task105a_gsm8k_controlled_speed_matrix/runs/dflash_r1_gsm8k_short_seed42_n100_mnt256.jsonl`
- `results/phase_2_system_optimization/final_reruns/task105a_gsm8k_controlled_speed_matrix/runs/cc_dflash_r2_light_gpu_gsm8k_short_seed42_n100_mnt256.jsonl`

Stability reference:

- `results/phase_2_system_optimization/final_reruns/task100b_light_gpu_n100_controlled_run/runs/20260621_1555_cc_dflash_r2_light_gpu_seed42_n100_mnt256.jsonl`

The audit reuses the Task95B deterministic quality proxy calibration policy.

## 3. Task105A Cap-Limited Overlap

Task105A calibrated cap-limited counts:

| Condition | Cap-limited incomplete |
| --- | ---: |
| `Baseline-AR` | `8/100` |
| `DFlash-R1` | `9/100` |
| `CC-DFlash-R2` Light GPU | `15/100` |

Overlap result:

- `CC-DFlash-R2` Light GPU cap-limited rows: `15`
- CC-only cap-limited rows: `9`
- CC rows shared with at least one reference: `6`
- Rows shared by all three conditions: `6`

CC-only cap-limited fixture IDs:

- `gsm8k_short_test_0008`
- `gsm8k_short_test_0035`
- `gsm8k_short_test_0045`
- `gsm8k_short_test_0056`
- `gsm8k_short_test_0066`
- `gsm8k_short_test_0089`
- `gsm8k_short_test_0092`
- `gsm8k_short_test_0093`
- `gsm8k_short_test_0099`

Shared-by-all-three fixture IDs:

- `gsm8k_short_test_0028`
- `gsm8k_short_test_0031`
- `gsm8k_short_test_0048`
- `gsm8k_short_test_0078`
- `gsm8k_short_test_0082`
- `gsm8k_short_test_0098`

Interpretation: the cap-limited gap is not purely a universal target-model/prompt behavior, because `9/15` CC cap-limited rows are CC-only. However, `6/15` are shared with both references, so the issue is mixed rather than exclusively compression-path-specific.

## 4. T100B vs T105A Stability

Task100B already showed the same optimized GSM8K Light GPU pattern:

| Source | Strict | Cap-limited | Strict wrong numeric |
| --- | ---: | ---: | ---: |
| Task100B Light GPU n100 | `79/100` | `15/100` | `6/100` |
| Task105A CC-DFlash-R2 Light GPU n100 | `79/100` | `15/100` | `6/100` |

The cap-limited fixture set is identical across Task100B and Task105A:

- shared cap-limited IDs: `15`
- T100B-only cap-limited IDs: `0`
- T105A-only cap-limited IDs: `0`

Interpretation: the optimized GSM8K cap-limited pattern predates the later QMSum remediation and human-review branch. The strict proxy drop should not be attributed to T102/T103 changes by default.

## 5. Attribution Categories

For the `15` CC-DFlash-R2 Light GPU cap-limited rows, the static row audit found:

| Attribution signal | Count |
| --- | ---: |
| final-answer marker missing | `15` |
| hit/near `max_new_tokens=256` | `15` |
| verbose or long reasoning near cap | `15` |
| shared target/prompt cap behavior | `6` |
| CC output longer than references | `8` |
| expected numeric present without final marker | `3` |

Primary attribution split:

| Primary attribution | Count |
| --- | ---: |
| truncated before final answer | `9` |
| shared target or prompt cap behavior | `6` |

The audit does not relabel cap-limited rows as correct. Under the Task95B policy, missing final-answer markers and cap pressure remain strict-proxy failures even when the expected numeric answer appears somewhere in the generated text.

## 6. Fix Recommendation

T106A recommends a scoped T106B follow-up before the default-candidate decision.

Recommended T106B scope:

- investigate a narrow GSM8K final-answer/finalization fix for cap-limited rows
- consider a small token-cap policy check if final-answer completion remains blocked
- preserve the Task95B strict proxy unless a later task explicitly changes it
- do not run n1000, full dataset, QMSum, full matrix, keep-rate tuning, or a default switch

Reason: `9/15` CC cap-limited rows are CC-only, and every CC cap-limited row shows final-marker/cap-pressure evidence. This is enough to justify a small optional fix decision, but not enough to claim a validated fix.

## 7. Claim Update

Allowed wording:

- Task105A supports bounded GSM8K faster-than-Baseline evidence for optimized `CC-DFlash-R2` Light GPU.
- Task105A does not show optimized `CC-DFlash-R2` Light GPU preserving strict GSM8K proxy quality versus references.
- T106A attributes the strict-proxy gap primarily to cap-limited/final-answer-marker pressure when supported by row evidence.
- T100B and T105A show the same optimized GSM8K Light GPU cap-limited pattern.

Blocked wording:

- optimized `CC-DFlash-R2` Light GPU is the overall default winner
- GSM8K quality is preserved versus `Baseline-AR` or `DFlash-R1`
- the strict drop was caused by QMSum remediation or T103 changes
- cap-limited rows should be counted as correct without a policy change
- a fix is validated by this static audit

## 8. Roadmap Update

Roadmap status after Task106A:

- T105C remains `PASS_WITH_CAVEAT`.
- T106A is `PASS_WITH_CAVEAT`.
- T106B is the planned optional cap-limited fix decision.
- T106C is the optimized default-candidate decision after T106B or if T106B is explicitly skipped.
- T103B remains deferred/reserved.
- Final report integration remains deferred outside active Phase 2.

## 9. Artifacts

Generated artifacts:

- `results/phase_2_system_optimization/final_reruns/task106a_gsm8k_cap_limited_attribution_audit/summary/task106a_audit_summary.json`
- `results/phase_2_system_optimization/final_reruns/task106a_gsm8k_cap_limited_attribution_audit/summary/task106a_cap_limited_fixture_overlap.json`
- `results/phase_2_system_optimization/final_reruns/task106a_gsm8k_cap_limited_attribution_audit/summary/task106a_cc_cap_limited_row_audit.jsonl`
- `results/phase_2_system_optimization/final_reruns/task106a_gsm8k_cap_limited_attribution_audit/summary/task106a_attribution_counts.json`
- `results/phase_2_system_optimization/final_reruns/task106a_gsm8k_cap_limited_attribution_audit/summary/task106a_t100b_vs_t105a_stability.json`
- `results/phase_2_system_optimization/final_reruns/task106a_gsm8k_cap_limited_attribution_audit/summary/task106a_fix_options.json`
- `results/phase_2_system_optimization/final_reruns/task106a_gsm8k_cap_limited_attribution_audit/summary/task106a_claim_update.json`
- `results/phase_2_system_optimization/final_reruns/task106a_gsm8k_cap_limited_attribution_audit/summary/task106a_next_task_decision.json`
- `results/phase_2_system_optimization/final_reruns/task106a_gsm8k_cap_limited_attribution_audit/tables/task106a_cap_limited_attribution_table.csv`

Analyzer:

- `scripts/phase_2_system_optimization/analysis/task106a_gsm8k_cap_limited_attribution_audit.py`

Tests:

- `tests/test_task106a_gsm8k_cap_limited_attribution_audit.py`

## 10. Decision

Decision: `PASS_WITH_CAVEAT`.

The audit is complete and supports T106B as an optional, scoped cap-limited fix decision. It does not validate a fix, does not authorize a default switch, and does not change the benchmark-scope claim boundaries from Task105C.
