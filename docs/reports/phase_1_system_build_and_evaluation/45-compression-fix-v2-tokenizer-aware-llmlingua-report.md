# Task 45-compression-fix-v2 — Tokenizer-Aware LLMLingua Chunking


> Deprecated note: This report refers to the earlier GSM8K+Wikipedia augmented dataset branch. That branch is no longer part of the active benchmark setup. The active setup uses GSM8K short-context numeric proxy and QMSum long-context diagnostic benchmark.

Date: 2026-06-06

## Result

PASS for tokenizer-aware LLMLingua input safety and tiny compressed-condition smoke.

Task 45 final benchmark remains PARTIAL. Baseline-AR and DFlash-R1 n=100 artifacts remain valid, but compressed n=100 artifacts are still missing or invalid until an explicit final rerun completes and passes artifact audit.

No final speedup, final correctness, deployment readiness, confirmed 8 GB deployment, or proven end-to-end compression benefit is claimed.

## Scope

Changed:

- `src/ccdf/compression/llmlingua.py`
- `scripts/run_mvp.py`
- `tests/test_compression.py`
- `tests/test_run_mvp_fixture_mode.py`
- `docs/Roadmap.html`
- `docs/CC-DFlash-Overview.html`

Verified:

- `instruction.md` already contains the required Understand-Anything refresh/check rule.

Created:

- `results/phase_1_system_build_and_evaluation/early_experiments/task45_compression_fix_v2_llmlingua_ar_r2_n3.jsonl`
- `results/phase_1_system_build_and_evaluation/early_experiments/task45_compression_fix_v2_cc_llm_r2_n3.jsonl`
- `logs/task45_compression_fix_v2_llmlingua_ar_r2_n3.log`
- `logs/task45_compression_fix_v2_cc_llm_r2_n3.log`
- `docs/reports/45-compression-fix-v2-tokenizer-aware-llmlingua-report.md`

## Root Cause of v1 Insufficiency

Task 45-compression-fix v1 split LLMLingua inputs by word chunks. That reduced the original failure symptom from `1483 > 512`, but did not enforce an encoder-safe invariant.

Latest failed LLMLingua n=100 rerun log:

```text
logs/task45_final_llmlingua_ar_r2_n100_2026-06-06_00-46-05.log
prompt_id=37 ... [transformers] Token indices sequence length is longer than the specified maximum sequence length for this model (728 > 512).
```

The value `728` is only a symptom. Future failures could be `650`, `899`, `1200`, or another value because word count is not equivalent to tokenizer length. The required fix target is the invariant:

```text
For every LLMLingua backend compression call:
token_count(actual_context_string) <= compressor_chunk_token_budget
```

## Tokenizer-Aware Fix

`LLMLinguaCompressor` now:

- Gets the tokenizer from the LLMLingua backend when available.
- Falls back to `transformers.AutoTokenizer.from_pretrained(model_name)` if needed.
- Uses fallback word-token estimates only as a last resort and marks the mode as `fallback_estimate`.
- Determines encoder max length from tokenizer/model config where possible.
- Uses a conservative default context budget of `384` tokens.
- Accounts for protected question overhead by reducing the context budget when needed:
  - `budget = min(configured_budget, encoder_max_length - question_tokens - margin)`
- Uses a default safety margin of `32` tokens.
- Splits context by tokenizer token windows when decoding support exists.
- Recursively splits any candidate chunk that still exceeds budget.
- Checks token count immediately before every backend call.
- Preserves chunk order and context coverage.
- Preserves the protected question unchanged and appends it after merged compressed chunks.

The discovered encoder max length in smoke artifacts is `512`.

Observed v2 smoke budgets:

- `compressor_chunk_encoder_max_length`: `512`
- `compressor_chunk_token_budget`: `383` or `384`
- `compressor_chunk_max_observed_tokens`: max `384`
- `compressor_chunking_mode`: `tokenizer`

## Metadata Added

The runner now forwards these tokenizer-aware metadata fields into compressed JSONL artifacts:

- `compressor_chunking_mode`
- `compressor_chunk_token_budget`
- `compressor_chunk_max_observed_tokens`
- `compressor_chunk_encoder_max_length`
- `compressor_chunk_safety_margin`
- `compressor_chunk_backend_calls`

Existing fields remain:

- `compression`
- `compressed_input_tokens`
- `strategy`
- `t_compress_ms`
- `R_actual`
- `N_original`
- `N_compressed`
- `keep_rate`
- `compressor_model`
- `question_preserved`
- `compressor_chunked`
- `compressor_chunk_count`

## n=100 Artifact State

Valid existing partial-final artifacts:

- `results/phase_1_system_build_and_evaluation/early_experiments/task45_final_baseline_ar_n100.jsonl`: `100` rows.
- `results/phase_1_system_build_and_evaluation/early_experiments/task45_final_dflash_r1_n100.jsonl`: `100` rows.

Missing compressed final artifacts:

- `results/phase_1_system_build_and_evaluation/early_experiments/task45_final_llmlingua_ar_r2_n100.jsonl`: missing, not a valid final artifact.
- `results/phase_1_system_build_and_evaluation/early_experiments/task45_final_cc_llm_r2_n100.jsonl`: missing, not run yet.

No valid compressed n=100 final benchmark artifact is claimed by this task.

## Tests

Added or updated CPU-only tests for:

- Synthetic long context exceeding 512 tokenizer tokens.
- Multiple tokenization patterns, including multi-token words and no-whitespace character text.
- Recursive splitting until every backend call is under budget.
- Protected question preservation.
- Deterministic chunking output for fixed input and fake backend.
- Tokenizer-aware metadata presence.
- `run_mvp` compressed fixture path avoiding over-budget fake backend calls.

Focused result:

```text
21 passed, 2 warnings
```

Full result:

```text
83 passed, 2 warnings
```

## Tiny Smoke Results

Dataset:

- `data/processed/gsm8k_wikipedia_augmented_full.jsonl`

Settings:

- `n=3`
- `max_new_tokens=128`
- `--store-generated-text`
- Transformers backend
- `flash_attn` not installed, torch SDPA fallback

### LLMLingua-AR-R2

Command:

```bash
PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --config config.yml --condition "LLMLingua-AR-R2" --prompt-source fixture --fixture data/processed/gsm8k_wikipedia_augmented_full.jsonl --n 3 --max-new-tokens 128 --store-generated-text --output results/phase_1_system_build_and_evaluation/early_experiments/task45_compression_fix_v2_llmlingua_ar_r2_n3.jsonl 2>&1 | tee logs/task45_compression_fix_v2_llmlingua_ar_r2_n3.log
```

Result: PASS.

Summary:

- Rows: `3`
- Average tok/s: `17.78`
- Average tau_mean: `0.00`
- Average `t_compress_ms`: `4281.40`
- Average `R_actual`: `2.08`
- Max VRAM allocated: `2.5024919509887695 GiB`
- Max VRAM reserved: `3.423828125 GiB`
- Chunk counts: `[4, 7]`
- Token budgets: `[383, 384]`
- Max observed chunk tokens: `384`
- Generated text stored: yes

### CC-LLM-R2

Command:

```bash
PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --config config.yml --condition "CC-LLM-R2" --prompt-source fixture --fixture data/processed/gsm8k_wikipedia_augmented_full.jsonl --n 3 --max-new-tokens 128 --store-generated-text --output results/phase_1_system_build_and_evaluation/early_experiments/task45_compression_fix_v2_cc_llm_r2_n3.jsonl 2>&1 | tee logs/task45_compression_fix_v2_cc_llm_r2_n3.log
```

Result: PASS.

Summary:

- Rows: `3`
- Average tok/s: `44.75`
- Average tau_mean: `4.98`
- Average `t_compress_ms`: `3923.23`
- Average `R_actual`: `2.08`
- Max VRAM allocated: `3.5108489990234375 GiB`
- Max VRAM reserved: `4.427734375 GiB`
- Chunk counts: `[4, 7]`
- Token budgets: `[383, 384]`
- Max observed chunk tokens: `384`
- Generated text stored: yes

## Smoke Log Warning Check

Command:

```bash
grep -RIn "sequence length is longer\|Traceback\|RuntimeError\|IndexError" logs/task45_compression_fix_v2_*_n3.log || true
```

Result: PASS. No matching encoder-length warning or runtime error appeared in the final v2 smoke logs.

## Artifact Audit

Command:

```bash
PYTHONPATH=src .venv/bin/python scripts/smoke_artifacts.py results/phase_1_system_build_and_evaluation/early_experiments/task45_compression_fix_v2_llmlingua_ar_r2_n3.jsonl results/phase_1_system_build_and_evaluation/early_experiments/task45_compression_fix_v2_cc_llm_r2_n3.jsonl
```

Result:

```text
PASS results/phase_1_system_build_and_evaluation/early_experiments/task45_compression_fix_v2_llmlingua_ar_r2_n3.jsonl condition=LLMLingua-AR-R2 rows=3 issues=0
PASS results/phase_1_system_build_and_evaluation/early_experiments/task45_compression_fix_v2_cc_llm_r2_n3.jsonl condition=CC-LLM-R2 rows=3 issues=0
```

## Understand-Anything Context

Before task work, `.understand-anything/meta.json` reported:

- `lastAnalyzedAt`: `2026-06-05T13:38:38.313379Z`
- `gitCommitHash`: `6e87fd48065a9b568ef27aa1ed3dfa245c4b0fd8`
- `analyzedFiles`: `163`

Understand-Anything refresh was skipped because `/understand` is not available in this environment.

`/understand-diff` was also skipped because slash commands are not available in this environment. The local skill instructions were inspected, but no graph/dashboard refresh is claimed.

## Validation

Commands run:

```bash
LOG=$(ls -t logs/task45_final_llmlingua_ar_r2_n100_*.log | head -1)
grep -n "Traceback\|RuntimeError\|IndexError\|sequence length\|LLMLingua" "$LOG" | tail -100
PYTHONPATH=src .venv/bin/python -m pytest tests/test_compression.py tests/test_run_mvp_fixture_mode.py -q
python3 -m compileall src tests scripts 2>&1 | tail -20
PYTHONPATH=src .venv/bin/python -m pytest tests/ -x -q 2>&1 | tail -30
PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --config config.yml --condition "LLMLingua-AR-R2" --prompt-source fixture --fixture data/processed/gsm8k_wikipedia_augmented_full.jsonl --n 3 --max-new-tokens 128 --store-generated-text --output results/phase_1_system_build_and_evaluation/early_experiments/task45_compression_fix_v2_llmlingua_ar_r2_n3.jsonl 2>&1 | tee logs/task45_compression_fix_v2_llmlingua_ar_r2_n3.log
PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --config config.yml --condition "CC-LLM-R2" --prompt-source fixture --fixture data/processed/gsm8k_wikipedia_augmented_full.jsonl --n 3 --max-new-tokens 128 --store-generated-text --output results/phase_1_system_build_and_evaluation/early_experiments/task45_compression_fix_v2_cc_llm_r2_n3.jsonl 2>&1 | tee logs/task45_compression_fix_v2_cc_llm_r2_n3.log
grep -RIn "sequence length is longer\|Traceback\|RuntimeError\|IndexError" logs/task45_compression_fix_v2_*_n3.log || true
wc -l results/phase_1_system_build_and_evaluation/early_experiments/task45_compression_fix_v2_*_n3.jsonl
PYTHONPATH=src .venv/bin/python scripts/smoke_artifacts.py results/phase_1_system_build_and_evaluation/early_experiments/task45_compression_fix_v2_llmlingua_ar_r2_n3.jsonl results/phase_1_system_build_and_evaluation/early_experiments/task45_compression_fix_v2_cc_llm_r2_n3.jsonl
```

Results:

- Failed n=100 LLMLingua log inspection: PASS, `728 > 512` warning confirmed.
- Focused tests: PASS, `21 passed, 2 warnings`.
- Compileall: PASS.
- Full pytest suite: PASS, `83 passed, 2 warnings`.
- LLMLingua-AR-R2 n=3 smoke: PASS.
- CC-LLM-R2 n=3 smoke: PASS.
- Final v2 smoke logs: PASS, no encoder-length warning/error pattern.
- v2 smoke artifact row counts: PASS, `3` rows each.
- v2 smoke artifact audit: PASS, zero issues.

## Next Step

Task 45 final benchmark can resume compressed n=100 conditions only when explicitly requested. Task 46 remains reserved for Pareto analysis after the full final benchmark and artifact audit are complete.
