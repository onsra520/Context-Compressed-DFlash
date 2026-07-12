# CCDF — Context-Compressed Decoding Flash

CCDF is an offline, artifact-first research runtime for measuring context compression with a locked local Qwen3 target. It compares cached autoregressive decoding with target-verified DFlash decoding, with optional LLMLingua2 context compression. It is designed to make timing, output health, token reduction, resource peaks, evaluator inputs, and source provenance inspectable after a run.

## Architecture

`ccdf` resolves a locked condition from `configs/reconstruction.yml`, loads local models, renders a structured prompt, optionally compresses only its context, generates with Baseline-AR or DFlash, and writes immutable JSONL plus manifests. Benchmark conditions run one per process, so model cleanup and resource accounting are isolated per condition.

- Baseline-AR: quantized target cached autoregressive decoding.
- DFlash: target-verified block decoding with a locked drafter.
- LLMLingua-AR: LLMLingua2 context compression followed by Baseline-AR.
- CC-DFlash: LLMLingua2 context compression followed by DFlash.
- `*-gpu` variants request a CUDA-resident compressor. Every discovered compressor parameter and buffer must be CUDA; mixed or CPU placement is rejected.

GSM8K short contexts may bypass compression. In that case the compressor is not loaded and the result records this fact.

## Verified Rec-T06D / Rec-T07 results

The preserved n=100 QMSum evidence shows GPU compression reducing mean LLMLingua compression time from 2858.357 ms to 154.037 ms (18.56x) and CC-DFlash compression from 2810.884 ms to 164.710 ms (17.07x). The long-context GPU rows retain 52.066% mean full-prompt reduction and the recorded CPU-row reference proxy metrics. GPU compression increases process VRAM; see [the combined analysis](results/Rec-T07/combined_report.md) and [comparison table](results/Rec-T07/combined_summary.csv).

These are benchmark observations, not universal performance guarantees. QMSum semantic correctness is **NOT_CLAIMED**; its evaluator reports lexical/reference proxy metrics only. Exact cached-AR token equivalence and lossless quantization are not claimed.

## Requirements

- Linux with Python 3.10–3.12.
- A local checkout, local fixture data, and local locked target/drafter/compressor directories referenced by `configs/reconstruction.yml`.
- PyTorch, Transformers, bitsandbytes, LLMLingua, and their compatible CUDA stack for model execution. The project package itself declares only its lightweight dependency; ML dependencies are environment-specific.
- For GPU compressor variants: a visible CUDA device and a locally cached tiktoken `cl100k_base` encoding. CCDF does not download models or tokenizer assets at runtime.

## Fresh-clone installation

Clone the repository, provision the local model/data directories required by `configs/reconstruction.yml`, then create an environment and install the package. Install the ML stack appropriate to the target CUDA environment before using inference.

```bash
git clone <repository-url> CCDF
cd CCDF
python -m venv .venv
. .venv/bin/activate
python -m pip install -e .
python -m ccdf --help
python -m ccdf paths
```

`python -m ccdf paths` reports the resolved logical/worktree path metadata. It is a safe first check that does not load a model.

## Configuration and model/dataset setup

`configs/reconstruction.yml` is the source of truth for conditions, fixed model identities, local paths, prompt policies, fixtures, and execution settings. Do not edit raw result manifests to redirect paths. Place local assets at the configured locations (or update the configuration deliberately and rerun a noncanonical validation); CCDF does not fetch them.

The required condition names are `baseline-ar`, `dflash-r1`, `llmlingua-ar-r2`, `cc-dflash-r2`, `llmlingua-ar-r2-gpu`, and `cc-dflash-r2-gpu`. GPU variants are valid only when CUDA placement verification succeeds.

## Quick start and single-prompt demo

After activation, use the module entry point (or the equivalent installed `ccdf` script). Set `PYTHONPATH=src` only when running directly from an uninstalled checkout.

```bash
. .venv/bin/activate
python -m ccdf paths
python -m ccdf run --condition baseline-ar --prompt 'What is 2 + 2?'
python -m ccdf run --condition baseline-ar --prompt 'What is 2 + 2?' --format json
```

The last two commands load the local target model. A context/question demo uses the QMSum prompt shape:

```bash
python -m ccdf run --condition llmlingua-ar-r2 \
  --context-file meeting.txt --question 'What decision was made?'
```

## CLI reference

```text
python -m ccdf run --condition CONDITION (--prompt TEXT | --context-file FILE --question TEXT | --dataset DATASET --fixture-id ID)
                    [--profile] [--save] [--format text|json]
python -m ccdf benchmark --dataset gsm8k|qmsum --subset n10|n30|n100
                          --conditions CONDITION[,CONDITION...] --output DIRECTORY
                          [--limit N] [--evaluate] [--task-id ID]
                          [--execution-mode benchmark|profiling|smoke]
python -m ccdf evaluate --run-dir DIRECTORY
python -m ccdf paths
```

`run --profile` selects profiling measurement mode. `run --save` writes the CLI artifact under the configured results root. `benchmark --evaluate` evaluates the newly created run directory; `evaluate` recomputes summaries from stored raw outputs and references without loading inference models. A limited run or a dirty source tree is noncanonical by design.

## Benchmark and evaluation examples

The following commands are valid CLI forms, but n=100 is intentionally expensive and should not overwrite preserved evidence directories.

```bash
python -m ccdf benchmark --dataset gsm8k --subset n10 \
  --conditions baseline-ar,dflash-r1 --output /tmp/ccdf-gsm8k-n10 \
  --limit 3 --task-id local-smoke --execution-mode smoke --evaluate
python -m ccdf evaluate --run-dir /tmp/ccdf-gsm8k-n10
```

## Artifact layout

A benchmark output directory contains `benchmark_manifest.json`, `resolved_config.json` and its hash, one condition JSONL plus worker manifest per condition, `evaluation_manifest.json`, `performance_summary.json`, `resource_summary.json`, `compression_summary.json`, quality summaries, failure samples, and CSV summaries. Parent/worker hashes bind source/configuration/fixture order and evaluation inputs.

`results/Rec-T06D` and `results/Rec-T07` are preserved n=100 evidence. The Rec-T07 hotfix audit and combined analysis live beside those artifacts.

## Testing and reproducibility

From an activated development environment:

```bash
python -m compileall -q src
python -m pytest -q
python -m pytest -q tests/test_rec_t07_gpu_hotfix.py
```

The focused hotfix tests cover all-tensor CUDA placement, rejected CPU fallback, bypass composition, GPU allocation-delta fields, and execution metadata. Reproduction must retain the locked model/data identities and record source state through the canonical benchmark workflow.

## Limitations and claim boundaries

- QMSum semantic correctness is **NOT_CLAIMED**.
- GPU compressor performance cannot be inferred from GSM8K bypass rows.
- CUDA peak allocation/reservation are process measurements. Isolated target and drafter byte attribution is explicitly unsupported.
- The runtime will fail rather than silently use a CPU compressor for a requested GPU condition.
- Model/data acquisition and ML dependency installation are operator responsibilities; no runtime download path is documented or supported.

## Project structure

- `src/ccdf/` — runtime, compression, DFlash, benchmark, evaluator, config, and CLI implementation.
- `configs/` — locked reconstruction configuration.
- `data/` and `models/` — locally provisioned fixtures and checkpoints (not fetched by CCDF).
- `results/` — benchmark evidence, reports, and audits.
- `tests/` — contract and regression tests.

## License, citation, and contributing

See the repository license and metadata for the applicable license. When citing results, cite the exact run directories and manifests, including model/data hashes and source provenance. Contributions should preserve the offline contract, canonical provenance checks, and claim boundaries; run the test suite and avoid replacing preserved benchmark evidence without an explicit benchmark task.
