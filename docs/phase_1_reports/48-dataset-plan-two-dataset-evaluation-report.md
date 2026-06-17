# Task 48 Dataset Plan Two-Dataset Evaluation Report

Date: 2026-06-11

Status: PASS

## Scope

This task safely changes the forward CC-DFlash dataset plan from GSM8K+Wikipedia augmented data to a two-dataset evaluation setup reused from the LLMLingua-2-Preproduction evaluation style:

1. `gsm8k_short`: GSM8K short-context numeric QA for answer extraction / exact-match proxy.
2. `qmsum_meeting_qa_long`: QMSum-style meeting QA long-context data for speed, prefill, and compression-overhead evaluation.

These are evaluation / benchmark datasets only. They are not training datasets and are not an official LLMLingua-2 paper benchmark reproduction.

## Safe Migration Inventory

Before changing dataset files, the current dataset inventory was listed with:

```bash
find data -maxdepth 4 -type f | sort
find tests/fixtures -maxdepth 3 -type f | sort
```

Observed files:

| Path | Migration decision |
|---|---|
| `data/processed/gsm8k_wikipedia_augmented_full.jsonl` | Kept as optional/legacy ablation |
| `data/processed/gsm8k_wikipedia_augmented_smoke.jsonl` | Kept as optional/legacy ablation |
| `data/raw/gsm8k_source.jsonl` | Kept as local GSM8K source |
| `data/raw/wikipedia_source.jsonl` | Kept as legacy augmentation source |
| `tests/fixtures/long_context_smoke.jsonl` | Kept; tests still reference it |

No old dataset files, result artifacts, benchmark outputs, or fixtures were deleted.

## Files Added or Updated

| Path | Purpose |
|---|---|
| `scripts/eval_datasets.py` | Named dataset registry and deterministic random row selection |
| `scripts/fetch_gsm8k_dataset.py` | Builds `gsm8k_short` JSONL from local GSM8K source |
| `scripts/fetch_qmsum_meeting_qa_dataset.py` | Builds `qmsum_meeting_qa_long` JSONL from QMSum-style source |
| `data/eval/gsm8k_100.jsonl` | 100-row GSM8K short-context evaluation JSONL |
| `data/eval/qmsum_meeting_qa_100.jsonl` | 100-row QMSum-style meeting QA long-context evaluation JSONL |
| `scripts/run_mvp.py` | Adds `--prompt-source dataset`, `--dataset`, `--dataset-path`, `--seed`, and `--dry-run-prompts` |
| `tests/test_eval_datasets.py` | CPU-only tests for builders, registry, and runner selection |
| `tests/test_compression.py` | Adds `CC-DFlash-R2/R3` condition alias checks |
| `config.yml` | Sets `benchmark.dataset: gsm8k_short` and records eval dataset paths |
| `instruction.md` | Adds stable dataset evaluation policy |
| `docs/Roadmap.html` | Updates live dataset plan and Task 48 status |
| `docs/CC-DFlash-Overview.html` | Updates stable research dataset policy |

## Dataset Contracts

### GSM8K Short-Context

Path: `data/eval/gsm8k_100.jsonl`

Role: numeric QA quality / answer extraction.

Important fields:

- `dataset_name`: `gsm8k_short`
- `context`: short non-answer context/instruction
- `question`: preserved GSM8K question
- `expected_answer` / `ground_truth_answer`: final numeric answer after the GSM8K `####` marker
- `prompt`: formatted numeric QA prompt
- `quality_policy`: `numeric_extraction_exact_match_proxy`

### QMSum-Style Meeting QA Long-Context

Path: `data/eval/qmsum_meeting_qa_100.jsonl`

Role: long-context speed, prefill, and compression-overhead evaluation.

Important fields:

- `dataset_name`: `qmsum_meeting_qa_long`
- `context`: meeting transcript, capped at 1,500 words for this committed eval file
- `question`: meeting QA query
- `expected_answer` / `ground_truth_answer`: reference answer/summary when available
- `prompt`: meeting transcript + question prompt
- `quality_policy`: `normalized_text_containment_proxy`

QMSum-style quality is a proxy only. It is not exact semantic correctness without manual or LLM-judge evaluation.

## Runner Registry

The runner can now select:

- `--prompt-source dataset --dataset gsm8k_short`
- `--prompt-source dataset --dataset qmsum_meeting_qa_long`

The dataset selection uses deterministic random sampling with `--seed`, so smoke checks can use random rows without hardcoded prompt examples.

The historical `CC-LLM-R2` condition remains supported. A forward-compatible `CC-DFlash-R2` alias now maps to the same R2 keep-rate behavior.

## Dataset Smoke Results

### GSM8K random n=3

Command:

```bash
PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --config config.yml --condition Baseline-AR --prompt-source dataset --dataset gsm8k_short --dataset-path data/eval/gsm8k_100.jsonl --n 3 --seed 42 --dry-run-prompts
```

Result: `DRY-RUN-PASS`

Selected rows:

| prompt_id | dataset_id | domain | expected_answer | context_words |
|---:|---|---|---:|---:|
| 1 | `gsm8k_short_test_0082` | `numeric_qa` | 6 | 13 |
| 2 | `gsm8k_short_test_0015` | `numeric_qa` | 5 | 13 |
| 3 | `gsm8k_short_test_0004` | `numeric_qa` | 12 | 13 |

### QMSum-style meeting QA random n=3

Command:

```bash
PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --config config.yml --condition Baseline-AR --prompt-source dataset --dataset qmsum_meeting_qa_long --dataset-path data/eval/qmsum_meeting_qa_100.jsonl --n 3 --seed 42 --dry-run-prompts
```

Result: `DRY-RUN-PASS`

Selected rows:

| prompt_id | dataset_id | domain | context_words |
|---:|---|---|---:|
| 1 | `qmsum_meeting_qa_test_0082` | `meeting_qa_long_context` | 1500 |
| 2 | `qmsum_meeting_qa_test_0015` | `meeting_qa_long_context` | 1500 |
| 3 | `qmsum_meeting_qa_test_0004` | `meeting_qa_long_context` | 1500 |

## Interpretation Policy

Allowed:

- Use GSM8K short-context for deterministic numeric extraction / exact-match proxy.
- Use QMSum-style meeting QA long-context for speed, prefill, and compression-overhead evaluation.
- Treat GSM8K+Wikipedia augmented data as optional/legacy ablation.
- Compare Baseline-AR, DFlash-R1, LLMLingua-AR-R2, and CC-DFlash-R2 only after new evidence exists.

Forbidden:

- Do not claim final speedup.
- Do not claim final correctness.
- Do not claim compression is proven useful end-to-end.
- Do not claim CC-DFlash is better than DFlash-R1 unless benchmark evidence shows it.
- Do not treat QMSum-style containment as exact semantic correctness.

## Validation

Commands run:

```bash
python3 scripts/fetch_gsm8k_dataset.py --source data/raw/gsm8k_source.jsonl --output data/eval/gsm8k_100.jsonl --max-samples 100 --seed 42 --split test
python3 scripts/fetch_qmsum_meeting_qa_dataset.py --output data/eval/qmsum_meeting_qa_100.jsonl --splits test --max-samples 100 --seed 42 --min-context-words 500 --max-context-words 1500
PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --config config.yml --condition Baseline-AR --prompt-source dataset --dataset gsm8k_short --dataset-path data/eval/gsm8k_100.jsonl --n 3 --seed 42 --dry-run-prompts
PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --config config.yml --condition Baseline-AR --prompt-source dataset --dataset qmsum_meeting_qa_long --dataset-path data/eval/qmsum_meeting_qa_100.jsonl --n 3 --seed 42 --dry-run-prompts
```

Full compile/test validation is recorded in the final agent response.

## Limitations

- QMSum-style data was fetched as an evaluation source, not training data.
- The committed QMSum-style eval file caps context at 1,500 words.
- QMSum-style quality is currently containment / normalized text proxy only.
- No GPU benchmark was run in this task.
- No old Task 45/46/47 benchmark result artifact was modified.

## Next Step

Task 49 should package figures/reports with the updated dataset policy, or schedule a new benchmark run on the two-dataset setup if paper packaging requires fresh evidence rather than reusing prior GSM8K+Wikipedia artifacts.
