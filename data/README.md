# Data Layout

## Active benchmark data

`data/eval/` contains the active Phase 1/Phase 2 benchmark datasets:

- `gsm8k_100.jsonl`
- `qmsum_meeting_qa_100.jsonl`

## Source cache

`data/raw/` contains source/cache files required by active dataset fetch/build commands.

- `gsm8k_source.jsonl` is retained only if required by `scripts/fetch_dataset.py`.

## Deprecated data branch

The earlier GSM8K+Wikipedia augmented branch has been deprecated and removed from the active path. Active evaluation now uses GSM8K short-context numeric proxy and QMSum long-context diagnostic benchmark.
