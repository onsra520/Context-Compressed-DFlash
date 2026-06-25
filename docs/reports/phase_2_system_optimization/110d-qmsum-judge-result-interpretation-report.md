# Task 110D — QMSum Judge Result Interpretation

**Date**: 2026-06-26
**Condition**: Static interpretation of targeted judge labels

## 1. Purpose
Interpret the T110C judge labels, compare the judge behavior against prior T103D human labels, decide whether the T108B repair improved QMSum enough to change the core claims, and establish the final QMSum semantic boundary for Phase 2 closure.

## 2. T110C Technical Result
The judge execution in T110C was technically flawless. The local `Qwen3.5-9B-UD-Q4_K_XL.gguf` model loaded successfully with all layers offloaded to the GPU. The model successfully parsed all 12 candidate outputs into perfectly bounded JSON (12/12, with 0 regex repair fallbacks).

## 3. Human-Label Calibration Result
Calibration against human ground truth was extremely poor:
- **Alignment**: 1/6
- **Disagreement**: 5/6
- **Calibration Status**: `LOW_ALIGNMENT`
**Conclusion**: Because the judge diverges heavily from the previously established human review protocol, the judge outputs cannot be treated as calibrated ground truth. They serve only as auxiliary evidence.

## 4. T105B vs T108B Judge Delta
Comparing the optimized CC-DFlash candidate (T105B) to the repaired candidate (T108B), the judge identified:
- **Improved**: 2
- **Unchanged**: 4
- **Regressed**: 0

## 5. Deterministic Proxy versus Judge Interpretation
The prior deterministic proxy analysis showed `0/6` improvements and `2/6` safer-but-uninformative responses. While the LLM judge saw `2/6` improvements, this signal is undermined by its low human-label calibration. 
**Conclusion**: The T108B repair signal remains mixed and is insufficient to validate a full QMSum repair.

## 6. Final QMSum Semantic Boundary
Given the mixed proxy metrics and the uncalibrated judge feedback, we set the following final semantic boundaries for QMSum:
- `qmsum_semantic_correctness`: `NOT_CLAIMED`
- `qmsum_residual_risk`: `REMAINS`
- `t108b_repair_status`: `NOT_VALIDATED_AS_REPAIR`
- `judge_status`: `AUXILIARY_EVIDENCE_ONLY`
- `qmsum_final_status`: `FINAL_LIMITATION_AFTER_REPAIR_AND_JUDGE_ATTEMPT`

## 7. Supported Claims
- T110C technically validated the local judge pipeline.
- Judge labels are auxiliary evidence because human-label alignment was low.
- T108B showed limited judge-positive signal, but not enough to validate QMSum repair.
- QMSum remains a final limitation after repair and judge attempts.

## 8. Blocked Claims
- QMSum semantic correctness is proven.
- QMSum residual risk is eliminated.
- T108B repaired QMSum.
- Judge labels are ground truth.
- CC-DFlash wins QMSum.
- Default switch is authorized.

## 9. Next Task
**T111 — Final Phase 2 Closure Pack**
Interpretation is complete, and QMSum claims are finalized as limitations. The system is ready to proceed to final Phase 2 closure and packaging.

## 10. Scope Confirmation
No generative tasks, benchmark matrix updates, new inferences, or code modifications to defaults were made during this static interpretation phase.
