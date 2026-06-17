# Task 55 — GSM8K Final-Answer and Compression Audit Policy Report

Date: 2026-06-11

Status: PASS, policy and schema update

## Scope

Task 55 improves GSM8K quality reliability before any larger benchmark by updating prompt policy, numeric extraction priority, and compressed-condition audit metadata.

No n=100 run was performed. No real model, compressor, CUDA, or benchmark run was performed. Existing result artifacts were not overwritten.

Task 54 was already committed before this task:

- `8c13959 test: triage compressed gsm8k quality failures`

## Prompt Policy Changes

GSM8K prompts now include the strict final-answer instruction:

```text
End with exactly one line:
Final answer: <number>
```

The loader also appends this instruction when an older `gsm8k_short` dataset row is missing it. This preserves compatibility with existing committed `data/eval/gsm8k_100.jsonl` rows while making future prompt construction follow the stricter policy.

The original question remains preserved in the prompt.

## Extractor Changes

Numeric extraction now checks marked answers in this order:

1. `Final answer: <number>`
2. GSM8K `#### <number>`
3. Other answer markers such as `Answer: <number>`
4. Existing fallback last-number extraction

The selected answer prefers `Final answer:` when present, while diagnostic candidates remain ordered by their position in the text so ambiguity reporting stays useful.

## Compression Audit Metadata

Compressed prompt preparation now emits audit metadata for future compressed benchmark rows:

- `keep_rate`
- `R_actual`
- `compression_ratio`
- `actual_compression_ratio`
- `N_original`
- `N_compressed`
- `original_input_tokens`
- `compressed_input_tokens`
- `t_compress_ms`
- `question_preserved`
- `original_context_preview`
- `compressed_context_preview`
- `original_prompt_preview`
- `compressed_prompt_preview`

Preview fields are capped to a short safe length instead of storing full prompts. Non-compressed Baseline-AR rows continue to report `compression=none` and do not claim compressed preview metadata.

## Files Changed

- `scripts/eval_datasets.py`
- `scripts/fetch_dataset.py --dataset gsm8k_eval`
- `scripts/run_mvp.py`
- `scripts/phase_1_analysis/analyze_task47_quality_refinement.py`
- `tests/test_eval_datasets.py`
- `tests/test_compression.py`
- `tests/test_task47_quality_refinement.py`
- `docs/Roadmap.html`
- `docs/CC-DFlash-Overview.html`
- `instruction.md`

## Tests Added or Updated

- GSM8K builder emits the exact final-answer-line instruction.
- GSM8K loader appends the instruction for older rows.
- Numeric extractor prefers `Final answer:` over GSM8K `####` markers.
- Compressed prompt preparation emits capped audit previews and compression ratio aliases.
- Non-compressed rows do not claim compressed prompt/context preview metadata.

## Validation

Commands run:

- `PYTHONPATH=src .venv/bin/python -m pytest tests/test_eval_datasets.py tests/test_compression.py tests/test_task47_quality_refinement.py -q`
- `PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --prompt-source dataset --dataset gsm8k_short --n 3 --seed 42 --dry-run-prompts`
- Prompt tail check through `_select_prompt_items`
- `python3 -m compileall src tests scripts 2>&1 | tail -20`
- `PYTHONPATH=src .venv/bin/python -m pytest tests/ -x -q 2>&1 | tail -30`
- `find docs -name "*.html" -exec grep -L "<!DOCTYPE html>" {} \;`
- `find docs -name "*.html" -exec grep -L "</html>" {} \;`
- Markdown fence balance for `instruction.md` and this report

Validation results are recorded in the final task response.

## Limitations

- This task does not prove improved GSM8K quality because no real calibration benchmark was run.
- Existing Task 53 artifacts do not gain retroactive compressed prompt previews.
- Future compressed quality runs must create new artifacts to use the new audit metadata.

## Next Step

Run a tiny GSM8K compressed calibration only after this policy change, using unique output paths, generated-text storage, `--resume`, and a slightly larger output cap such as `max_new_tokens=192` or `256`. Do not run n=100 yet.

## Understand-Anything

`.understand-anything/meta.json` was read before task completion. `/understand` refresh was skipped because `/understand` is not available in this environment.
