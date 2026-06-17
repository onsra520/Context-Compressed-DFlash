# Task 45-prep — Full Source-Mode Dataset and Frozen Schema Audit Prep


> Deprecated note: This report refers to the earlier GSM8K+Wikipedia augmented dataset branch. That branch is no longer part of the active benchmark setup. The active setup uses GSM8K short-context numeric proxy and QMSum long-context diagnostic benchmark.

Date: 2026-06-05

## Result

PARTIAL.

Task 45-prep implements the missing frozen Task 44 artifact-schema audit and documents the full source-mode dataset path, but Task 45 remains blocked because full source-mode GSM8K + Wikipedia data is not available in the current environment.

No final benchmark was run. No model, compressor, CUDA, vLLM, SGLang, Docker, or scale-up path was used.

## Scope

- Inspected Task 41 dataset builder:
  - `scripts/create_dataset.py`
  - `tests/test_create_dataset.py`
- Inspected Task 42 dataset audit:
  - `scripts/audit_dataset.py`
  - `tests/test_audit_dataset.py`
- Inspected existing smoke artifact audit:
  - `scripts/smoke_artifacts.py`
- Added frozen Task 44 artifact schema audit:
  - `scripts/frozen_benchmark_schema.py`
- Added frozen schema tests:
  - `tests/test_frozen_benchmark_schema.py`
- Checked local source-mode data/cache availability without downloading datasets.
- Created readiness artifact:
  - `results/task45_prep_source_mode_readiness.json`

## Frozen Schema Audit

New script:

```bash
PYTHONPATH=src .venv/bin/python scripts/frozen_benchmark_schema.py <artifact.jsonl>
```

The audit enforces:

- Required common fields from Task 44.
- `generated_text` required and non-empty.
- `generated_token_count` required.
- `max_new_tokens >= 128`.
- `t_prefill_ms` and `t_prefill_mode` required.
- Prefill VRAM fields required and nullable.
- Compression fields required and nullable for no-compression rows.
- Compression fields required and non-null for compression rows.
- `draft_path` required and nullable for AR rows.
- Dataset identifier required via one of `dataset_id`, `fixture_id`, or `id`.
- `expected_answer`, `evidence`, and `domain` required.
- AR rows require empty `acceptance_lengths`, `tau_mean == 0.0`, `generation_mode == "autoregressive"`, and `draft_used == false`.
- DFlash/CC rows require non-empty acceptance lengths when `output_tokens > 0` and `draft_used == true`.

## Frozen Schema Tests

Added tests cover:

- PASS case with nullable compression fields for `DFlash-R1`.
- FAIL case for missing `generated_text`.
- FAIL case for `max_new_tokens < 128`.
- PASS for `Baseline-AR` with empty `acceptance_lengths` and `tau_mean == 0.0`.
- PASS for compression rows with required non-null compression fields.
- FAIL for compression rows when nullable/frozen fields are missing.

## Source-Mode Dataset Readiness

Current state:

| Check | Result |
| --- | --- |
| Sample artifact present | yes |
| Full source-mode artifact present | no |
| Local Hugging Face GSM8K cache present | no |
| `datasets` package installed | no |
| Local Wikipedia JSONL source present | no |
| Full source-mode dataset generated | no |
| Full source-mode dataset audited | no |

Existing local artifact:

- `data/processed/gsm8k_wikipedia_augmented_smoke.jsonl`
- 5 rows
- `source_mode: sample`

Readiness artifact:

- `results/task45_prep_source_mode_readiness.json`

## Documented Full Source-Mode Command Path

With local JSONL sources:

```bash
PYTHONPATH=src .venv/bin/python scripts/create_dataset.py --output data/processed/gsm8k_wikipedia_augmented_full.jsonl --max-samples 100 --min-context-words 500 --max-context-words 1500 --seed 41 --split test --source-mode hf --gsm8k-jsonl /path/to/gsm8k.jsonl --wikipedia-jsonl /path/to/wikipedia.jsonl
```

With Hugging Face GSM8K cache and local Wikipedia JSONL:

```bash
PYTHONPATH=src .venv/bin/python scripts/create_dataset.py --output data/processed/gsm8k_wikipedia_augmented_full.jsonl --max-samples 100 --min-context-words 500 --max-context-words 1500 --seed 41 --split test --source-mode hf --wikipedia-jsonl /path/to/wikipedia.jsonl
```

Audit command after generation:

```bash
PYTHONPATH=src .venv/bin/python scripts/audit_dataset.py --input data/processed/gsm8k_wikipedia_augmented_full.jsonl --output results/task45_source_mode_dataset_audit_summary.json
```

## Gate Decision

Task 45 remains BLOCKED.

Resolved in this task:

- Frozen Task 44 schema audit script exists.
- Frozen schema tests exist and pass.

Still blocking:

- Full source-mode GSM8K + Wikipedia dataset is not generated.
- Full source-mode dataset audit is not available.
- A real final benchmark artifact cannot pass frozen schema audit until Task 45 produces one.

## Validation

Commands run:

```bash
python3 -m compileall src tests scripts
PYTHONPATH=src .venv/bin/python -m pytest tests/ -x -q
python3 -m json.tool results/task45_prep_source_mode_readiness.json
PYTHONPATH=src .venv/bin/python scripts/frozen_benchmark_schema.py /tmp/task45_frozen_schema_valid.jsonl
```

Results:

- Compileall: PASS.
- Pytest suite: PASS, `77 passed, 2 warnings`.
- Readiness JSON validation: PASS.
- Frozen schema audit CLI temp check: PASS.
- Markdown fence balance for this report: PASS.
- HTML sanity for `docs/Roadmap.html` and `docs/CC-DFlash-Overview.html`: PASS.

## Next Step

Task 45-data: provide or install source-mode dataset inputs, generate `data/processed/gsm8k_wikipedia_augmented_full.jsonl`, and run `scripts/audit_dataset.py` on it. Task 45 final benchmark must remain blocked until that dataset gate passes.
