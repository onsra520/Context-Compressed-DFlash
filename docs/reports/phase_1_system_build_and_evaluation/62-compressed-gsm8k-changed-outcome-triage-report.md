# Task 62 — Compressed GSM8K Changed-Outcome Triage

Date: 2026-06-12

Status: PASS, read-only preliminary triage

## Scope

Task 62 analyzes Task 60 keep_rate=0.50 versus Task 61B keep_rate=0.67 compressed GSM8K artifacts. It does not run new benchmarks, load models, use CUDA, modify prior artifacts, or make final correctness/speedup claims.

## Precondition

Task 61B was already committed:

- `56b3567 test: calibrate compressed gsm8k at keep rate 67`

## Inputs

| Input | Purpose |
|---|---|
| `results/task60_gsm8k_short_llmlingua_ar_r2_n10_mnt256_suffixfix.jsonl` | Task 60 LLMLingua-AR-R2 keep_rate=0.50 artifact |
| `results/task60_gsm8k_short_cc_dflash_r2_n10_mnt256_suffixfix.jsonl` | Task 60 CC-DFlash-R2 keep_rate=0.50 artifact |
| `results/task61b_gsm8k_short_llmlingua_ar_r2_n10_mnt256_k067.jsonl` | Task 61B LLMLingua-AR-R2 keep_rate=0.67 artifact |
| `results/task61b_gsm8k_short_cc_dflash_r2_n10_mnt256_k067.jsonl` | Task 61B CC-DFlash-R2 keep_rate=0.67 artifact |
| `results/task61b_keep_rate67_changed_outcomes.jsonl` | Task 60 to Task 61B outcome map |
| `data/eval/gsm8k_100.jsonl` | Dataset metadata and question context |

## Outputs

| Output | Description |
|---|---|
| `scripts/phase_1_system_build_and_evaluation/analysis/t62_changed_outcome_triage.py` | Read-only changed-outcome triage analyzer |
| `tests/test_task62_changed_outcome_triage.py` | Lightweight CPU-only analyzer test |
| `results/task62_changed_outcome_triage_summary.json` | Machine-readable summary |
| `results/task62_changed_outcome_cases.jsonl` | Per-case triage rows |

## Summary

Task 60 and Task 61B both produced 8/10 numeric extraction matches for LLMLingua-AR-R2 and CC-DFlash-R2. Task 61B changed individual outcomes but did not improve the net result.

| Condition | FAIL_TO_PASS | PASS_TO_FAIL | SAME_FAIL | Cases triaged |
|---|---:|---:|---:|---:|
| LLMLingua-AR-R2 | 1 | 1 | 1 | 3 |
| CC-DFlash-R2 | 1 | 1 | 1 | 3 |

## Triage Label Counts

| Label | Count | Interpretation |
|---|---:|---|
| `K67_HURT_BY_EXTRA_CONTEXT_OR_GENERATION_VARIANCE` | 2 | k67 emitted a final-answer marker but regressed from a numeric match to a wrong numeric answer |
| `TRUNCATION_REMAINING` | 2 | k50 and k67 both hit the 256-token cap and failed |
| `UNCLEAR` | 2 | k67 changed failure to pass, but previews do not directly prove restored critical information |

No row received `K67_HELPED_COMPRESSION_LOSS`, because the available previews do not directly show that k67 restored missing answer-critical information compared with k50.

## Representative FAIL_TO_PASS Case

| Field | Value |
|---|---|
| Conditions | LLMLingua-AR-R2 and CC-DFlash-R2 |
| Dataset row | `gsm8k_short_test_0015` |
| Expected answer | `5` |
| k50 extracted answer | `50` |
| k67 extracted answer | `5` |
| Triage label | `UNCLEAR` |

The generated text at k50 and k67 both reason about weekly duck food and daily conversion. k67 reaches the correct final numeric answer, but the compressed prompt previews do not directly prove that a critical number or relation was absent at k50 and restored at k67. This is a real observed improvement, but not direct evidence of compression-loss repair.

## Representative PASS_TO_FAIL Case

| Field | Value |
|---|---|
| Conditions | LLMLingua-AR-R2 and CC-DFlash-R2 |
| Dataset row | `gsm8k_short_test_0004` |
| Expected answer | `12` |
| k50 extracted answer | `12` |
| k67 extracted answer | `3` |
| Triage label | `K67_HURT_BY_EXTRA_CONTEXT_OR_GENERATION_VARIANCE` |

The k50 output calculates 20 candles, 4 packs, and total cost `12`. The k67 output incorrectly reasons that James only needs 2 candles and therefore one pack costing `3`. Both outputs have final-answer markers and neither hits the token cap, so this looks like a quality instability or generation drift rather than a formatting issue.

## Remaining SAME_FAIL Case

| Field | Value |
|---|---|
| Conditions | LLMLingua-AR-R2 and CC-DFlash-R2 |
| Dataset row | `gsm8k_short_test_0082` |
| Expected answer | `6` |
| k50 extracted answer | `2` |
| k67 extracted answer | `300` for LLMLingua-AR-R2, `2` for CC-DFlash-R2 |
| Triage label | `TRUNCATION_REMAINING` |

Both keep rates hit the 256-token cap and fail to emit a final-answer marker. This row remains an output-length / prompt-control problem, not clear evidence about keep-rate quality.

## Decision

Does keep_rate=67 directly help compression loss?

- No direct evidence from previews. The FAIL_TO_PASS rows improve, but the available compressed/final previews do not show critical information missing at k50 and restored at k67.

Does keep_rate=67 introduce instability or extra-context drift?

- There is direct evidence of at least a regression pattern: both compressed conditions have one PASS_TO_FAIL row where k67 emits a final-answer marker with the wrong numeric answer after k50 passed.

Should keep_rate=80 be tested next?

- No. The current evidence does not justify a blind 80% keep-rate test. Net quality is unchanged, and k67 introduced pass-to-fail regressions.

Should n=30 be run next?

- Not as a blind quality claim. If the project needs confidence intervals, run n=30 with the default R2 keep_rate=0.50 and optionally a matched k67 comparison, using the same generated-text and preview metadata. Do not replace the default R2 setting with k67.

## Conservative Recommendation

Keep compressed calibration as-is for now:

- Keep R2 default at keep_rate=0.50 for the main speed-stress comparison.
- Do not test keep_rate=80 yet.
- If more evidence is needed, run an n=30 compressed GSM8K confidence check with keep_rate=0.50 and optionally k67, then compare changed outcomes again.
- For the persistent same-fail truncation row, consider prompt/output-control triage rather than more compression-rate changes.

## Validation

- Task 62 analyzer focused test: PASS
- Task 62 analyzer real artifact run: PASS
- Summary JSON validation: PASS
- No real benchmark, CUDA, model, or compressor run was performed.

Full validation command results are recorded in the final response.
