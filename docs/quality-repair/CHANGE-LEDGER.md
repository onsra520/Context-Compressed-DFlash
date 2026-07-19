# Quality repair change ledger

| Change | Contract effect | Verification |
|---|---|---|
| Independent normalized fact inventory | Detects lost/added currencies, numbers, percentages, fractions, units, relations, negations, durations, and output constraints. | Targeted loss tests pass. |
| Protector number and sentence parsing | `$20.` is protected as `$20`; decimal dots require a following digit. | Five parsing cases plus real GSM row 158 pass. |
| Written fractions and relation clauses | Preserves complete clauses containing written fractions, remaining/left, each/per/of, and durations. | Parameterized span tests plus real GSM row 104 pass. |
| Adaptive target-token policy | Replaces fixed 0.50 default with validated 0.85/0.70/0.55 tiers. | Boundary tests and every cache row pass. |
| Retry and explicit fallback | Retries at 0.90 and makes unresolved samples generation-eligible with explicit fallback fields. | Retry and fallback unit tests pass; fallback excluded from success counts. |
| Query-aware QMSum selection | Replaces prefix words with target-token-budgeted speaker chunks and deterministic lexical ranking. | Determinism, tie-break, budget, reorder, and no-reference-input tests pass. |
| QMSum context-only compression | Keeps query/instruction stable while compressing only selected context once. | Selected-context hash shared C1–C4; compressed-context hash shared C3/C4. |
| Manifest/raw schemas | Records policy, attempts, final status, target token counts, context hashes, and three keep-rate levels. | Unified schema and raw completeness pass in all runs. |
| Audit policy | Keeps QMSum exact-token parity diagnostic, adds GSM EM non-regression and C2/C4 E2E comparison. | Mock, GSM8K, and QMSum audits pass. |

Execution outcomes: 95 tests pass; targeted two-sample compression passes on CUDA; mock, GSM8K, and QMSum each complete 10 samples × 4 measured conditions with zero failed rows and zero fallbacks. No full benchmark was run.
