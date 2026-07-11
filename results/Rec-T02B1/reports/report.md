# Rec-T02B1 - Single-Prompt Runner

Status: PASS

## Scope

Rec-T02B1 added the `ccdf run` single-prompt CLI for direct prompt, context/question, and canonical fixture execution. The CLI uses `ccdf.runtime.execute_request`, the same request path used by `ccdf.benchmark.execution.synthetic_row`, so demo/debug execution is not a separate implementation.

The runner does not write canonical benchmark results. `--save` writes only under `results/Rec-T02B1/`.

## Implementation

- Added `src/ccdf/cli.py` and `src/ccdf/__main__.py`.
- Added console entry point `ccdf = ccdf.cli:main` in `pyproject.toml`.
- Added shared request executor in `src/ccdf/runtime/request.py`.
- Rewired Rec-T02B synthetic benchmark execution through the shared request executor.
- Added CLI tests in `tests/test_rec_t02b1_cli.py`.

## Required Artifacts

- `results/Rec-T02B1/cli_contract.json`
- `results/Rec-T02B1/smoke_baseline.json`
- `results/Rec-T02B1/smoke_dflash.json`
- `results/Rec-T02B1/logs/`

Additional retained evidence:

- `results/Rec-T02B1/logs/fixture_profile.json`
- `results/Rec-T02B1/logs/text_mode.log`
- `results/Rec-T02B1/baseline-ar_ad_hoc_ad_hoc_prompt_benchmark.json`

## Smoke Results

Direct prompt baseline:

- Command: `python -m ccdf run --condition baseline-ar --prompt "How many positive divisors does 196 have?" --format json`
- Result: PASS
- Measurement mode: `benchmark`
- Answer: `Final answer: 9`

Direct prompt DFlash:

- Command: `python -m ccdf run --condition dflash-r1 --prompt "How many positive divisors does 196 have?" --format json`
- Result: PASS
- Measurement mode: `benchmark`
- Answer: `Final answer: 9`

Canonical fixture/profile smoke:

- Command: `python -m ccdf run --condition dflash-r1 --dataset gsm8k --fixture-id <Rec-T02A fixture> --profile --format json`
- Result: PASS
- Measurement mode: `profiling`
- Fixture answer label: `strict_correct`

Text mode smoke:

- Command: `python -m ccdf run --condition baseline-ar --prompt "How many positive divisors does 196 have?"`
- Result: PASS
- Output includes Condition, Answer, Input tokens, Output tokens, Request latency, Generation tok/s, and Stop reason.

## Checks

Commands:

```bash
PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_rec_t02b_benchmark_contract.py tests/test_rec_t02b1_cli.py
PYTHONPATH=src .venv/bin/python -m ccdf run --condition baseline-ar --prompt "How many positive divisors does 196 have?" --format json
PYTHONPATH=src .venv/bin/python -m ccdf run --condition dflash-r1 --prompt "How many positive divisors does 196 have?" --format json
PYTHONPATH=src .venv/bin/python -m ccdf run --condition dflash-r1 --dataset gsm8k --fixture-id <fixture_id> --profile --format json
PYTHONPATH=src .venv/bin/python -m pytest -q
```

Results:

- Focused B/B1 tests: `15 passed`
- Full available test suite: `25 passed`

## Gate Decision

PASS.

Gate evidence:

- Direct prompt execution works.
- Canonical fixture execution works.
- Text and JSON modes work.
- Profile mode is marked with `measurement_mode=profiling`.
- Single-prompt and benchmark synthetic execution share `ccdf.runtime.execute_request`.
- No notebook is required for demo execution.
- Validation failures exit non-zero.
