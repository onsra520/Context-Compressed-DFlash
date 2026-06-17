# Task 42 — Dataset Audit


> Deprecated note: This report refers to the earlier GSM8K+Wikipedia augmented dataset branch. That branch is no longer part of the active benchmark setup. The active setup uses GSM8K short-context numeric proxy and QMSum long-context diagnostic benchmark.

Date: 2026-06-04

## Result

PASS, sample-mode audit.

Task 42 added a dataset audit utility and audited the Task 41 dev-safe GSM8K + Wikipedia sample artifact. The sample artifact passed schema, leakage, length, runner-compatibility, and reproducibility checks. This does not mean the full benchmark dataset is ready; full source-mode data has not been generated or audited.

## Scope

- Added `scripts/audit_dataset.py`.
- Added CPU-only tests in `tests/test_audit_dataset.py`.
- Audited `data/processed/gsm8k_wikipedia_augmented_smoke.jsonl`.
- Generated `results/task42_dataset_audit_summary.json`.
- Updated `docs/Roadmap.html` to mark Task 42 complete and set Task 43 as next.
- Updated `docs/CC-DFlash-Overview.html` to clarify sample-mode readiness versus full benchmark dataset readiness.

No model benchmarks were run. No target, draft, tokenizer, compressor, CUDA, or model weights were loaded.

## Audit Command

```bash
PYTHONPATH=src .venv/bin/python scripts/audit_dataset.py --input data/processed/gsm8k_wikipedia_augmented_smoke.jsonl --output results/task42_dataset_audit_summary.json
```

## Summary Artifact

`results/task42_dataset_audit_summary.json`

Top-level result:

- status: `PASS`
- row count: 5
- source: `gsm8k+wikipedia`
- source mode: `sample`
- issues: 0
- duplicate id count: 0

## Checks Performed

The audit checks:

- JSONL parse validity
- required field presence
- stable row ids
- duplicate ids
- non-empty question/context/prompt
- `expected_answer` and `ground_truth_answer` presence
- question preservation in prompt
- final answer not leaked into context
- final answer not leaked into prompt
- `approximate_context_words` distribution
- `approximate_context_tokens` distribution
- source/source_mode consistency
- augmentation metadata presence
- token length metadata presence
- fixture runner-compatible fields

## Length Distribution

| Metric | Words | Tokens |
| --- | ---: | ---: |
| min | 274.0 | 356.0 |
| max | 274.0 | 356.0 |
| mean | 274.0 | 356.0 |
| median | 274.0 | 356.0 |

Token counts are word-estimate fallback values from Task 41, not tokenizer-backed counts.

## Reproducibility

The audit reran the Task 41 sample builder twice in temporary outputs using the same seed and settings:

- mode: `sample`
- seed: 41
- rows: 5
- row-level equality: true
- byte-level equality: true

## Readiness

| Readiness item | Status |
| --- | --- |
| Builder readiness | PASS |
| Sample artifact readiness | PASS |
| Full benchmark dataset readiness | NOT READY |

Full benchmark dataset readiness is false because `source_mode` is `sample`; full source-mode GSM8K/Wikipedia data has not been generated or audited.

## Interpretation

Task 42 gives us a reliable guardrail for the dataset contract and verifies that the current sample artifact is safe to use for development checks. It does not authorize final benchmark claims. A future full dataset path must generate and audit source-mode rows before any n>=100 benchmark or final claim.

## Limitations

- Audit covers the sample-mode artifact only.
- No external GSM8K or Wikipedia dataset was downloaded for this audit.
- Token counts are estimated, not tokenizer-backed.
- This is not a model benchmark and does not measure correctness or speed.
- No final speedup, final correctness, deploy readiness, confirmed 8 GB deployment, or proven compression benefit is claimed.

## Validation

- `PYTHONPATH=src .venv/bin/python -m pytest tests/test_audit_dataset.py -q`: PASS, 5 passed
- `PYTHONPATH=src .venv/bin/python scripts/audit_dataset.py --input data/processed/gsm8k_wikipedia_augmented_smoke.jsonl --output results/task42_dataset_audit_summary.json`: PASS
- `python3 -m json.tool results/task42_dataset_audit_summary.json`: PASS

## Next Step

Task 43: targeted long-context rerun using the audited sample-mode dataset path, still preliminary and not a final benchmark.
