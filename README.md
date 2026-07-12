# CCDF — Context-Compressed Decoding Flash

CCDF is an offline, reproducible runtime for measuring context compression with
cached autoregressive decoding and target-verified DFlash decoding. It records
raw generation artifacts, provenance, resource measurements, and evaluator-only
summaries for GSM8K and QMSum fixtures.

The locked target is Qwen3-4B NF4. QMSum semantic correctness is
**NOT_CLAIMED**; lexical/reference proxy metrics are reported instead. Exact
token equivalence with baseline is observed evidence only, never a claim.

## Conditions

- `baseline-ar` — cached target autoregressive decoding.
- `dflash-r1` — target-verified DFlash with the locked drafter.
- `llmlingua-ar-r2` — CPU LLMLingua context compression plus cached AR.
- `cc-dflash-r2` — CPU LLMLingua compression plus DFlash.
- `llmlingua-ar-r2-gpu` / `cc-dflash-r2-gpu` — Rec-T07 CUDA-compressor variants.

GSM8K short contexts may bypass compression; artifacts identify that bypass.
GPU conditions reject silent CPU compressor fallback.

## Requirements

- Python 3.10–3.12.
- Local copies of the locked target, drafter, LLMLingua model, and fixture data.
- PyTorch, Transformers, bitsandbytes, LLMLingua, and project dependencies in
  the active environment. GPU variants require CUDA.

## Install

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e . --no-deps
python -m ccdf paths
```

Install heavyweight ML dependencies appropriate to the local CUDA environment
before running inference. Paths and locked model identities are resolved from
`configs/reconstruction.yml`; model/data files are deliberately not downloaded
by CCDF.

## Quick start

```bash
. .venv/bin/activate
export PYTHONPATH=src
python -m ccdf run --dataset gsm8k --condition baseline-ar --prompt '2 + 2'
python -m ccdf paths
```

The `run` command also supports `--context-file`, `--question`, `--fixture-id`,
`--profile`, `--save`, and `--format json`.

## Benchmarks and evaluation

Run benchmark workers only through the canonical matrix for the selected task:

```bash
python -m ccdf benchmark --dataset gsm8k --subset n100 \
  --conditions baseline-ar,dflash-r1,llmlingua-ar-r2,cc-dflash-r2 \
  --output results/Rec-T06D/gsm8k_n100 --task-id Rec-T06D --evaluate

python -m ccdf benchmark --dataset qmsum --subset n100 \
  --conditions llmlingua-ar-r2-gpu,cc-dflash-r2-gpu \
  --output results/Rec-T07/qmsum_n100 --task-id Rec-T07 --evaluate

python -m ccdf evaluate --run-dir results/Rec-T06D/gsm8k_n100
```

Evaluation recomputes from stored raw outputs and references; it does not load
models or instantiate the runtime.

## Artifacts and reproducibility

Each run directory contains a benchmark manifest, resolved configuration/hash,
one JSONL file and worker manifest per condition, evaluator manifest, summaries,
and failure samples. `evaluation_manifest.json` binds consumed inputs and
produced summary hashes. Use:

```bash
python -m compileall -q src
pytest -q
```

## Project layout

- `src/ccdf/` — runtime, DFlash, compression, evaluator, CLI, and benchmark code.
- `configs/reconstruction.yml` — locked configuration and logical paths.
- `data/` and `models/` — locally provisioned fixtures and checkpoints.
- `results/` — immutable benchmark evidence and reports.
- `tests/` — contracts and regression coverage.

## Limitations, contributing, citation, license

This repository is an experimental reconstruction benchmark, not a claim of
lossless quantization, universal quality preservation, or baseline token
equivalence. Contributions should preserve locked identities and claim
boundaries. See repository metadata for licensing; cite the benchmark artifacts
and their manifests when reporting results.
