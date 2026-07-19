# Short-prompt and QMSum n=10 quality repair

## Technical summary

The bounded repair is complete and all requested hard gates pass. The `$20.` and written-fraction regressions are fixed, GSM8K compressed quality recovers from the earlier 3/10 to 5/10 and now matches both original conditions, and QMSum uses deterministic query-aware selected contexts rather than a word prefix. The result is **ready for a final n=20 validation run**, but not evidence that CC-DFlash improves end-to-end latency: QMSum C4 is 362.49 ms slower than C2 on mean pipeline E2E once compression cost is included.

## Root causes and fixes

The `$20.` false negative came from a numeric regex that rejected any following dot, including sentence punctuation. The repaired expression consumes decimals only when the dot is followed by a digit and otherwise ends the match before punctuation. Tests cover `$20.`, `$20,`, `3.5`, `1,200`, and `20%`; the real Raphael source sample preserves `$20.` after compression.

Written fractions were missing from the protector, while `remaining`, `left`, and `of` were absent from the relation inventory. The repaired protector recognizes all required written forms and protects their whole semantic clauses. The real Poppy sample preserves both `a quarter of the pieces` and `a third of the remaining pieces`.

Validation is now independent: the protector and normalized validator have separate extractors. A failed fact inventory retries at 0.90. A second failure emits the original prompt with `compression_applied=false`, `compression_status=FACT_SAFETY_FALLBACK`, a reason, and attempted rates. Such a row remains usable for generation but is not a compression success and is excluded from compression-ratio summaries.

## Adaptive compression policy

Target-user length is measured before compression using the target tokenizer. The validated config selects 0.85 below 128 tokens, 0.70 from 128 through 512, and 0.55 above 512. All three n=10 workloads performed ten successful CUDA compressions with zero fallback. Mock compression ratio remains diagnostic. GSM8K mean target-user keep rate is 0.9894; this small reduction is intentionally subordinate to fact safety.

## QMSum selector and consistency

The **QMSum query-aware budgeted-context benchmark** builds roughly 300-target-token speaker chunks, ranks them by normalized query overlap, exact entity/number overlap, transcript-relative rare-term weight, and phrase match, selects within 1,000 target tokens, and restores source order. The selector cannot accept the reference summary. Reference overlap is computed only afterward.

The locked n=10 rebuild is byte-identical across two constructions, raw inputs retain their hashes, selected contexts contain at most 986 target tokens, and minimum query-term coverage is 0.50. Config and runtime both declare `query_aware_budgeted`. Selected-context hashes match across C1–C4, and compressed-context hashes match across C3/C4.

## Results

| Workload | Hard result | C1 | C2 | C3 | C4 | Fallback |
|---|:---:|---:|---:|---:|---:|---:|
| Mock n=10 | PASS | 10/10 quality | 10/10 | 10/10 | 10/10 | 0/10 |
| GSM8K n=10 | PASS | 5/10 EM | 5/10 EM | 5/10 EM | 5/10 EM | 0/10 |
| QMSum n=10 | PASS | 0.1783 mean ROUGE-L F1 | 0.1796 | 0.1790 | 0.1783 | 0/10 |

All workloads have 40/40 successful measured rows, plus four successful warmups, no duplicates, complete expected keys, matching original/compressed prompt hashes, CUDA compression, empty GPU boundaries between conditions, and independently recomputed metrics. Canonical C1/C2 50/50 and mock-08 5/5 remain the frozen pre-repair correctness truth; this task did not alter the DFlash verifier or generation policy.

## QMSum C2 versus C4

| Metric, mean over n=10 | C2 | C4 | C4 minus C2 |
|---|---:|---:|---:|
| Generation latency | 2,057.37 ms | 1,954.19 ms | -103.18 ms |
| Compressor latency | 0 ms | 465.67 ms | +465.67 ms |
| Pipeline E2E | 2,057.37 ms | 2,419.85 ms | +362.49 ms |
| Decode throughput | 41.58 tok/s | 41.15 tok/s | -0.43 tok/s |
| Pipeline E2E throughput | 24.03 tok/s | 19.56 tok/s | -4.48 tok/s |

C4 reduces generation latency but does not repay the one-time compression cost on this measured request protocol. No CC-DFlash end-to-end speedup is claimed.

## PASS table

| Gate | Result |
|---|:---:|
| 95-test suite and compileall | PASS |
| Independent broken-fact detection | PASS |
| Targeted real-sample CUDA compression | PASS |
| Canonical C1/C2 50/50 frozen guard | PASS |
| Mock C1/C2 parity and 10/10 quality in C1–C4 | PASS |
| GSM8K C1/C2 parity and compressed EM non-regression | PASS |
| QMSum config/runtime selector consistency and deterministic rebuild | PASS |
| C1/C2 selected-context and C3/C4 compressed-context fairness | PASS |
| CUDA compressor, raw completeness, uniqueness, and metric recomputation | PASS |
| Non-empty QMSum outputs and recomputed quality proxy | PASS |

## FAIL and diagnostic table

| Item | Status | Interpretation |
|---|:---:|---|
| QMSum C1/C2 exact generated-token parity | 8/10, diagnostic FAIL | Two mismatches retained with first-token and decoded-output evidence; not relabeled. |
| QMSum C3/C4 exact generated-token parity | 8/10, diagnostic FAIL | Two mismatches retained; diagnostic only. |
| Mock C3/C4 exact generated-token parity | Diagnostic FAIL | Input/compressed hash parity and quality still pass. |
| GSM8K meaningful target-token reduction on every sample | Diagnostic FAIL | One prompt has no target-token reduction; compression ratio is not a hard gate. |
| Config memory sum warning | Warning | Nominal 6.0 + 2.25 GiB budgets exceed 8 GiB, but staged execution and measured CUDA gates pass. |

## Blockers and next step

There is no blocker to the specifically requested final n=20 validation. Remaining limitations are explicit: QMSum exact token parity remains diagnostic, QMSum quality is a lexical proxy rather than semantic proof, and C4 pipeline latency is worse than C2 at n=10. The final n=20 run should use the same source locks, adaptive policy, selector, single-compression cache reuse, and hard/diagnostic parity classification. No full benchmark was run in this task.
