# Task106C — Optimized Default Candidate Decision

## 1. Purpose

Task106C decides whether the optimized `CC-DFlash-R2` Light GPU path, including the Task106B GSM8K concise final-answer policy, should be treated as a default, scoped candidate, or experimental path.

This task is static decision/reporting only. It did not run a benchmark, model inference, GPU job, QMSum run, GSM8K rerun, n1000, full matrix, Large CPU, LLMLingua-AR-R2, query-aware compression, keep-rate tuning, LLM judge, human scoring, default switch, or download.

## 2. Evidence Chain From T105C/T106A/T106B

Task105C closed benchmark-scope claims:

- GSM8K Task105A: optimized `CC-DFlash-R2` Light GPU was faster than `Baseline-AR` on average e2e time but slower than `DFlash-R1`.
- GSM8K Task105A: optimized strict proxy trailed both references: `79/100` versus `85/100` for `Baseline-AR` and `84/100` for `DFlash-R1`.
- QMSum Task105B: optimized `CC-DFlash-R2` Light GPU completed the runtime matrix but did not beat `Baseline-AR` or `DFlash-R1`.
- QMSum semantic correctness remained blocked.
- No default switch was authorized.

Task106A attributed the GSM8K strict drop mainly to cap/final-answer-marker pressure:

- `CC-DFlash-R2` Light GPU cap-limited rows: `15/100`
- `15/15` missing final-answer marker
- `15/15` hit or near `max_new_tokens=256`
- `15/15` verbose/long reasoning near cap
- T100B and T105A showed the same optimized pattern, so the drop predates the later QMSum remediation branch.

Task106B tested the narrow GSM8K-only finalization policy:

- policy: `gsm8k_concise_final_answer_v1`
- default behavior unchanged
- run scope: optimized `CC-DFlash-R2` Light GPU only, GSM8K n100/mnt256
- strict improved from `79/100` to `88/100`
- cap-limited incomplete rows dropped from `15/100` to `2/100`
- final-answer marker count improved from `85/100` to `98/100`
- strict wrong numeric increased from `6/100` to `10/100`
- average e2e improved from `2.896622s` to `2.145689s`
- average `T_compress_ms` stayed low at `17.457620ms`
- max reserved VRAM stayed local at about `4.439453 GiB`

## 3. T106B Improvement Summary

| Metric | Before T106B | After T106B | Delta |
| --- | ---: | ---: | ---: |
| Strict numeric proxy | `79/100` | `88/100` | `+9` |
| Cap-limited incomplete | `15/100` | `2/100` | `-13` |
| Final-answer marker | `85/100` | `98/100` | `+13` |
| Strict wrong numeric | `6/100` | `10/100` | `+4` |
| Average e2e time | `2.896622s` | `2.145689s` | `-0.750933s` |
| Average `T_compress_ms` | `17.249677ms` | `17.457620ms` | `+0.207943ms` |
| Max reserved VRAM | `4.431641 GiB` | `4.439453 GiB` | `+0.007812 GiB` |

Interpretation: T106B is strong evidence that the optimized path's GSM8K cap/finalization failure mode can be reduced with a narrow final-answer policy. It is not evidence that all quality risk is solved because wrong numeric rows increased.

## 4. Fairness Caveats

T106B reran only the optimized `CC-DFlash-R2` Light GPU condition with the concise final-answer policy. `Baseline-AR` and `DFlash-R1` were not rerun with the same policy.

Therefore T106C does not claim:

- final all-reference speed win
- final all-reference quality win
- quality-preserved speed win versus all references
- global/default optimized path win

Reference-fairness caveat: T106B is excellent candidate evidence, but it is not a complete reference-rerun matrix.

Additional caveats:

- strict wrong numeric increased from `6/100` to `10/100`
- QMSum was not rerun
- QMSum semantic correctness remains not claimed
- the concise GSM8K policy is not authorized globally

## 5. Candidate/Default Decision

Task106C decision: `PASS_WITH_CAVEAT`.

Decision fields:

| Field | Value |
| --- | --- |
| `optimized_path_status` | `SCOPED_GSM8K_CANDIDATE` |
| `default_switch` | `NO` |
| `qmsum_default_support` | `NO` |
| `production_ready` | `NO` |
| `needs_reference_policy_fairness_rerun_for_final_all_reference_win` | `YES` |

T106C treats the optimized `CC-DFlash-R2` Light GPU plus GSM8K concise final-answer policy as a scoped GSM8K candidate. It is not the global default and not a benchmark-wide winner.

## 6. Supported Candidate Claims

Supported wording:

- T106B shows the optimized `CC-DFlash-R2` Light GPU GSM8K policy can reduce cap-limited failures and improve strict proxy in the optimized condition.
- The optimized path is a scoped GSM8K candidate with strong cap/finalization improvement evidence.
- The candidate remains benchmark-scoped and does not resolve QMSum semantic risk.
- No default switch is authorized.

## 7. Blocked Default Claims

Blocked wording:

- optimized `CC-DFlash` is the default winner
- optimized `CC-DFlash` wins all references
- T106B proves final all-reference speed/quality win
- QMSum semantic correctness is proven
- QMSum residual risk is eliminated
- universal 8GB deployment readiness is proven
- the concise GSM8K policy should be applied globally

## 8. T107 Unblock Requirements

T107 is unblocked as the Phase 2 Optimization Closure Pack, but it must package Phase 2 as candidate/experimental evidence rather than a default-winner story.

T107 must preserve:

- `optimized_path_status=SCOPED_GSM8K_CANDIDATE`
- `default_switch=NO`
- `qmsum_default_support=NO`
- `needs_reference_policy_fairness_rerun_for_final_all_reference_win=YES`
- wrong-numeric regression caveat
- QMSum semantic caveat
- no universal deployment readiness claim

## 9. Roadmap Update

Roadmap status after Task106C:

- T106A remains `PASS_WITH_CAVEAT`.
- T106B remains `PASS_WITH_CAVEAT`.
- T106C is `PASS_WITH_CAVEAT`.
- Current next is `T107 — Phase 2 Optimization Closure Pack`.
- T103B remains deferred/reserved.
- Final report integration remains deferred outside active Phase 2.

## 10. Artifacts

Generated artifacts:

- `results/phase_2_system_optimization/final_reruns/task106c_optimized_default_candidate_decision/summary/task106c_decision_summary.json`
- `results/phase_2_system_optimization/final_reruns/task106c_optimized_default_candidate_decision/summary/task106c_candidate_policy_matrix.json`
- `results/phase_2_system_optimization/final_reruns/task106c_optimized_default_candidate_decision/summary/task106c_supported_candidate_claims.json`
- `results/phase_2_system_optimization/final_reruns/task106c_optimized_default_candidate_decision/summary/task106c_blocked_default_claims.json`
- `results/phase_2_system_optimization/final_reruns/task106c_optimized_default_candidate_decision/summary/task106c_fairness_caveats.json`
- `results/phase_2_system_optimization/final_reruns/task106c_optimized_default_candidate_decision/summary/task106c_t107_unblock_requirements.json`
- `results/phase_2_system_optimization/final_reruns/task106c_optimized_default_candidate_decision/summary/task106c_next_task_decision.json`
- `results/phase_2_system_optimization/final_reruns/task106c_optimized_default_candidate_decision/tables/task106c_default_candidate_decision_table.csv`

Analyzer:

- `scripts/phase_2_system_optimization/analysis/task106c_optimized_default_candidate_decision.py`

Tests:

- `tests/test_task106c_optimized_default_candidate_decision.py`

## 11. Scope Confirmation

Task106C is static decision/reporting only.

It did not run a benchmark, model inference, GPU job, QMSum run, GSM8K rerun, n1000, full matrix, Large CPU, LLMLingua-AR-R2, query-aware compression, keep-rate tuning, LLM judge, human scoring, default switch, or download.
