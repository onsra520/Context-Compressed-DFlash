# Task 45-data-fix — Leakage-Safe Source-Mode Dataset Generation

Date: 2026-06-05

## Result

PASS for dataset generation and audit.

Task 45-data-fix keeps the leakage guard enabled and fixes source-mode generation by resampling Wikipedia distractors when the final GSM8K answer appears in a candidate passage, merged context, or model-visible prompt. The full local JSONL-backed GSM8K + SQuAD-derived Wikipedia source-mode dataset was generated and audited successfully.

No final benchmark was run. No target model, draft model, tokenizer, compressor, CUDA path, vLLM, SGLang, Docker, or scale-up path was used.

## Scope

Changed:

- `scripts/create_dataset.py`
- `tests/test_create_dataset.py`

Generated:

- `data/processed/gsm8k_wikipedia_augmented_full.jsonl`
- `results/task45_source_mode_dataset_audit_summary.json`

Updated:

- `docs/Roadmap.html`
- `docs/CC-DFlash-Overview.html`

## Root Cause

The prior Task 45-data blocker was a real leakage-safety failure, not a reason to weaken validation.

Confirmed case:

- GSM8K row: `gsm8k_wiki_test_0002`
- Final answer: `70000`
- Wikipedia passage row: `146`
- Passage title: `Canadian Armed Forces`
- Leaking phrase: `active to at least 70000`

The correct fix is to reject and resample leaking distractors, not to disable or soften leakage validation.

## Implementation

The builder now:

- Detects numeric leakage variants such as `70,000` vs `70000`.
- Rejects individual Wikipedia passages that leak the final answer.
- Retries merged distractor contexts when the answer leaks into context or prompt.
- Skips a GSM8K row after a bounded retry limit if clean distractors cannot be found.
- Continues until `--max-samples` clean rows are produced.
- Fails clearly if it cannot produce the requested clean row count.
- Adds `--max-leakage-resample-attempts`, default `100`.
- Records `leakage_resample_attempts` and `skipped_due_to_leakage` in generated rows.
- Records leakage metadata under `augmentation_metadata`, including:
  - `answer_in_distractor`
  - `answer_in_context`
  - `answer_in_prompt`
  - `answer_leakage_guard`
  - `max_leakage_resample_attempts`
  - `saw_answer_in_rejected_distractor`

The builder also now applies the configured context word ceiling to the full context, including the fixed context prefix.

## Tests Added

Added focused tests for:

- Numeric leakage equivalence between comma and non-comma answer forms.
- Rejection of a Wikipedia passage containing the final answer.
- Resampling to a clean Wikipedia passage.
- Failure with a clear message when a row is unsatisfiable under the retry limit.
- Continued `validate_rows` compatibility.
- Existing deterministic-output behavior.

Focused test command:

```bash
PYTHONPATH=src .venv/bin/python -m pytest tests/test_create_dataset.py -q
```

Result: PASS, `7 passed, 2 warnings`.

## Source-Mode Dataset Generation

Command run:

```bash
PYTHONPATH=src .venv/bin/python scripts/create_dataset.py \
  --output data/processed/gsm8k_wikipedia_augmented_full.jsonl \
  --max-samples 100 \
  --min-context-words 500 \
  --max-context-words 1500 \
  --seed 41 \
  --split test \
  --source-mode hf \
  --gsm8k-jsonl data/raw/gsm8k_source.jsonl \
  --wikipedia-jsonl data/raw/wikipedia_source.jsonl
```

Outcome:

- Output: `data/processed/gsm8k_wikipedia_augmented_full.jsonl`
- Rows: `100`
- `source_mode`: `hf`
- GSM8K source: `data/raw/gsm8k_source.jsonl`
- Wikipedia source: `data/raw/wikipedia_source.jsonl`
- Wikipedia provenance: SQuAD-derived Wikipedia passages
- Context words: min `564`, max `1500`, mean `1021.16`, median `1056`
- Max leakage resample attempts used by any generated row: `2`
- Rows requiring more than one leakage-resample attempt: `1`
- Context leakage count: `0`
- Prompt leakage count: `0`

## Dataset Audit

Command run:

```bash
PYTHONPATH=src .venv/bin/python scripts/audit_dataset.py \
  --input data/processed/gsm8k_wikipedia_augmented_full.jsonl \
  --output results/task45_source_mode_dataset_audit_summary.json
```

Audit summary:

- Status: `PASS`
- Row count: `100`
- Source modes: `["hf"]`
- Sources: `["gsm8k+wikipedia"]`
- Issues: `0`
- Duplicate IDs: `0`
- `builder_ready`: `true`
- `sample_artifact_ready`: `false`
- `full_benchmark_dataset_ready`: `true`
- Context words: min `564`, max `1500`, mean `1021.16`, median `1056`
- Context tokens: min `733`, max `1950`, mean `1327.49`, median `1373`

Note: the audit script's reproducibility subcheck still exercises the sample-mode deterministic builder path. The full source-mode artifact itself was generated deterministically from fixed local JSONL sources and seed `41`.

## Gate Decision

The source-mode dataset blocker is resolved.

Resolved:

- Full source-mode local JSONL-backed GSM8K + SQuAD-derived Wikipedia dataset exists.
- Full source-mode dataset audit passes.
- Leakage-safe distractor resampling is implemented and tested.
- Frozen-schema audit utility from Task 45-prep remains available.

Still not done:

- Task 45 final benchmark has not been run.
- Final benchmark artifacts have not been audited against the frozen Task 44 artifact schema.
- No final speedup, correctness, deployment, 8 GB, or end-to-end compression-benefit claim is supported.

## Understand-Anything Context

Task bootstrap checked `.understand-anything/meta.json` as required by the current agent manual.

No documented repository command or script was found to refresh or rebuild the Understand-Anything graph. The repo documents the bootstrap metadata check and includes `.agent/scripts/open-understand-dashboard.sh`, but that script opens the dashboard rather than updating analysis context. Therefore no Understand-Anything refresh was run.

## Validation

Commands run:

```bash
python3 -m compileall src tests scripts
PYTHONPATH=src .venv/bin/python -m pytest tests/ -x -q
PYTHONPATH=src .venv/bin/python scripts/create_dataset.py --output data/processed/gsm8k_wikipedia_augmented_full.jsonl --max-samples 100 --min-context-words 500 --max-context-words 1500 --seed 41 --split test --source-mode hf --gsm8k-jsonl data/raw/gsm8k_source.jsonl --wikipedia-jsonl data/raw/wikipedia_source.jsonl
PYTHONPATH=src .venv/bin/python scripts/audit_dataset.py --input data/processed/gsm8k_wikipedia_augmented_full.jsonl --output results/task45_source_mode_dataset_audit_summary.json
python3 -m json.tool results/task45_source_mode_dataset_audit_summary.json
wc -l data/processed/gsm8k_wikipedia_augmented_full.jsonl
```

Results:

- Compileall: PASS.
- Pytest suite: PASS, `79 passed, 2 warnings`.
- Source-mode generation: PASS, `100` rows.
- Dataset audit: PASS.
- JSON validation: PASS.
- Row count: PASS, `100`.
- Full source-mode deterministic rerun to `/tmp`: PASS, byte-for-byte match.
- Markdown fence balance for this report: PASS.
- HTML sanity for `docs/Roadmap.html` and `docs/CC-DFlash-Overview.html`: PASS.

## Next Step

Task 45 final benchmark may be planned next under the frozen Task 44 policy, but it must still:

- Use the full source-mode dataset generated here.
- Use `max_new_tokens >= 128`.
- Store generated text.
- Run only the frozen matrix conditions unless a new task changes the spec.
- Audit resulting benchmark artifacts against the frozen schema before any final analysis.
