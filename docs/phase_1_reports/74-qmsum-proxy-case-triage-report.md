# Task 74 - QMSum Concise-Policy Proxy and Case Triage

Date: 2026-06-13

## Result

PASS_WITH_NOTES.

Task 74 performed a read-only case-level triage of the Task 73 QMSum concise-answer calibration. No benchmark was run, no model/compressor/CUDA path was loaded, and no existing Task 71 or Task 73 artifacts were modified.

Task 73 commit: `67718b7 test: refine qmsum concise output policy`.

## Artifacts Analyzed

| Artifact | Rows | Role |
|---|---:|---|
| `results/task71_qmsum_long_llmlingua_ar_r2_n30_mnt384.jsonl` | 30 | Task 71 LLMLingua before concise policy |
| `results/task71_qmsum_long_cc_dflash_r2_n30_mnt384.jsonl` | 30 | Task 71 CC-DFlash before concise policy |
| `results/task73_qmsum_long_llmlingua_ar_r2_n30_mnt384_concise.jsonl` | 30 | Task 73 LLMLingua after concise policy |
| `results/task73_qmsum_long_cc_dflash_r2_n30_mnt384_concise.jsonl` | 30 | Task 73 CC-DFlash after concise policy |
| `results/task71_qmsum_n30_full_matrix_summary.json` | 4 conditions | Reference summary |
| `results/task73_qmsum_concise_policy_summary.json` | 2 conditions | Reference summary |
| `results/task73_qmsum_concise_policy_cases.jsonl` | 91 rows | Reference changed-case list |

## Outputs

| Artifact | Purpose |
|---|---|
| `scripts/analyze_task74_qmsum_proxy_case_triage.py` | Read-only case triage analyzer |
| `tests/test_task74_qmsum_proxy_case_triage.py` | CPU-only analyzer tests |
| `results/task74_qmsum_proxy_case_summary.json` | Machine-readable summary |
| `results/task74_qmsum_proxy_case_table.csv` | Per-condition summary table |
| `results/task74_qmsum_proxy_case_samples.jsonl` | Per-prompt labels and snippets |

## Cap-Hit Fix Summary

| Condition | Task 71 Cap Hits | Task 73 Cap Hits | Result |
|---|---:|---:|---|
| LLMLingua-AR-R2 | 22/30 | 0/30 | Fixed cap hits |
| CC-DFlash-R2 | 21/30 | 0/30 | Fixed cap hits |

The concise policy successfully removed the cap-hit failure mode at `max_new_tokens=384`.

## Proxy Degradation Summary

| Condition | Before Avg Overlap | After Avg Overlap | Before Avg Output Tokens | After Avg Output Tokens |
|---|---:|---:|---:|---:|
| LLMLingua-AR-R2 | 0.358644 | 0.227541 | 348.53 | 48.50 |
| CC-DFlash-R2 | 0.357483 | 0.228499 | 345.33 | 48.67 |

The overlap drop is not explained solely by the proxy being strict about wording. The case labels show many concise answers omit key reference details, so the current 1-3 sentence policy should be revised rather than frozen as final.

## Label Counts

| Label | Count |
|---|---:|
| ANSWER_TOO_SHORT_OR_UNSUPPORTED | 51 |
| TRUNCATION_FIXED | 6 |
| UNCLEAR | 2 |
| TRUE_QUALITY_DEGRADATION_POSSIBLE | 1 |

By condition:

| Condition | Label Counts |
|---|---|
| LLMLingua-AR-R2 | ANSWER_TOO_SHORT_OR_UNSUPPORTED 26; TRUNCATION_FIXED 3; UNCLEAR 1 |
| CC-DFlash-R2 | ANSWER_TOO_SHORT_OR_UNSUPPORTED 25; TRUNCATION_FIXED 3; TRUE_QUALITY_DEGRADATION_POSSIBLE 1; UNCLEAR 1 |

## Representative Examples

| Label | Condition | Prompt ID | Interpretation |
|---|---|---:|---|
| ANSWER_TOO_SHORT_OR_UNSUPPORTED | CC-DFlash-R2 | 1 | Concise answer mentions the intelligent controller and speech/gesture recognition, but misses important reference details about convenience, reliability limits, differentiation, and replacement motivation. |
| ANSWER_TOO_SHORT_OR_UNSUPPORTED | CC-DFlash-R2 | 2 | Concise answer discusses microphone issues but misses the reference emphasis that lapel microphones were too close and captured breath/non-voice sounds. |
| TRUNCATION_FIXED | CC-DFlash-R2 | 10 | Concise answer preserves core remote-control product goals and avoids cap hit; overlap remains reasonably high. |
| TRUNCATION_FIXED | CC-DFlash-R2 | 15 | Concise answer includes the target selling price, profit aim, and international sales direction; this is a useful cap-hit fix case. |
| TRUE_QUALITY_DEGRADATION_POSSIBLE | CC-DFlash-R2 | 9 | Concise answer shifts to generic transition support and misses the reference detail about Sharon Davies and team-around-the-family support. |
| UNCLEAR | LLMLingua-AR-R2 / CC-DFlash-R2 | 8 | Overlap improves, but the generated answer contains extra interpretive material, so semantic quality is unclear without manual review. |

## LLMLingua vs CC-DFlash under Task 73

| Metric | LLMLingua-AR-R2 | CC-DFlash-R2 |
|---|---:|---:|
| Rows | 30 | 30 |
| Cap hits | 0 | 0 |
| Avg overlap | 0.227541 | 0.228499 |
| Policy preservation | 30/30 | 30/30 |
| Avg e2e latency from Task 73 summary | 8.04 s | 7.58 s |

CC-DFlash-R2 still roughly matches LLMLingua-AR-R2 on the current proxy and remains faster end-to-end in the Task 73 artifacts. This remains preliminary and should not be treated as a final speedup or correctness claim.

## Decision

| Question | Decision |
|---|---|
| Is the overlap drop mostly proxy mismatch? | No. Some cases may be proxy-sensitive, but most labeled cases appear too short or missing key details under lexical evidence. |
| Should the concise policy be kept as final? | No. Revise to a balanced QMSum answer policy. |
| Should the policy be rejected entirely? | Not entirely. It fixed cap hits, so keep the protected-suffix mechanism and tune wording. |
| Is `max_new_tokens=512` still needed? | No. Cap pressure was removed at mnt384. |
| Is QMSum n=100 justified? | No. Blocked until prompt/proxy policy is resolved. |

Recommended next task:

Task 75 should implement and test a balanced QMSum prompt policy, such as asking for a concise but complete answer that covers all key facts from the reference-style answer, without long reasoning or full context repetition.

## Conservative Interpretation

Task 74 supports this bounded conclusion only:

- QMSum compressed cap hits can be fixed without increasing output length.
- The current concise policy is too terse for the normalized-overlap proxy and likely loses answer details.
- A balanced answer policy should be tested before QMSum n=100.
- No final speedup, semantic correctness, deployment, 8 GB, or proven end-to-end compression benefit claim is supported.

## Validation

Validation commands were run after code, report, and documentation updates. Results are summarized in the final response for Task 74.

Understand-Anything refresh was skipped because `/understand` is not available in this environment, and a broad graph refresh could scan forbidden archive/deprecated/backup paths.
