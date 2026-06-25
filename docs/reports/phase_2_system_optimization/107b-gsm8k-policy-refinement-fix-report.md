# Task107B — Optional GSM8K Policy Refinement Fix

## 1. Purpose

Task107B tested a narrow GSM8K-only policy refinement after Task107A found that the Task106B concise final-answer policy fixed cap/finalization pressure but increased strict wrong numeric rows.

This task ran one controlled optimized-condition GSM8K rerun:

- condition: `CC-DFlash-R2`
- dataset: `gsm8k_short`
- seed: `42`
- n: `100`
- `max_new_tokens=256`
- compressor profile: `light`
- compressor device map: `cuda`
- runtime-only GSM8K policy override

Task107B did not run QMSum, a full matrix, Baseline-AR, DFlash-R1, Large CPU, LLMLingua-AR-R2, GSM8K n1000/full dataset, keep-rate tuning, query-aware compression, LLM judge, human scoring, default switch, model/config default change, or downloads.

## 2. Policy Tested

Policy name:

- `gsm8k_minimal_arithmetic_verify_v1`

Policy suffix:

> Show only the necessary arithmetic. Verify the calculation once. End with exactly one line in the format: Final answer: `<number>`. Do not continue after the final answer.

The policy was applied through the existing runtime-only GSM8K policy override. Default GSM8K behavior and project config remain unchanged.

Metadata audit confirmed all `100/100` T107B rows recorded:

- `gsm8k_answer_policy_enabled=true`
- `gsm8k_answer_policy_type=gsm8k_minimal_arithmetic_verify_v1`
- `gsm8k_policy_suffix_override=true`
- `gsm8k_answer_policy_preserved=true`
- `compressor_profile=light`
- `compressor_device_map=cuda`
- `requested_compressor_device_map=cuda`
- `local_files_only=true`

## 3. Run Artifact

Primary run artifact:

- `results/phase_2_system_optimization/final_reruns/task107b_gsm8k_policy_refinement_fix/runs/cc_dflash_r2_light_gpu_gsm8k_seed42_n100_mnt256_minimal_arithmetic_verify.jsonl`

The corrected dataset run completed `100/100` rows with no recorded OOM/CUDA failure flags.

Runtime summary:

| Metric | T107B value |
| --- | ---: |
| rows | `100/100` |
| strict correct | `85/100` |
| cap-limited incomplete | `2/100` |
| strict wrong numeric | `13/100` |
| answer missing | `0/100` |
| final-answer marker | `98/100` |
| average `T_compress_ms` | `17.095514` |
| average e2e time | `1.910664s` |
| average tok/s | `53.470150` |
| average `R_actual` | `2.00` |
| max reserved VRAM | `4.431641 GiB` |

## 4. Comparison Against T106B

T107B was compared primarily against Task106B because Task106B is the current scoped GSM8K candidate policy.

| Metric | T106B concise final-answer | T107B minimal arithmetic verify | Delta |
| --- | ---: | ---: | ---: |
| strict correct | `88/100` | `85/100` | `-3` |
| cap-limited incomplete | `2/100` | `2/100` | `0` |
| strict wrong numeric | `10/100` | `13/100` | `+3` |
| answer missing | `0/100` | `0/100` | `0` |
| final-answer marker | `98/100` | `98/100` | `0` |
| average e2e time | `2.145689s` | `1.910664s` | `-0.235025s` |
| average `T_compress_ms` | `17.457620` | `17.095514` | `-0.362106ms` |
| average tok/s | `52.231247` | `53.470150` | `+1.238903` |
| max reserved VRAM | `4.439453 GiB` | `4.431641 GiB` | `-0.007812 GiB` |

Interpretation: T107B preserves the cap-limited and final-answer-marker improvements from T106B and improves average e2e time. However, it lowers strict correctness and increases strict wrong numeric rows. Therefore it is not the better GSM8K candidate.

## 5. Wrong-Numeric Delta

Wrong numeric changed from `10/100` under T106B to `13/100` under T107B.

Resolved wrong-numeric rows:

- `gsm8k_short_test_0004`
- `gsm8k_short_test_0020`

New wrong-numeric rows:

- `gsm8k_short_test_0011`
- `gsm8k_short_test_0029`
- `gsm8k_short_test_0053`
- `gsm8k_short_test_0057`
- `gsm8k_short_test_0094`

Persistent wrong-numeric rows:

- `gsm8k_short_test_0001`
- `gsm8k_short_test_0034`
- `gsm8k_short_test_0043`
- `gsm8k_short_test_0045`
- `gsm8k_short_test_0061`
- `gsm8k_short_test_0068`
- `gsm8k_short_test_0089`
- `gsm8k_short_test_0098`

The softer arithmetic-verification wording did not reduce the wrong-numeric issue targeted by Task107B.

## 6. Cap-Limited Delta

Cap-limited incomplete rows remained unchanged:

- T106B: `2/100`
- T107B: `2/100`

Persistent cap-limited rows:

- `gsm8k_short_test_0028`
- `gsm8k_short_test_0078`

T107B did not reintroduce broad cap/final-marker failures, but it also did not improve beyond T106B.

## 7. Reference Context

Task105A reference context, not policy-fair reruns:

| Condition | Strict | Cap-limited | Wrong numeric | Avg e2e |
| --- | ---: | ---: | ---: | ---: |
| Baseline-AR | `85/100` | `8/100` | `7/100` | `4.641074s` |
| DFlash-R1 | `84/100` | `9/100` | `7/100` | `2.650564s` |
| T105A optimized Light GPU | `79/100` | `15/100` | `6/100` | `2.896622s` |
| T106B concise Light GPU | `88/100` | `2/100` | `10/100` | `2.145689s` |
| T107B minimal arithmetic Light GPU | `85/100` | `2/100` | `13/100` | `1.910664s` |

Baseline-AR and DFlash-R1 remain historical/context references here because they were not rerun with the T106B or T107B GSM8K policy suffix.

## 8. Decision

Decision: `PASS_WITH_CAVEAT`.

Policy interpretation:

- `t106b_remains_better_gsm8k_candidate`

Best scoped GSM8K candidate after T107B:

- `T106B CC-DFlash-R2 Light GPU concise final-answer policy`
- policy: `gsm8k_concise_final_answer_v1`

T107B is a valid bounded policy test, but it is not adopted as the preferred GSM8K candidate because it worsened strict and wrong-numeric metrics relative to T106B.

## 9. Claim Update

Allowed wording:

- T107B tested a narrow GSM8K-only arithmetic-verification policy for optimized `CC-DFlash-R2` Light GPU.
- T107B preserved T106B's cap-limited count at `2/100` and final-answer marker count at `98/100`.
- T107B improved average e2e time versus T106B in this run.
- T107B did not improve the GSM8K candidate decision because strict dropped to `85/100` and wrong numeric rose to `13/100`.
- T106B remains the scoped GSM8K candidate.

Blocked wording:

- T107B fixes wrong numeric.
- T107B is the new default policy.
- Optimized `CC-DFlash-R2` becomes the default.
- GSM8K quality is fully solved.
- QMSum semantic risk is resolved.
- Full benchmark speed or quality closure is proven.
- References have been policy-fairly rerun.

## 10. Next Task

Next task:

- `T108A — QMSum Targeted Recheck / Fix Feasibility`

Rationale: the GSM8K wrong-numeric branch has been tested. T106B remains the best scoped GSM8K candidate, and the active Phase 2 question moves to whether any QMSum targeted recheck/fix feasibility is needed before closure packaging.

No automatic default switch, full matrix, QMSum semantic claim, or extra benchmark is authorized by Task107B.

## 11. Artifacts

Generated artifacts:

- `results/phase_2_system_optimization/final_reruns/task107b_gsm8k_policy_refinement_fix/runs/cc_dflash_r2_light_gpu_gsm8k_seed42_n100_mnt256_minimal_arithmetic_verify.jsonl`
- `results/phase_2_system_optimization/final_reruns/task107b_gsm8k_policy_refinement_fix/summary/task107b_fix_summary.json`
- `results/phase_2_system_optimization/final_reruns/task107b_gsm8k_policy_refinement_fix/summary/task107b_condition_metrics.json`
- `results/phase_2_system_optimization/final_reruns/task107b_gsm8k_policy_refinement_fix/summary/task107b_policy_comparison.json`
- `results/phase_2_system_optimization/final_reruns/task107b_gsm8k_policy_refinement_fix/summary/task107b_wrong_numeric_delta.json`
- `results/phase_2_system_optimization/final_reruns/task107b_gsm8k_policy_refinement_fix/summary/task107b_cap_limited_delta.json`
- `results/phase_2_system_optimization/final_reruns/task107b_gsm8k_policy_refinement_fix/summary/task107b_runtime_delta.json`
- `results/phase_2_system_optimization/final_reruns/task107b_gsm8k_policy_refinement_fix/summary/task107b_metadata_audit.json`
- `results/phase_2_system_optimization/final_reruns/task107b_gsm8k_policy_refinement_fix/summary/task107b_claim_update.json`
- `results/phase_2_system_optimization/final_reruns/task107b_gsm8k_policy_refinement_fix/summary/task107b_next_task_decision.json`
- `results/phase_2_system_optimization/final_reruns/task107b_gsm8k_policy_refinement_fix/tables/task107b_gsm8k_policy_refinement_comparison.csv`

Analyzer:

- `scripts/phase_2_system_optimization/analysis/task107b_gsm8k_policy_refinement_fix.py`

Tests:

- `tests/test_task107b_gsm8k_policy_refinement_fix.py`

## 12. Scope Confirmation

Task107B ran only the requested optimized GSM8K condition.

It did not run QMSum, QMSum n100, a full matrix, Baseline-AR, DFlash-R1, Large CPU, LLMLingua-AR-R2, GSM8K n1000/full dataset, query-aware compression, keep-rate tuning, human scoring, LLM judge, default switch, or downloads.
