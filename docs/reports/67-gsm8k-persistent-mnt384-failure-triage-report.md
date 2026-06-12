# Task 67 — Read-only Triage of Persistent mnt384 GSM8K Compressed Failures

Date: 2026-06-13

Status: PASS, preliminary read-only analysis

## Scope

Task 67 analyzed persistent compressed GSM8K failures from the Task 66 `max_new_tokens=384` rerun. This was artifact analysis only: no benchmark execution, no model loading, no compressor loading, no CUDA, no QMSum, and no n=100 run.

Task 66 commit:

- `a512832 test: rerun compressed gsm8k mnt384 latency`

Inputs:

- `results/task66_gsm8k_short_llmlingua_ar_r2_n30_mnt384_rerun.jsonl`
- `results/task66_gsm8k_short_cc_dflash_r2_n30_mnt384_rerun.jsonl`
- `results/task66_mnt384_rerun_changed_outcomes.jsonl`
- `data/eval/gsm8k_100.jsonl`

Outputs:

- `scripts/analyze_task67_persistent_mnt384_failures.py`
- `tests/test_task67_persistent_mnt384_failures.py`
- `results/task67_persistent_mnt384_failure_summary.json`
- `results/task67_persistent_mnt384_failure_cases.jsonl`

## Summary

Both compressed conditions reproduced the same remaining quality shape:

| Condition | Rows | Numeric matches | Numeric failures | Cap hits | Cap-hit failures | Non-cap failures |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| LLMLingua-AR-R2 | 30 | 24 | 6 | 3 | 3 | 3 |
| CC-DFlash-R2 | 30 | 24 | 6 | 3 | 3 | 3 |

Overall label counts:

| Label | Count |
| --- | ---: |
| TRUNCATION_REMAINING | 6 |
| REASONING_FAIL | 6 |
| ANSWER_FORMAT_OR_EXTRACTION_ISSUE | 0 |
| COMPRESSION_LOSS_POSSIBLE | 0 |
| UNCLEAR | 0 |

The same row pattern appears in both compressed conditions. Task 66 changed-outcome rows remain `48 SAME_PASS` and `12 SAME_FAIL`, with no fail-to-pass or pass-to-fail rows versus Task 65.

## Representative Examples

### REASONING_FAIL

`gsm8k_short_test_0015`, both LLMLingua-AR-R2 and CC-DFlash-R2:

- Expected answer: `5`
- Extracted answer: `50`
- Generated output computes `35 / 7 = 5`, then ends with `Final answer: 50`.
- Interpretation: the deterministic extractor is doing the right thing by trusting the final-answer line. This is a completed wrong final answer, not an extraction miss.

`gsm8k_short_test_0089`, LLMLingua-AR-R2:

- Expected answer: `170`
- Extracted answer: `140`
- Generated output includes a final-answer marker with a wrong total after intermediate arithmetic.
- Interpretation: completed arithmetic/reasoning failure.

`gsm8k_short_test_0001`, LLMLingua-AR-R2:

- Expected answer: `2280`
- Extracted answer: `2180`
- Generated output reaches `Final answer: 2180`.
- Interpretation: completed arithmetic/reasoning failure.

### TRUNCATION_REMAINING

`gsm8k_short_test_0098`, LLMLingua-AR-R2:

- Expected answer: `1,600`
- Extracted answer: `0.02`
- Output tokens: `384`
- Final-answer marker: absent
- Interpretation: output hit the token cap while still reasoning through the lumber/stick calculation.

`gsm8k_short_test_0028`, LLMLingua-AR-R2:

- Expected answer: `18`
- Extracted answer: `12`
- Output tokens: `384`
- Final-answer marker: absent
- Interpretation: output hit the token cap during algebraic setup.

`gsm8k_short_test_0078`, LLMLingua-AR-R2:

- Expected answer: `64`
- Extracted answer: `4`
- Output tokens: `384`
- Final-answer marker: absent
- Interpretation: output hit the token cap during speed/distance reasoning.

## Compression Metadata Check

For all Task 66 compressed rows:

- `protected_suffix_preserved`: 30/30 per condition
- `question_preserved`: 30/30 per condition
- final prompt tail includes the protected `Final answer: <number>` instruction
- compression metadata is present

No Task 67 failure was labeled `COMPRESSION_LOSS_POSSIBLE` from available previews. This does not prove compression is harmless, but the current evidence does not justify changing keep rate before addressing the remaining truncation/reasoning split.

## Decision

mnt512 is not justified as the immediate next step. The remaining failures are split evenly between cap-hit truncation and completed wrong-answer reasoning, rather than being dominated by remaining truncation.

n=100 is conditionally justified only after report synthesis / final-run planning, not as an automatic next command. The evidence supports:

- Speed-oriented GSM8K setting: `max_new_tokens=256`, `keep_rate=0.50`, protected final-answer suffix.
- Quality-oriented GSM8K setting: `max_new_tokens=384`, `keep_rate=0.50`, protected final-answer suffix.

The conservative next step is to synthesize Task 60–67 evidence and decide whether to run a bounded n=100 quality-oriented pass or report the current compressed GSM8K state.

## Limitations

- This is read-only analysis of n=30 artifacts.
- Numeric extraction is a deterministic proxy, not final semantic correctness.
- QMSum was not analyzed in this task.
- No model rerun was performed.
- Compression-loss labels are limited by available preview metadata.

## Verification

Commands run:

- `PYTHONPATH=src .venv/bin/python -m pytest tests/test_task67_persistent_mnt384_failures.py -q`
- `PYTHONPATH=src .venv/bin/python scripts/analyze_task67_persistent_mnt384_failures.py`
- `python3 -m compileall src tests scripts 2>&1 | tail -20`
- `PYTHONPATH=src .venv/bin/python -m pytest tests/ -x -q 2>&1 | tail -30`
- `python3 -m json.tool results/task67_persistent_mnt384_failure_summary.json >/dev/null`
- HTML sanity checks for `<!DOCTYPE html>` and `</html>`
- Markdown fence balance checks for `instruction.md` and this report

Result: validation passed.
