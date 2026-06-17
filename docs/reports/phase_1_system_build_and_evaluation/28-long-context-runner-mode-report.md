# 28 Long-Context Runner Mode Report

## Task Title and Date

- Task: Add long-context runner mode using the Task 25 fixture
- Date: 2026-06-04

## Scope

This task adds minimal fixture-mode support to the existing MVP smoke runner. It does not run the Phase 2 benchmark matrix, does not change model/runtime behavior, and does not make any speedup or benchmark conclusions.

## CLI Changes

Added to `scripts/run_mvp.py`:

- `--prompt-source smoke|fixture`
- `--fixture PATH`

Default behavior remains:

- `--prompt-source smoke`
- no fixture required
- existing built-in smoke prompts are used

Fixture example for a future pilot:

- `PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --config config.yml --condition DFlash-R1 --n 6 --prompt-source fixture --fixture tests/fixtures/long_context_smoke.jsonl --output results/task29_dflash_fixture_n6.jsonl`

This command is documented as a future shape only; Task 28 did not run the benchmark.

## Fixture Behavior

Fixture mode reads JSONL rows from the supplied fixture path. Each selected row builds the generation prompt as:

- `context`
- blank line
- `question`

Selection behavior:

- `prompt_id` remains stable and one-based for the selected run.
- if `n` is larger than the fixture size, rows cycle in fixture order.
- if `n` is smaller than the fixture size, only the first `n` selected rows are used.

## Compression Behavior

For `CC-LLM-R2`, `CC-LLM-R3`, `LLMLingua-AR-R2`, and `LLMLingua-AR-R3`:

- fixture `context` is the compressible content
- fixture `question` is passed as the protected question
- the merged prompt preserves the original fixture question

For `DFlash-R1`:

- no compression is applied
- the prompt is `context + question`

Answer correctness checking is intentionally not added in this task. Expected-answer metadata is carried through for Task 30.

## Artifact Metadata Changes

When fixture mode is used, output JSONL rows include:

- `prompt_source: fixture`
- `fixture_id`
- `domain`
- `expected_answer`
- `evidence`
- `approximate_context_words`

Smoke mode does not add these fixture fields, so existing smoke artifact shape is not changed unnecessarily.

## Backward Compatibility Notes

Existing commands continue to work without new flags:

- `PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --config config.yml --condition DFlash-R1 --n 3 --output results/some_file.jsonl`

The built-in prompt list and cycling behavior remain unchanged for smoke mode.

## Verification Commands and Results

Commands run:

- `python3 -m compileall src tests scripts`
- `PYTHONPATH=src .venv/bin/python -m pytest tests/test_compression.py tests/test_smoke_artifact_audit.py tests/test_long_context_fixture.py tests/test_task24_analysis.py -q`
- `PYTHONPATH=src .venv/bin/python -m pytest tests/test_run_mvp_fixture_mode.py -q`
- `PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --help`

Results:

- `compileall`: PASS
- existing lightweight pytest set: PASS
- fixture-mode pytest file: PASS
- `run_mvp.py --help`: PASS, shows `--prompt-source` and `--fixture`

## Limitations

- No GPU benchmark was run.
- No Task 29 matrix artifact was created.
- No answer correctness checking was added.
- No final speedup or compression-value claim is supported.
- The runner still uses the existing Transformers backend assumptions.

## Next Step

Task 29: run an `n=6` long-context pilot across DFlash, CC-LLM, and AR paths.
