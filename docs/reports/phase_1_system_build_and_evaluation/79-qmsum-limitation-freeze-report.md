# Task 79B — Final QMSum Limitation Freeze / Reporting Decision

Date: 2026-06-14

Status: PASS_WITH_NOTES

## Scope

Task 79B freezes how QMSum-style meeting QA should be used and reported after the Task 73–78 prompt-quality debugging loop.

This task is documentation and decision packaging only. It does not run benchmarks, load target models, load draft models, load LLMLingua, use CUDA, run QMSum n=100, run `max_new_tokens=512`, run GSM8K, or tune prompts.

## Precondition

Task 78 was already committed before this task:

- `221a9a9 test: audit qmsum compressed evidence retention`

## Inputs Read

| Input | Status |
| --- | --- |
| `docs/reports/71-qmsum-n30-full-matrix-report.md` | present |
| `docs/reports/72-qmsum-cap-proxy-triage-report.md` | missing; current history uses Task 72 results through later summaries/docs |
| `docs/reports/73-qmsum-concise-policy-report.md` | present |
| `docs/reports/74-qmsum-proxy-case-triage-report.md` | present |
| `docs/reports/75-qmsum-balanced-policy-report.md` | present |
| `docs/reports/76-qmsum-evidence-error-taxonomy-report.md` | present |
| `docs/reports/77-qmsum-evidence-focused-policy-report.md` | present |
| `docs/reports/78-qmsum-compressed-prompt-evidence-retention-report.md` | present |
| `results/phase_1_system_build_and_evaluation/early_experiments/task71_qmsum_n30_full_matrix_summary.json` | present |
| `results/phase_1_system_build_and_evaluation/early_experiments/task73_qmsum_concise_policy_summary.json` | present |
| `results/phase_1_system_build_and_evaluation/early_experiments/task75_qmsum_balanced_policy_summary.json` | present |
| `results/phase_1_system_build_and_evaluation/early_experiments/task76_qmsum_evidence_error_summary.json` | present |
| `results/phase_1_system_build_and_evaluation/early_experiments/task77_qmsum_evidence_policy_summary.json` | present |
| `results/phase_1_system_build_and_evaluation/early_experiments/task78_qmsum_evidence_retention_summary.json` | present |

## Task Timeline: 71–78

| Task | Role | Result |
| --- | --- | --- |
| Task 71 | Fresh QMSum n=30 full matrix at `max_new_tokens=384` | Compressed rows had higher lexical overlap but frequent cap hits; CC-DFlash-R2 improved e2e speed versus LLMLingua-AR-R2 in this diagnostic run. |
| Task 72 | Cap-hit and proxy triage | Compressed cap hits were treated as long-answer pressure; QMSum n=100 stayed blocked. |
| Task 73 | Terse QMSum protected suffix | Removed cap hits but made answers too short and degraded overlap proxy. |
| Task 74 | Terse-policy case triage | Found that many concise answers were too short or unsupported by lexical evidence. |
| Task 75 | Balanced 3–6 sentence protected suffix | Kept cap hits at zero and recovered some overlap, but quality remained unstable. |
| Task 76 / 76-fix | Evidence-error taxonomy | Refined failures into evidence-misfocus, wrong-negative answers, and missing entities/numbers. |
| Task 77 | Evidence-focused protected suffix | Preserved suffix and kept cap hits at zero, but wrong-negative and evidence-targeting failures persisted. |
| Task 78 | Compressed-prompt evidence-retention audit | Found retained/partial evidence, source/reference mismatch, and unclear cases; did not support broad compressed-evidence deletion as the main explanation. |

## Key Metric Table

| Stage | LLMLingua-AR-R2 cap hits | LLMLingua-AR-R2 avg overlap | LLMLingua-AR-R2 avg e2e s | CC-DFlash-R2 cap hits | CC-DFlash-R2 avg overlap | CC-DFlash-R2 avg e2e s | Interpretation |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Task 71 original | 22/30 | 0.358644 | 26.378 | 21/30 | 0.357483 | 19.056 | Better lexical overlap but high cap pressure. |
| Task 73 terse | 0/30 | 0.227541 | 8.040 | 0/30 | 0.228499 | 7.576 | Cap fixed, but answers became too short. |
| Task 75 balanced | 0/30 | 0.261336 | 10.476 | 0/30 | 0.259867 | 9.484 | Partial overlap recovery, still unstable quality. |
| Task 77 evidence-focused | 0/30 | 0.267398 | 11.634 | 0/30 | 0.270660 | 10.573 | Slight overlap gain versus balanced, but wrong-negative/evidence-targeting failures remain. |
| Task 78 evidence-retention labels | n/a | n/a | n/a | n/a | n/a | n/a | 29 prompt-level audits: 10 retained-evidence/model-failed, 6 partial, 6 source/reference mismatch, 7 unclear, 0 broad missing-compressed-evidence cases. |

## Final QMSum Role Decision

QMSum remains a diagnostic long-context benchmark for:

- latency
- compression overhead
- prefill behavior
- compression ratio / input reduction
- lexical or normalized-text proxy quality

QMSum is not a final semantic correctness benchmark in this project unless future work adds manual review, an LLM judge, or another semantic evaluation layer.

## QMSum Quality Status

The frozen quality status is:

- lexical / normalized-text proxy only
- answer quality under compressed prompts remains unstable
- cap-hit and suffix preservation are controlled
- evidence targeting and wrong-negative issues remain
- Task 78 does not support broad compressed-evidence deletion as the main explanation

## QMSum Speed Status

QMSum remains useful for long-context efficiency analysis. It can show prefill behavior, compression cost, output length effects, and CC-DFlash versus LLMLingua-AR latency differences.

However, speed claims remain preliminary. Do not claim final speedup from QMSum.

## Frozen QMSum Policy Decision

| Question | Decision |
| --- | --- |
| Freeze Task 77 evidence-focused suffix as final quality fix? | No. It preserves the suffix but does not solve wrong-negative/evidence-targeting failures. |
| Keep tuning QMSum suffix indefinitely? | No. Tasks 73–78 are enough to characterize the current limitation for reporting. |
| Use Task 75 or Task 77 in diagnostic runs? | Allowed as implementation candidates, but neither proves semantic quality. |
| Treat QMSum as final semantic correctness evidence? | No. |

## Frozen Experiment Decision

| Question | Decision |
| --- | --- |
| Run QMSum n=100 now? | No. |
| Run `max_new_tokens=512` now? | No. |
| Continue QMSum prompt tuning before final report? | No. |
| Optional future work | Manual review, semantic judge, retrieval/reranking, or dataset/reference alignment audit. |

## Why QMSum n=100 Is Not Justified

QMSum n=100 is not justified because the current blocker is not sample size. The blocker is interpretation: QMSum quality is still lexical-proxy based, wrong-negative/evidence-targeting failures persist, and Task 78 did not turn those failures into a simple compression-deletion diagnosis.

Running more rows would add cost without resolving the semantic evaluation gap.

## Why mnt512 Is Not Needed

`max_new_tokens=512` is not needed because Tasks 73, 75, and 77 all controlled cap hits at `max_new_tokens=384` under protected QMSum suffixes. The remaining issue is not output cap pressure.

## Why More Suffix Tuning Is Not Justified

Tasks 73–77 already tested terse, balanced, and evidence-focused suffixes. The evidence-focused suffix preserved policy and cap behavior, but did not solve quality instability. Task 78 then showed that broad compressed-evidence deletion is not the main supported explanation. More suffix tuning would be speculative unless paired with semantic review or a retrieval/evidence-location intervention.

## Why QMSum Remains Useful

QMSum remains useful because it stresses the long-context path where compression should matter most. It measures input length reduction, compression overhead, prefill behavior, end-to-end latency, generated output length, and proxy quality tradeoffs.

The useful claim is diagnostic, not semantic: QMSum helps understand long-context system behavior.

## Final-Report Wording

English:

> QMSum is retained as a long-context diagnostic benchmark for latency, compression overhead, prefill behavior, and lexical proxy quality. Tasks 73–78 showed that cap pressure and protected-suffix preservation can be controlled, but compressed QMSum answer quality remains unstable. Evidence-targeting and wrong-negative failures persist, and Task 78 did not support broad compressed-evidence deletion as the main explanation. Therefore, QMSum results are reported as diagnostic evidence, not as final semantic correctness proof.

Vietnamese:

> QMSum được giữ như benchmark chẩn đoán long-context cho latency, compression overhead, prefill behavior và lexical proxy quality. Các Task 73–78 cho thấy có thể kiểm soát cap-hit và bảo toàn protected suffix, nhưng chất lượng trả lời QMSum dưới compressed prompt vẫn chưa ổn định. Lỗi bám evidence và wrong-negative vẫn còn, và Task 78 không cho thấy bằng chứng mạnh rằng compression xóa mất evidence là nguyên nhân chính. Vì vậy kết quả QMSum được báo cáo như diagnostic evidence, không phải bằng chứng semantic correctness cuối cùng.

## Forbidden Claims

- No final semantic correctness claim.
- No final speedup claim.
- No production or deployment readiness claim.
- No confirmed 8 GB deployment claim.
- No proven end-to-end compression benefit claim.
- No QMSum n=100 readiness claim.

## Outputs

| Output | Purpose |
| --- | --- |
| `results/phase_1_system_build_and_evaluation/early_experiments/task79_qmsum_reporting_decision.json` | Machine-readable reporting decision |
| `results/phase_1_system_build_and_evaluation/early_experiments/task79_qmsum_reporting_decision_table.csv` | Compact decision table |
| `docs/reports/79-qmsum-limitation-freeze-report.md` | Human-readable freeze report |

## Next Task Recommendation

Task 80 cross-dataset final result packaging.

Task 80 should package the current GSM8K and QMSum evidence with conservative language, preserving the split between GSM8K numeric quality evidence and QMSum long-context diagnostic evidence.

## Validation

Task 79B validation:

- `python3 -m compileall src tests scripts 2>&1 | tail -20`
- `python3 -m json.tool results/phase_1_system_build_and_evaluation/early_experiments/task79_qmsum_reporting_decision.json >/dev/null`
- Markdown fence balance for this report
- HTML sanity for changed docs

Understand-Anything refresh was skipped because `/understand` is not available in this environment.
