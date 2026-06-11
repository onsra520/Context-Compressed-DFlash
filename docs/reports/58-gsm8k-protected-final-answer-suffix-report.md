# Task 58 — GSM8K Protected Final-Answer Suffix Report

Date: 2026-06-12

Status: PASS, prompt/metadata policy fix

## Scope

Task 58 fixes the prompt assembly issue found in Task 57. It does not run a real model, compressor, CUDA, QMSum, or n=100 benchmark.

Task 57 was already committed before this task:

- `bfa6ef2 test: triage compressed gsm8k prompt previews`

## What Was Wrong After Task 57

Task 57 found that Task 56 compressed GSM8K artifacts had complete compression metadata and `question_preserved=true`, but the strict final-answer instruction was visible in `0/20` compressed prompt previews.

The root cause was prompt segmentation:

- `scripts/eval_datasets.py` appended the final-answer instruction to the full GSM8K prompt text.
- `scripts/run_mvp.py` compressed only `item.context` and protected only `item.question`.
- The final-answer instruction was therefore not carried as a protected suffix in compressed prompt assembly.

## Fix

`scripts/run_mvp.py` now carries a `PromptItem.protected_suffix` for `gsm8k_short` rows. For GSM8K compressed conditions, `_prepare_cc_prompt()` builds the final prompt as:

```text
compressed_context

original_question

End with exactly one line:
Final answer: <number>
```

The protected suffix is appended after compression, outside the compressible context. The original math question remains the protected question passed to LLMLingua.

Baseline-AR and DFlash-R1 already use the dataset prompt text, which includes the final-answer instruction. Compressed conditions now get the same instruction as a post-compression suffix.

## Artifact Metadata Fields

Compressed rows produced by future runs now include:

- `protected_suffix_preserved`
- `protected_suffix_preview`
- `final_prompt_preview`
- `final_prompt_tail_preview`

`compressed_prompt_preview` now represents a head+tail preview of the actual final prompt sent to the model, so it can include both prompt beginning and protected suffix without storing the full prompt.

The existing fields remain:

- `question_preserved`
- `original_context_preview`
- `compressed_context_preview`
- `original_prompt_preview`
- `compressed_prompt_preview`
- `compression_ratio`
- `actual_compression_ratio`
- `original_input_tokens`
- `compressed_input_tokens`

## Tests Added or Updated

Updated `tests/test_compression.py`:

- Verifies `_prepare_cc_prompt()` appends the GSM8K final-answer instruction after compression.
- Verifies the LLMLingua-protected question remains only the original math question.
- Verifies `protected_suffix_preview`, `final_prompt_preview`, and `final_prompt_tail_preview` expose `Final answer: <number>`.
- Verifies long prompt previews still include the protected suffix via head+tail previewing.

Updated `tests/test_eval_datasets.py`:

- Verifies GSM8K dataset prompt items carry `protected_suffix=GSM8K_FINAL_ANSWER_INSTRUCTION`.
- Verifies the dry-run prompt still ends with `Final answer: <number>`.

## Benchmark Status

No real benchmark was run in this task. No model weights, tokenizer, compressor, or CUDA path was loaded. No old result artifacts were overwritten.

## Recommended Next Task

Task 59 should run a tiny GSM8K compressed metadata rerun, for example `n=1` or `n=3`, only for LLMLingua-AR-R2 and CC-DFlash-R2 if needed, to verify that new artifacts contain:

- `protected_suffix_preserved=true`
- `Final answer: <number>` in `final_prompt_preview`
- `Final answer: <number>` in `final_prompt_tail_preview`
- `question_preserved=true`

Only after that should the project consider `max_new_tokens=256`, gentler keep rates, or larger `n`.

## Validation

Validation commands and results are recorded in the final task response.

## Understand-Anything

`.understand-anything/meta.json` was read before task work. `/understand` refresh was skipped because `/understand` is not available in this environment.
