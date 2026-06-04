# Task 41 — GSM8K + Wikipedia Augmented Dataset Builder

Date: 2026-06-04

## Result

PASS, sample-mode.

Task 41 added a reproducible dataset builder for GSM8K + Wikipedia augmented long-context prompts and generated a small dev-safe JSONL artifact. This prepares the dataset path for Task 42 audit and later benchmark planning. It does not run benchmarks and does not support final benchmark claims by itself.

## Scope

- Replaced the placeholder `scripts/create_dataset.py` with a deterministic dataset builder.
- Added CPU-only tests in `tests/test_create_dataset.py`.
- Generated `data/processed/gsm8k_wikipedia_augmented_smoke.jsonl`.
- Updated `docs/Roadmap.html` to mark Task 41 complete and set Task 42 as next.
- Updated `docs/CC-DFlash-Overview.html` to say the builder exists but the dataset remains sample-mode and unaudited.

No final benchmarks were run. No target, draft, tokenizer, compressor, CUDA, or model weights were loaded.

## Builder Command

```bash
PYTHONPATH=src .venv/bin/python scripts/create_dataset.py --output data/processed/gsm8k_wikipedia_augmented_smoke.jsonl --max-samples 5 --min-context-words 220 --max-context-words 360 --seed 41 --split test --source-mode sample
```

## Output Artifact

`data/processed/gsm8k_wikipedia_augmented_smoke.jsonl`

Smoke output:

- rows: 5
- source: `gsm8k+wikipedia`
- source mode: `sample`
- split: `test`
- seed: 41
- context words: `[274, 274, 274, 274, 274]`

No external GSM8K or Wikipedia dataset download was performed in this task. The builder supports a future `--source-mode hf` path for GSM8K loading and a `--wikipedia-jsonl` path for local/cache Wikipedia text, but Task 41 validation used deterministic bundled sample rows.

## Row Schema

Each row includes:

| Field | Purpose |
| --- | --- |
| `id` | Stable row id |
| `source` | `gsm8k+wikipedia` |
| `source_mode` | `sample` or future `hf` |
| `domain` | Dataset domain for runner metadata |
| `question` | GSM8K-style question, preserved unchanged |
| `answer` | Final answer for evaluation |
| `ground_truth_answer` | Same final answer, explicit evaluation field |
| `expected_answer` | Runner-compatible expected answer field |
| `context` | Wikipedia-derived distractor context |
| `prompt` | Reconstructable model-visible prompt |
| `evidence` | Non-answer-leaking provenance note |
| `noise_type` | Augmentation noise label |
| `approximate_context_words` | Word-count length metadata |
| `approximate_context_tokens` | Token estimate when tokenizer is not used |
| `token_length_metadata` | Token counting method and length fields |
| `original_dataset_reference` | GSM8K dataset/config/split/source metadata |
| `augmentation_metadata` | Wikipedia distractor metadata and leakage guard status |

## Leakage Policy

The builder keeps the ground truth answer out of model-visible text:

- Wikipedia distractor text is rejected when it contains the normalized final answer.
- The generated context is checked for final-answer leakage.
- The generated prompt is checked for final-answer leakage.
- The GSM8K question is preserved unchanged.
- The final answer is stored only in evaluation fields, not in `context` or `prompt`.

Task 41 smoke validation confirmed:

- `required_fields_ok`: true
- `question_preserved`: true
- `answer_in_prompt`: false for all rows
- `answer_in_context`: false for all rows

## Runner Compatibility

The artifact is compatible with the existing fixture runner shape because every row includes:

- `id`
- `domain`
- `context`
- `question`
- `expected_answer`
- `evidence`
- `approximate_context_words`

The runner can reconstruct prompts as `context + question` through the existing `--prompt-source fixture` path.

## Tests

Added `tests/test_create_dataset.py` to validate:

- JSONL schema
- deterministic output with fixed seed
- answer and question preservation
- leakage guard behavior
- compatibility with `scripts/run_mvp.py` fixture selection

## Limitations

- Task 41 generated a sample-mode artifact, not a full downloaded GSM8K + Wikipedia dataset.
- Wikipedia passages are bundled dev-safe sample snippets for smoke validation.
- Token lengths use a word-based estimate unless a tokenizer is explicitly supplied.
- Dataset audit is still required before benchmark use.
- No final speedup, correctness, deploy readiness, confirmed 8 GB deployment, or proven compression benefit is claimed.

## Validation

- `PYTHONPATH=src .venv/bin/python -m pytest tests/test_create_dataset.py -q`: PASS, 5 passed
- `PYTHONPATH=src .venv/bin/python scripts/create_dataset.py --output data/processed/gsm8k_wikipedia_augmented_smoke.jsonl --max-samples 5 --min-context-words 220 --max-context-words 360 --seed 41 --split test --source-mode sample`: PASS
- Artifact validation: PASS, 5 rows with required fields and no model-visible final-answer leakage

## Next Step

Task 42: audit the generated dataset for schema, leakage, answer preservation, token length distribution, reproducibility, and benchmark readiness.
