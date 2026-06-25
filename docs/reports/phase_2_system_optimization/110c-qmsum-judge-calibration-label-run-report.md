# Task 110C — QMSum Judge Calibration / Targeted Label Run

**Date**: 2026-06-26
**Condition**: Local validation targeted judge run
**Validation Model**: `Qwen3.5-9B-UD-Q4_K_XL.gguf` via `llama_cpp` (n_ctx=8192, full GPU offload)

## 1. Purpose
Run the local Qwen3.5-9B GGUF validation judge on the six QMSum target rows that constitute our residual semantic risk. The goal is to evaluate both the T105B (CC-DFlash-R2) candidates and the T108B (repaired evidence-grounded) candidates to provide calibration evidence. 

## 2. Load & Parse Status
- **Status**: Loaded successfully via `llama_cpp`.
- **Judged Rows**: 12 total runs (6 rows for T105B and 6 rows for T108B).
- **Valid JSON Generated**: 12/12 (100% success).
- **JSON Repair Fallback**: 0.

## 3. Human Calibration Alignment
The judge outputs for T105B were compared against the existing T103D human labels for these 6 rows.
- **Total compared**: 6
- **Alignments**: 1
- **Disagreements**: 5
*Note: The judge only aligned with human labels on 1/6 rows. The judge's calibration indicates that it does not strictly mimic human ground truth evaluation on this specific subset.*

## 4. T105B vs. T108B Judge Delta
Comparing the judge's assigned rank for T105B versus T108B on the same fixture rows:
- **Improved**: 2
- **Unchanged**: 4
- **Regressed**: 0
While T108B showed two proxy improvements under this specific judge schema, human calibration divergence means we cannot definitively conclude that the risk is semantically eliminated.

## 5. Constraint & Scope Compliance
- No benchmark iterations or model inferences using target/draft generator models were executed.
- **QMSum semantic correctness remains unclaimed**. The judge labels represent calibration evidence, not final ground truth.
- The default pipeline switch remains strictly unauthorized.

## 6. Next Task
**T110D — QMSum Judge Result Interpretation**
Because the label parse success was 100% and it provided a T105B vs. T108B comparison, the pipeline status is `TARGETED_JUDGE_LABELS_READY` and the decision is `PASS_WITH_CAVEAT`. The next phase will interpret these divergences to determine the final system closure state.
