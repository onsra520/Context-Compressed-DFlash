# Task 109 — GSM8K Balanced Numeric Residual Repair

**Date**: 2026-06-26
**Condition**: CC-DFlash-R2 Light GPU
**Dataset**: `gsm8k_short` (seed 42, n=100, max_new_tokens=256)

## Purpose
T107A identified that T106B's `gsm8k_concise_final_answer_v1` policy introduced or exposed 5 CC-only wrong-numeric rows, including cases where compressed context was missing needed detail or reasoning was overcompressed. This task audits the wrong-numeric residual and tests a candidate policy (`gsm8k_numeric_detail_preserve_v1`) designed to preserve necessary arithmetic steps and details without sacrificing cap-limited behavior.

## Policy Details
**Candidate Policy Name**: `gsm8k_numeric_detail_preserve_v1`
**Policy Suffix**:
> Use only the numbers and conditions given in the problem. Keep the reasoning concise but include all necessary arithmetic steps. Do not skip units or constraints. End with exactly one line in the format: Final answer: `<number>`. Do not continue after the final answer.

## Key Results (n=100)

| Metric | T106B (Concise) | T107B (Minimal Verify) | T109 (Detail Preserve) |
|---|---:|---:|---:|
| Strict Correct | 88/100 | 85/100 | 82/100 |
| Cap-Limited | 2/100 | 2/100 | 8/100 |
| Strict Wrong Numeric | 10/100 | 13/100 | 10/100 |
| Avg e2e time | 2.145s | 1.910s | ~2.5s* |

*\*Estimated from run logs. See summary JSON for exact times.*

## Audit Findings
The T107A audit on T106B's 10 wrong-numeric rows identified 5 rows shared with references (Baseline-AR/DFlash-R1), 3 rows resolved from cap-limited status, and 2 rows explicitly missing context/detail. Because there were >=2 CC-only wrong-numeric rows that could theoretically benefit from detail preservation, a T109 rerun was justified.

## Evaluation & Decision
- **Decision**: PASS_WITH_CAVEAT
- **Candidate Selection**: **T106B (`gsm8k_concise_final_answer_v1`) remains the best scoped candidate.**
- **Reasoning**: The T109 policy caused strict correct to drop from 88 to 82, and cap-limited failures to increase from 2 to 8. Wrong numeric failures did not improve (stayed at 10). Preserving more detail forced longer outputs, hitting the token cap more often without improving numeric extraction accuracy.
- **Next Task**: Proceed to T110 — QMSum Semantic Validation / Judge Protocol.

## Claim Boundaries
- T109 balances the GSM8K candidate search after T106B/T107B.
- T106B's concise policy remains the best candidate for GSM8K quality proxy and cap-limit balance.
- Default switch is blocked. Full quality solution remains unproven.

## Validation
- T109 analyzer script and test coverage added.
- All artifact contracts generated successfully.
