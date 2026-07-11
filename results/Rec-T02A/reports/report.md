# Rec-T02A - Dataset Pipeline Reconstruction

Status: PASS

## Scope

Rec-T02A rebuilt the dataset pipeline outside `.archives/` for GSM8K and QMSum. The pipeline reads the Rec-T01A archive as a locked historical raw-source reference, writes build output to staging first, and only freezes canonical eval files through an explicit `--confirm-freeze` command.

No archived files or historical result directories were modified. `docs/ROADMAP.html` was not updated. Notebooks were not used as canonical implementation or evidence.

## Implementation

- Added `src/ccdf/datasets/` with source locks, stable fixture identity, manifests, validation, build, audit, and freeze commands.
- Added `python -m ccdf.datasets build`, `freeze`, and `audit-reproducibility`.
- Added Rec-T02A tests in `tests/test_rec_t02a_datasets.py`.
- Restored a minimal `pyproject.toml` for the reconstructed `src/` layout.

## Source Lock

Source lock artifact: `results/Rec-T02A/source_lock.json`

The source lock records:

- GSM8K identity: `openai/gsm8k:test`
- QMSum identity: `psunlpgroup/QMSum:test`
- Resolved historical archive source commit: `d638c3496131ba6bae0f2c6e89676e37fee7155a`
- Raw SHA-256 for both source JSONL files
- Deterministic fetch timestamp: `2026-07-11T04:38:59Z`
- Builder version: `rec-t02a.builder.v1`

Caveat: raw sources are locked to the Rec-T01A archive copy and archive source commit rather than dynamically refetched from upstream. This avoids dynamic branch drift and preserves byte-level reproducibility for reconstruction.

## Frozen Datasets

Frozen subset artifact: `results/Rec-T02A/frozen_subset_manifest.json`

| Dataset | Processed fixtures | n10 SHA-256 | n30 SHA-256 | n100 SHA-256 |
| --- | ---: | --- | --- | --- |
| GSM8K | 1319 | `45d50bac9cd425b509bdcda119c5b7ce295e1acac655ffec1eb0ca3ab21240b7` | `87da9c01a428d1e41a52a75e9ca473a3cab46cdb43a0a878b7d8396a66ba6dba` | `c0684d66bd4842ad6cdbdf1689a0cd5ac8e971b5ed08fcf1325107492bf94c25` |
| QMSum | 244 | `429a8aac613a9def9e81761d510df68a2c38d6e8fb097b8ffb1b2cfb11160152` | `781b89748b66433997937d0a3d6fcdaf194a7a327198b80b27cfdf812a8bfa74` | `5a2ae726b885c299e60d4814ec0aff14cfda864f3bf253cda8609b19d596b451` |

Canonical files were frozen under:

- `data/eval/gsm8k/gsm8k_n10.jsonl`
- `data/eval/gsm8k/gsm8k_n30.jsonl`
- `data/eval/gsm8k/gsm8k_n100.jsonl`
- `data/eval/qmsum/qmsum_n10.jsonl`
- `data/eval/qmsum/qmsum_n30.jsonl`
- `data/eval/qmsum/qmsum_n100.jsonl`

Stage manifests were retained under `data/manifests/`.

## QMSum Policy

QMSum query policy is explicit: `specific_only`.

Transcript structure is retained as speaker/content turns in each fixture. Rendered prompt context is derived from those turns with newline-separated speaker lines. Truncation is explicit and audited in `results/Rec-T02A/truncation_audit.csv`.

All 244 QMSum fixtures were prefix-truncated at utterance boundaries with the caveat: reference evidence may fall outside retained context. QMSum semantic correctness is not claimed; fixtures carry `semantic_correctness=NOT_CLAIMED`.

## Reproducibility

Audit artifact: `results/Rec-T02A/reproducibility_audit.json`

The audit built two independent staging folders and compared:

- `source_lock.json`
- `dataset_schema.json`
- `dataset_lineage.json`
- `frozen_subset_manifest.json`
- `fixture_inventory.csv`
- `truncation_audit.csv`

Result: PASS. Compared artifacts were byte-identical.

## Checks

Commands:

```bash
PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_rec_t02a_datasets.py
PYTHONPATH=src .venv/bin/python -m ccdf.datasets build --source-root .archives/20260711-043859/project --staging results/Rec-T02A/staging
PYTHONPATH=src .venv/bin/python -m ccdf.datasets audit-reproducibility --source-root .archives/20260711-043859/project --audit-root results/Rec-T02A/repro_audit --output results/Rec-T02A/reproducibility_audit.json
PYTHONPATH=src .venv/bin/python -m ccdf.datasets freeze --staging results/Rec-T02A/staging --project-root . --dataset all --confirm-freeze
PYTHONPATH=src .venv/bin/python -m pytest -q
```

Results:

- Focused Rec-T02A tests: `10 passed`
- Full available test suite: `10 passed`
- Build: `{"gsm8k": 1319, "qmsum": 244}`
- Reproducibility: `{"pass": true}`
- Freeze: `{"copied": 16}`

## Gate Decision

PASS.

Gate evidence:

- GSM8K and QMSum both have source lock entries.
- Stable IDs include source identity components plus content hash prefixes.
- Content changes alter fixture IDs.
- n10, n30, and n100 subsets are nested prefixes.
- Reproducibility audit passed.
- Canonical eval hashes are recorded in `frozen_subset_manifest.json`.
- Freeze requires `--confirm-freeze` and refuses overwrite by default.
- QMSum query/truncation policy is explicit and audited.
- Remaining caveat is limited to QMSum truncation evidence coverage; semantic correctness is not claimed.
