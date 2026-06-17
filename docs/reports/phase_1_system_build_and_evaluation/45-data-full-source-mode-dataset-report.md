# Task 45-data — Full Source-Mode Dataset Generation and Audit


> Deprecated note: This report refers to the earlier GSM8K+Wikipedia augmented dataset branch. That branch is no longer part of the active benchmark setup. The active setup uses GSM8K short-context numeric proxy and QMSum long-context diagnostic benchmark.

Date: 2026-06-05

## Result

BLOCKED.

Task 45-data attempted the full source-mode dataset readiness path, but the required local source inputs are not available in the current environment. The full source-mode GSM8K + Wikipedia dataset was not generated, and no full source-mode dataset audit was run.

No final benchmark was run. No target model, draft model, tokenizer, compressor, CUDA path, vLLM, SGLang, Docker, or scale-up path was used.

## Scope

Inspected:

- `scripts/create_dataset.py`
- `scripts/audit_dataset.py`
- `results/phase_1_system_build_and_evaluation/early_experiments/task45_prep_source_mode_readiness.json`
- `docs/reports/45-prep-full-dataset-schema-audit-report.md`

Checked current environment/source availability without downloading datasets.

## Source-Mode Input Check

| Check | Result | Evidence |
| --- | --- | --- |
| `datasets` package installed | yes | `.venv` can import/find the package |
| Local Hugging Face GSM8K cache | no | No local `openai___gsm8k`, `gsm8k`, or Hugging Face dataset cache directory was found |
| Local Wikipedia JSONL source | no | Only `data/processed/gsm8k_wikipedia_augmented_smoke.jsonl` was found under the allowed `data/` search |
| Existing sample-mode artifact | yes | `data/processed/gsm8k_wikipedia_augmented_smoke.jsonl`, 5 rows, `source_mode: sample` |
| Existing full source-mode artifact | no | `data/processed/gsm8k_wikipedia_augmented_full.jsonl` does not exist |

## Dataset Generation Decision

The full source-mode dataset was not generated.

Reason:

- The builder can use `source_mode=hf`, but GSM8K is not locally cached.
- The builder can accept `--gsm8k-jsonl` and `--wikipedia-jsonl`, but no local source JSONL files were found.
- The task explicitly requires a clean BLOCKED/PARTIAL report when dependencies or local source files are missing.
- The task does not authorize external dataset downloads.

Calling the 5-row sample artifact full source-mode would violate the frozen Task 44 dataset policy, so Task 45 remains blocked.

## Audit Decision

The full source-mode dataset audit was not run because the full source-mode dataset artifact does not exist.

No `results/phase_1_system_build_and_evaluation/early_experiments/task45_source_mode_dataset_audit_summary.json` was created.

## Current Dataset State

| Artifact | Status | Notes |
| --- | --- | --- |
| `data/processed/gsm8k_wikipedia_augmented_smoke.jsonl` | Exists | 5-row sample-mode artifact only |
| `data/processed/gsm8k_wikipedia_augmented_full.jsonl` | Missing | Required before final benchmark |
| `results/phase_1_system_build_and_evaluation/early_experiments/task45_source_mode_dataset_audit_summary.json` | Missing | Must be produced after full source-mode generation |

## Required Unblock Inputs

Provide one of these source paths before rerunning Task 45-data:

1. Local JSONL sources:
   - GSM8K JSONL with question/answer fields
   - Wikipedia JSONL with title/text fields

2. Local/cache source path:
   - Cached GSM8K dataset available to the `datasets` package
   - Local Wikipedia JSONL source

Once available, rerun a command shaped like:

```bash
PYTHONPATH=src .venv/bin/python scripts/create_dataset.py --output data/processed/gsm8k_wikipedia_augmented_full.jsonl --max-samples 100 --min-context-words 500 --max-context-words 1500 --seed 41 --split test --source-mode hf --gsm8k-jsonl /path/to/gsm8k.jsonl --wikipedia-jsonl /path/to/wikipedia.jsonl
```

Then audit:

```bash
PYTHONPATH=src .venv/bin/python scripts/audit_dataset.py --input data/processed/gsm8k_wikipedia_augmented_full.jsonl --output results/phase_1_system_build_and_evaluation/early_experiments/task45_source_mode_dataset_audit_summary.json
```

## Gate Decision

Task 45 final benchmark remains BLOCKED.

Resolved before this task:

- Frozen artifact schema audit exists.
- Frozen artifact schema tests pass.

Still blocking:

- Full source-mode GSM8K + Wikipedia dataset is missing.
- Full source-mode dataset audit summary is missing.
- Final benchmark artifacts cannot be accepted until the full dataset and audit gates pass.

## Validation

Commands run:

```bash
python3 -m compileall src tests scripts
PYTHONPATH=src .venv/bin/python -m pytest tests/ -x -q
```

Results:

- Compileall: PASS.
- Pytest suite: PASS, `77 passed, 2 warnings`.
- Markdown fence balance for this report: PASS.
- HTML sanity for `docs/Roadmap.html` and `docs/CC-DFlash-Overview.html`: PASS.

## Next Step

Task 45-data-inputs: provide or stage local source-mode GSM8K and Wikipedia JSONL/cache inputs, then rerun Task 45-data. Do not run Task 45 final benchmark until the full source-mode dataset exists and `scripts/audit_dataset.py` passes on that artifact.
