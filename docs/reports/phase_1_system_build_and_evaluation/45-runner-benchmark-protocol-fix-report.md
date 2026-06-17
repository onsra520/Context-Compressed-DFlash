# Task 45-runner-benchmark-protocol-fix — Warm-Up and Incremental Artifact Protocol


> Deprecated note: This report refers to the earlier GSM8K+Wikipedia augmented dataset branch. That branch is no longer part of the active benchmark setup. The active setup uses GSM8K short-context numeric proxy and QMSum long-context diagnostic benchmark.

Date: 2026-06-06

## Result

PASS for runner protocol hardening and tiny condition-agnostic smoke verification.

Task 45 final benchmark remains PARTIAL. Existing Baseline-AR and DFlash-R1 n=100 artifacts remain untouched, and compressed n=100 artifacts still require an explicit resumed final run under the fixed protocol.

No final speedup, final correctness, deployment readiness, confirmed 8 GB deployment, or proven end-to-end compression benefit is claimed.

## Scope

Changed:

- `scripts/run_mvp.py`
- `tests/test_run_mvp_fixture_mode.py`
- `docs/Roadmap.html`
- `docs/CC-DFlash-Overview.html`

Created:

- `docs/reports/45-runner-benchmark-protocol-fix-report.md`
- `results/task45_runner_fix_llmlingua_ar_r2_n3.jsonl`
- `results/task45_runner_fix_cc_llm_r2_n3.jsonl`
- `results/task45_runner_fix_baseline_ar_n1.jsonl`
- `results/task45_runner_fix_dflash_r1_n1.jsonl`
- `logs/task45_runner_fix_llmlingua_ar_r2_n3.log`
- `logs/task45_runner_fix_cc_llm_r2_n3.log`
- `logs/task45_runner_fix_baseline_ar_n1.log`
- `logs/task45_runner_fix_dflash_r1_n1.log`

## Root Cause

The latest LLMLingua-AR-R2 n=100 rerun log stopped after prompt 74:

```text
logs/task45_final_llmlingua_ar_r2_n100_2026-06-06_01-25-53.log
prompt_id=74 input_tokens=738 output_tokens=128 generation_time_s=7.3666 tok/s=17.38 acceptance_lengths=[] tau_mean=0.00 t_prefill_ms=234.68
```

There was no final summary and no valid JSONL artifact. The runner had accumulated rows in memory and wrote the artifact only at the end, so an interruption after many successful prompts lost all measured rows.

This task classifies the issue as benchmark protocol/artifact durability, not DFlash generation logic and not tokenizer-length safety.

## Protocol Fix

`scripts/run_mvp.py` now uses benchmark protocol `per_prompt_jsonl_v1`:

- Runs warm-up prompts before measured prompts.
- Excludes warm-up rows from measured JSONL artifacts.
- Writes each measured prompt row immediately after completion.
- Flushes and `fsync`s the JSONL file after each row.
- Refuses to silently overwrite existing output files.
- Adds explicit `--overwrite` for replacement runs.
- Adds explicit `--resume` for append/resume runs.
- Rejects `--resume` and `--overwrite` used together.
- Validates resume rows for condition, stable prompt indexes, range, and duplicates.
- Prints per-prompt start, finish, and write-progress logs.
- Prints final PASS only after the output artifact has the expected measured row count.

## Artifact Schema Additions

Each measured row now includes:

- `row_written_at_utc`
- `benchmark_prompt_index`
- `is_warmup`
- `warmup_prompts`
- `resume_enabled`
- `resumed_from_rows`
- `output_write_mode`
- `output_path`
- `benchmark_protocol_version`
- `tokens_per_second`

The existing `tok_per_sec` field remains for backward compatibility.

Condition-specific behavior is preserved:

- Baseline-AR: target-only autoregressive path, no compression, no draft.
- DFlash-R1: target + draft speculative path, no compression.
- LLMLingua-AR-R2: compression + target-only autoregressive path.
- CC-LLM-R2: compression + target + draft speculative path.

## Tiny Smoke Results

These are protocol proof smokes only, not final benchmark results.

Dataset:

- `data/processed/gsm8k_wikipedia_augmented_full.jsonl`

Common settings:

- Transformers backend
- `flash_attn` not installed, torch SDPA fallback
- `--prompt-source fixture`
- `--store-generated-text`
- `--warmup-prompts 1`
- `--overwrite`

| Artifact | Condition | Measured rows | Warm-up rows written | Average tok/s | Average tau_mean | Average t_compress_ms | Average R_actual | Max VRAM allocated GiB | Max VRAM reserved GiB | Status |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `results/task45_runner_fix_llmlingua_ar_r2_n3.jsonl` | LLMLingua-AR-R2 | 3 | 0 | 16.49 | 0.00 | 4081.54 | 2.08 | 2.5024919509887695 | 3.423828125 | PASS |
| `results/task45_runner_fix_cc_llm_r2_n3.jsonl` | CC-LLM-R2 | 3 | 0 | 39.61 | 4.98 | 4169.98 | 2.08 | 3.5108489990234375 | 4.427734375 | PASS |
| `results/task45_runner_fix_baseline_ar_n1.jsonl` | Baseline-AR | 1 | 0 | 13.46 | 0.00 | 0.00 | 0.00 | 2.50250244140625 | 3.326171875 | PASS |
| `results/task45_runner_fix_dflash_r1_n1.jsonl` | DFlash-R1 | 1 | 0 | 21.40 | 3.89 | 0.00 | 0.00 | 3.5108561515808105 | 4.341796875 | PASS |

## Commands Run

LLMLingua-AR-R2:

```bash
PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --config config.yml --condition "LLMLingua-AR-R2" --prompt-source fixture --fixture data/processed/gsm8k_wikipedia_augmented_full.jsonl --n 3 --warmup-prompts 1 --max-new-tokens 128 --store-generated-text --overwrite --output results/task45_runner_fix_llmlingua_ar_r2_n3.jsonl
```

CC-LLM-R2:

```bash
PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --config config.yml --condition "CC-LLM-R2" --prompt-source fixture --fixture data/processed/gsm8k_wikipedia_augmented_full.jsonl --n 3 --warmup-prompts 1 --max-new-tokens 128 --store-generated-text --overwrite --output results/task45_runner_fix_cc_llm_r2_n3.jsonl
```

Baseline-AR:

```bash
PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --config config.yml --condition "Baseline-AR" --prompt-source fixture --fixture data/processed/gsm8k_wikipedia_augmented_full.jsonl --n 1 --warmup-prompts 1 --max-new-tokens 32 --store-generated-text --overwrite --output results/task45_runner_fix_baseline_ar_n1.jsonl
```

DFlash-R1:

```bash
PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --config config.yml --condition "DFlash-R1" --prompt-source fixture --fixture data/processed/gsm8k_wikipedia_augmented_full.jsonl --n 1 --warmup-prompts 1 --max-new-tokens 32 --store-generated-text --overwrite --output results/task45_runner_fix_dflash_r1_n1.jsonl
```

## Validation

Compile:

```text
python3 -m compileall src tests scripts 2>&1 | tail -20
PASS
```

Tests:

```text
PYTHONPATH=src .venv/bin/python -m pytest tests/ -x -q 2>&1 | tail -30
90 passed, 2 warnings in 4.20s
```

Log failure scan:

```text
grep -RIn "sequence length is longer\|Traceback\|RuntimeError\|IndexError" logs/task45_runner_fix_*.log || true
PASS: no matches
```

Row counts:

```text
1 results/task45_runner_fix_baseline_ar_n1.jsonl
3 results/task45_runner_fix_cc_llm_r2_n3.jsonl
1 results/task45_runner_fix_dflash_r1_n1.jsonl
3 results/task45_runner_fix_llmlingua_ar_r2_n3.jsonl
```

JSONL protocol inspection:

- Every row had `is_warmup == false`.
- Every row had `benchmark_protocol_version == "per_prompt_jsonl_v1"`.
- Every row had `output_write_mode == "overwrite"`.
- Every row had `generated_text`.
- Prompt indexes were stable and complete for each tiny smoke.

## Understand-Anything Status

The existing `instruction.md` sync rule was verified. The latest known Understand-Anything metadata remains read from `.understand-anything/meta.json` when available.

Understand-Anything refresh and diff commands were skipped in this environment because slash-command execution is not available here. No stale hard-coded Understand node was added to project docs.

## Remaining Work

Task 45 final benchmark is still PARTIAL:

- Baseline-AR n=100 artifact exists and was not overwritten.
- DFlash-R1 n=100 artifact exists and was not overwritten.
- LLMLingua-AR-R2 n=100 must be rerun or resumed under `per_prompt_jsonl_v1`.
- CC-LLM-R2 n=100 must be run under `per_prompt_jsonl_v1`.
- Final artifacts must pass frozen-schema audit before Task 46 Pareto analysis.

## Next Step

Resume Task 45 compressed-condition n=100 runs using:

- `--warmup-prompts 1`
- `--resume` when continuing a partial artifact
- `--overwrite` only when intentionally replacing a tiny smoke or invalid artifact
- `--max-new-tokens 128`
- `--store-generated-text`

