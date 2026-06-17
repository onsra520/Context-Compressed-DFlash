# Task 45-compression-fix — LLMLingua Long-Context Input Safety


> Deprecated note: This report refers to the earlier GSM8K+Wikipedia augmented dataset branch. That branch is no longer part of the active benchmark setup. The active setup uses GSM8K short-context numeric proxy and QMSum long-context diagnostic benchmark.

Date: 2026-06-05

## Result

PASS for the compression safety fix and tiny compressed-condition smoke.

Task 45 final benchmark remains PARTIAL. Baseline-AR and DFlash-R1 n=100 artifacts exist, but the compressed n=100 final benchmark conditions were not rerun in this task.

No final speedup, final correctness, deployment readiness, confirmed 8 GB deployment, or proven end-to-end compression benefit is claimed.

## Scope

Changed:

- `src/ccdf/compression/llmlingua.py`
- `scripts/run_mvp.py`
- `tests/test_compression.py`
- `tests/test_run_mvp_fixture_mode.py`
- `docs/Roadmap.html`
- `docs/CC-DFlash-Overview.html`

Created:

- `results/phase_1_system_build_and_evaluation/early_experiments/task45_compression_fix_llmlingua_ar_r2_n2.jsonl`
- `results/phase_1_system_build_and_evaluation/early_experiments/task45_compression_fix_cc_llm_r2_n2.jsonl`
- `docs/reports/45-compression-fix-llmlingua-long-context-report.md`

## Root Cause

The latest Task 45 final benchmark log shows the compressed LLMLingua-AR-R2 condition crashed after the first two frozen n=100 conditions completed.

Observed log indicator:

```text
[transformers] Token indices sequence length is longer than the specified maximum sequence length for this model (1483 > 512). Running this sequence through the model will result in indexing errors
```

The runner passed the full long-context fixture row directly to `LLMLinguaCompressor.compress(context=..., question=...)`. The locked LLMLingua-2 model uses an XLM-RoBERTa encoder path with a 512-token positional limit, while the full source-mode dataset contains contexts around 500-1500 words and up to about 1950 tokenizer-estimated tokens.

This affected both compressed paths:

- `LLMLingua-AR-R2`
- `CC-LLM-R2`

## Fix Implemented

`LLMLinguaCompressor` now applies deterministic context chunking before calling LLMLingua:

- Split only the compressible context.
- Preserve the protected question unchanged.
- Pass the same `question=` value to every LLMLingua chunk compression call.
- Compress each chunk independently with the requested `keep_rate`.
- Merge compressed chunks in original order.
- Append the original protected question with `merge(...)`.
- Aggregate `N_original`, `N_compressed`, `R_actual`, and `t_compress_ms` across chunks.

Default chunk size:

- `max_context_words_per_chunk = 240`

This is a conservative word-window safety adaptation for the current Transformers backend. It is not blind truncation: all context chunks are processed.

New compression metadata forwarded into JSONL rows:

- `compression`
- `compressed_input_tokens`
- `strategy`
- `compressor_chunked`
- `compressor_chunk_count`
- `compressor_chunk_max_words`

Existing required compression fields remain:

- `t_compress_ms`
- `R_actual`
- `N_original`
- `N_compressed`
- `keep_rate`
- `compressor_model`
- `question_preserved`

## Tests Added

Added focused CPU-only tests for:

- Synthetic long context exceeding the old single-call encoder-safe length.
- No backend compression call receives a chunk above the configured limit.
- Protected question remains unchanged in merged prompt.
- Chunk metadata is reported.
- Chunked compression is deterministic for fixed input and fake backend.
- `run_mvp` fixture compression path can use the wrapper on a long fixture row without passing an over-long chunk to the fake LLMLingua backend.

Focused test result:

```text
20 passed, 2 warnings
```

Full test result:

```text
82 passed, 2 warnings
```

## Small Compressed Smoke

Dataset:

- `data/processed/gsm8k_wikipedia_augmented_full.jsonl`

Settings:

- `n=2`
- `max_new_tokens=128`
- `--store-generated-text`
- Transformers backend
- `flash_attn` not installed, torch SDPA fallback

### LLMLingua-AR-R2

Command:

```bash
PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --config config.yml --condition "LLMLingua-AR-R2" --prompt-source fixture --fixture data/processed/gsm8k_wikipedia_augmented_full.jsonl --n 2 --max-new-tokens 128 --store-generated-text --output results/phase_1_system_build_and_evaluation/early_experiments/task45_compression_fix_llmlingua_ar_r2_n2.jsonl
```

Result: PASS.

Summary:

- Rows: `2`
- Average tok/s: `15.69`
- Average tau_mean: `0.00`
- Average `t_compress_ms`: `4465.50`
- Average `R_actual`: `2.11`
- Max VRAM allocated: `2.502490520477295 GiB`
- Max VRAM reserved: `3.18359375 GiB`
- Chunk counts: `[5]`
- Generated text stored: yes

### CC-LLM-R2

Command:

```bash
PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --config config.yml --condition "CC-LLM-R2" --prompt-source fixture --fixture data/processed/gsm8k_wikipedia_augmented_full.jsonl --n 2 --max-new-tokens 128 --store-generated-text --output results/phase_1_system_build_and_evaluation/early_experiments/task45_compression_fix_cc_llm_r2_n2.jsonl
```

Result: PASS.

Summary:

- Rows: `2`
- Average tok/s: `39.35`
- Average tau_mean: `5.22`
- Average `t_compress_ms`: `4473.54`
- Average `R_actual`: `2.11`
- Max VRAM allocated: `3.510848045349121 GiB`
- Max VRAM reserved: `4.1875 GiB`
- Chunk counts: `[5]`
- Generated text stored: yes

## Artifact Contract Check

Command:

```bash
PYTHONPATH=src .venv/bin/python scripts/smoke_artifacts.py results/phase_1_system_build_and_evaluation/early_experiments/task45_compression_fix_llmlingua_ar_r2_n2.jsonl results/phase_1_system_build_and_evaluation/early_experiments/task45_compression_fix_cc_llm_r2_n2.jsonl
```

Result:

```text
PASS results/phase_1_system_build_and_evaluation/early_experiments/task45_compression_fix_llmlingua_ar_r2_n2.jsonl condition=LLMLingua-AR-R2 rows=2 issues=0
PASS results/phase_1_system_build_and_evaluation/early_experiments/task45_compression_fix_cc_llm_r2_n2.jsonl condition=CC-LLM-R2 rows=2 issues=0
```

## Interpretation

The immediate LLMLingua long-context encoder safety blocker is mitigated for the current full source-mode dataset path. The compressed conditions can now process the first two full-source rows without the prior 512-token failure, while preserving protected questions and reporting compression metadata.

This is not final benchmark evidence. The Task 45 final benchmark remains incomplete until the compressed n=100 frozen conditions are rerun and audited under the Task 44 schema and quality policy.

## Understand-Anything Context

Task bootstrap read `.understand-anything/meta.json` as required by `instruction.md`.

No Understand-Anything refresh was run because this repository documents the metadata check but does not provide a required refresh command for this task. The latest metadata file reported:

- `lastAnalyzedAt`: `2026-06-05T13:38:38.313379Z`
- `analyzedFiles`: `163`

## Validation

Commands run:

```bash
LOG=$(ls -t logs/task45_final_benchmark_*.log | head -1)
grep -n "Traceback\|RuntimeError\|IndexError\|sequence length\|LLMLingua" "$LOG" | tail -80
PYTHONPATH=src .venv/bin/python -m pytest tests/test_compression.py tests/test_run_mvp_fixture_mode.py -q
python3 -m compileall src tests scripts 2>&1 | tail -20
PYTHONPATH=src .venv/bin/python -m pytest tests/ -x -q 2>&1 | tail -30
PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --config config.yml --condition "LLMLingua-AR-R2" --prompt-source fixture --fixture data/processed/gsm8k_wikipedia_augmented_full.jsonl --n 2 --max-new-tokens 128 --store-generated-text --output results/phase_1_system_build_and_evaluation/early_experiments/task45_compression_fix_llmlingua_ar_r2_n2.jsonl
PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --config config.yml --condition "CC-LLM-R2" --prompt-source fixture --fixture data/processed/gsm8k_wikipedia_augmented_full.jsonl --n 2 --max-new-tokens 128 --store-generated-text --output results/phase_1_system_build_and_evaluation/early_experiments/task45_compression_fix_cc_llm_r2_n2.jsonl
wc -l results/phase_1_system_build_and_evaluation/early_experiments/task45_compression_fix_*_n2.jsonl
PYTHONPATH=src .venv/bin/python scripts/smoke_artifacts.py results/phase_1_system_build_and_evaluation/early_experiments/task45_compression_fix_llmlingua_ar_r2_n2.jsonl results/phase_1_system_build_and_evaluation/early_experiments/task45_compression_fix_cc_llm_r2_n2.jsonl
```

Results:

- Latest Task 45 log inspection: PASS, root-cause warning found.
- Focused tests: PASS, `20 passed, 2 warnings`.
- Compileall: PASS.
- Full pytest suite: PASS, `82 passed, 2 warnings`.
- LLMLingua-AR-R2 n=2 smoke: PASS.
- CC-LLM-R2 n=2 smoke: PASS.
- Smoke artifact row counts: PASS, `2` rows each.
- Smoke artifact audit: PASS, zero issues.

## Next Step

Resume Task 45 final benchmark for compressed n=100 conditions only if the user explicitly requests it. Keep Task 46 reserved for Pareto analysis after the full final benchmark and artifact audit are complete.
