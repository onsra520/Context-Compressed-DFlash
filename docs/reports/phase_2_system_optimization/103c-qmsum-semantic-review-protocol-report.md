# Task103C - QMSum Semantic Judge / Human Review Protocol

## 1. Purpose

Task103C prepares a controlled semantic-review protocol for the six residual QMSum target rows after Task103A showed deterministic evidence selection alone did not materially repair the failures.

This task is protocol/design/static packaging only. It did not run an LLM judge, perform human scoring, rerun QMSum, run a benchmark, run QMSum `n=100`, run a full matrix, run DFlash-R1/Large/GSM8K, tune keep-rate, change defaults, or download models/datasets.

## 2. Why Semantic Review Protocol Is Needed

Task103A result:

- Baseline-AR evidence-selected: `0/6` resolved, `4/6` unchanged, `2/6` worsened.
- CC-DFlash-R2 Light GPU evidence-selected: `0/6` resolved, `1/6` improved, `3/6` unchanged, `2/6` worsened.
- Interpretation: `GENERATION_OR_SEMANTIC_LIMITATION_REMAINS`.

The deterministic proxy cannot cleanly decide whether every residual row is a true semantic failure, a source/reference mismatch, a target-model grounding limitation, or a deterministic proxy limitation. Task103C therefore freezes a review packet and rubric before any optional review execution.

## 3. Inputs

Task103C reads existing artifacts only:

- Task102H remediation reassessment:
  `results/phase_2_system_optimization/final_reruns/task102h_qmsum_remediation_reassessment/task102h_before_after_row_assessment.jsonl`
- Task102I Baseline-AR mini-check:
  `results/phase_2_system_optimization/final_reruns/task102i_qmsum_baseline_ar_target_row_mini_check/summary/task102i_baseline_vs_cc_row_assessment.jsonl`
- Task103A selected evidence:
  `results/phase_2_system_optimization/final_reruns/task103a_qmsum_evidence_selector_before_answer/summary/task103a_selected_evidence.jsonl`
- Task103A before/after assessment:
  `results/phase_2_system_optimization/final_reruns/task103a_qmsum_evidence_selector_before_answer/summary/task103a_before_after_assessment.jsonl`
- Task103A comparison table:
  `results/phase_2_system_optimization/final_reruns/task103a_qmsum_evidence_selector_before_answer/tables/task103a_evidence_selector_comparison.csv`

## 4. Review Packet

Review packet artifact:

- `results/phase_2_system_optimization/final_reruns/task103c_qmsum_semantic_review_protocol/task103c_review_packet.jsonl`

Each review unit contains:

- `fixture_id`
- question
- reference answer
- selected source/evidence when available
- original CC-DFlash output
- remediated CC-DFlash output
- Baseline-AR output
- evidence-selected Baseline-AR output
- evidence-selected CC-DFlash output
- deterministic labels from T102H/T102I/T103A
- blank review fields for future approved review execution

Rows covered:

| Fixture ID                   |
| ---------------------------- |
| `qmsum_meeting_qa_test_0036` |
| `qmsum_meeting_qa_test_0070` |
| `qmsum_meeting_qa_test_0055` |
| `qmsum_meeting_qa_test_0078` |
| `qmsum_meeting_qa_test_0094` |
| `qmsum_meeting_qa_test_0001` |

## 5. Rubric

Rubric artifact:

- `results/phase_2_system_optimization/final_reruns/task103c_qmsum_semantic_review_protocol/task103c_review_rubric.json`

Allowed review labels:

| Label                                     | Meaning                                                                                                                          |
| ----------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| `correct_supported`                       | The answer directly addresses the question and is supported by the provided source/evidence packet.                              |
| `partially_correct_or_incomplete`         | The answer contains some supported information but omits required entities/actions/numbers/reasons or is materially incomplete.  |
| `unsupported_or_wrong`                    | The answer is contradicted by, unsupported by, or off-topic relative to the provided source/evidence packet.                     |
| `cannot_determine_from_available_context` | The packet does not provide enough context to distinguish model failure from source/reference mismatch or insufficient evidence. |

Scoring dimensions:

- answers the question
- uses correct evidence
- includes required entities/actions/numbers/reasons
- avoids hallucination
- avoids unsupported "not discussed"
- completeness
- reference/source mismatch risk

## 6. Option Matrix

Option matrix artifact:

- `results/phase_2_system_optimization/final_reruns/task103c_qmsum_semantic_review_protocol/task103c_option_matrix.json`

| Option | Summary                                               | Recommended when                                                  |
| ------ | ----------------------------------------------------- | ----------------------------------------------------------------- |
| A      | No semantic judge; freeze caveat                      | Phase 2 should continue with deterministic-only methodology.      |
| B      | Human review on six target rows                       | User wants a stronger QMSum semantic claim without an LLM judge.  |
| C      | LLM judge with fixed rubric and evidence packet       | Only after explicit approval for an LLM judge path.               |
| D      | Hybrid: human review only unresolved/conflicting rows | User wants stronger semantic evidence while keeping review small. |

Default guidance:

- Prefer Option B or D if the user wants a stronger semantic claim.
- Prefer Option A if Phase 2 should continue without changing methodology.
- Do not run an LLM judge automatically.

## 7. Claim Boundary

Claim boundary artifact:

- `results/phase_2_system_optimization/final_reruns/task103c_qmsum_semantic_review_protocol/task103c_claim_boundary.json`

Allowed wording:

- "A semantic review protocol was prepared for residual QMSum rows."
- "QMSum deterministic proxy limitations remain explicitly bounded."
- "The review packet can support a future approved human or judge review on six target rows."

Blocked wording:

- "QMSum semantic correctness is proven."
- "Human/LLM review was performed."
- "Query-aware compression is validated by T103C."
- "The full QMSum matrix is complete."
- "Residual QMSum risk is eliminated."

Claim status:

- `SEMANTIC_REVIEW_PROTOCOL_PREPARED`

## 8. Recommended Decision Paths

Next-task decision artifact:

- `results/phase_2_system_optimization/final_reruns/task103c_qmsum_semantic_review_protocol/task103c_next_task_decision.json`

Decision state:

- `USER_DECISION_REQUIRED`

Available paths:

- Stronger QMSum semantic claim: `T103C-R — QMSum Human/Semantic Review Execution`
- Deterministic-only methodology: `T103D — QMSum Deep Fix Closure Decision`
- Query-aware compression exploration: `T103B — Query-aware Compression Prototype`, only after preserving the T103A caveat

## 9. Roadmap Update

Task103C is recorded as `PASS` for protocol preparation.

T103C-R is added as an optional gated review-execution path. T103D remains the deterministic-only closure path. T103B remains planned/reserved, not the default next step. T104 speed-reference alignment remains waiting until QMSum deep-fix closure or explicit deferral.

## 10. Scope Confirmation

Task103C did not run:

- LLM judge
- human scoring
- benchmark
- model inference
- QMSum rerun
- QMSum `n=100`
- full matrix
- DFlash-R1
- Large CPU
- GSM8K
- keep-rate tuning
- default config switch
- model or dataset download

Task103C prepared only static protocol artifacts from existing evidence.
