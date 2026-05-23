# HTFS-Decoding: Hierarchical Token-Feature Speculative Decoding

<div align="center">

**MVP Phase 0-2 for vLLM-native speculative decoding research with Qwen D-Flash drafts and Gemma E2B greedy verification.**

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)
![vLLM](https://img.shields.io/badge/vLLM-0.5.0+-4B5563?style=flat-square)
![Version](https://img.shields.io/badge/version-0.1.0-blue?style=flat-square)
![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)
![Status](https://img.shields.io/badge/status-MVP%20Phase%200--2-orange?style=flat-square)

</div>

---

## Table of Contents

- [HTFS-Decoding: Hierarchical Token-Feature Speculative Decoding](#htfs-decoding-hierarchical-token-feature-speculative-decoding)
  - [Table of Contents](#table-of-contents)
  - [About](#about)
  - [Current Scope](#current-scope)
  - [Architecture](#architecture)
  - [Features](#features)
  - [Repository Layout](#repository-layout)
  - [Installation](#installation)
  - [Model Preparation](#model-preparation)
    - [Option A: Let vLLM Use Hugging Face IDs](#option-a-let-vllm-use-hugging-face-ids)
    - [Option B: Pre-Download Models To Local Paths](#option-b-pre-download-models-to-local-paths)
  - [Configuration](#configuration)
  - [Usage](#usage)
  - [Run Logs](#run-logs)
  - [Benchmarking](#benchmarking)
  - [Testing and Quality Gates](#testing-and-quality-gates)
  - [Research Guardrails](#research-guardrails)
  - [Documentation for Agents](#documentation-for-agents)
  - [Contributing](#contributing)
  - [License](#license)
  - [Contact](#contact)

## About

HTFSD, **Hierarchical Token-Feature Speculative Decoding**, is a research project
for exploring speculative decoding across a hierarchical model stack:

```text
Qwen3-0.6B -> Gemma E2B -> Gemma E4B
```

The long-term research direction is:

- **Low Tier**: Qwen3-0.6B proposes candidate continuations as structured text
  through D-Flash.
- **Mid Tier**: Gemma E2B verifies Low Tier candidates in Gemma token space.
- **High Tier**: Gemma E2B hidden states may later feed an EAGLE-style
  speculator for Gemma E4B.

The current codebase intentionally implements only **MVP Phase 0-2**. High Tier,
EAGLE, and hidden-state promotion are future research work and are not part of
the current MVP.

## Current Scope

Implemented:

- Phase 0: YAML config and Gemma E4B autoregressive baseline benchmark runner.
- Phase 1: strict D-Flash parser, D-Flash prompt template, and Qwen drafter
  adapter.
- Phase 2: Low Tier engine, Gemma E2B greedy verifier adapter, interactive
  generate CLI, and Low Tier batch benchmark CLI.
- Fake-adapter unit tests for core correctness without requiring GPU downloads.
- Optional vLLM/GPU integration boundary.
- Pyright and Pylint quality gates.

Not implemented:

- High Tier.
- EAGLE or EAGLE-2 draft head.
- Hidden-state promotion.
- Gemma E4B verification inside the Low Tier loop.
- Lossless or speedup claims against Gemma E4B.

## Architecture

The implemented Low Tier greedy path is:

```text
user prompt
  -> Qwen D-Flash draft
  -> strict D-Flash JSON parse
  -> Gemma tokenizer retokenization
  -> Gemma E2B greedy exact-match verification
  -> accepted prefix append
  -> one-token Gemma E2B greedy fallback on reject or malformed draft
  -> final text
```

Important behavior:

- Full candidate match appends the accepted prefix and does not fallback.
- Immediate reject appends one Gemma E2B greedy fallback token.
- Partial reject appends the accepted prefix, then one Gemma E2B greedy fallback
  token at the rejection position.
- Malformed D-Flash does not fail generation; the engine falls back by one Gemma
  E2B greedy token and continues.
- EOS inside accepted tokens stops generation when `stop_on_eos=true`.
- Greedy Low Tier output is **Gemma E2B greedy-equivalent**, not Gemma
  E4B-equivalent.

## Features

- Strict D-Flash parser with no regex repair or semantic rewriting.
- Gemma token-space verification and acceptance metrics.
- Interactive generation mode for arbitrary prompts.
- Batch Low Tier benchmark mode with JSONL output.
- Separate Gemma E4B autoregressive baseline benchmark.
- Configurable runtime execution mode:
  - `concurrent` by default for realistic serving-style measurement.
  - `sequential` for debug or VRAM-constrained local runs only.
- Sampling mode is available only as experimental interactive mode, not for
  correctness or benchmark claims.
- Source layout is flattened under `src/`, without a `src/htfsd` package.

## Repository Layout

```text
.
├── .agents/
│   ├── agent/
│   │   └── CODEX.md
│   └── docs/
│       ├── instruction.md
│       └── superpowers/
├── benchmarks/
│   └── fixtures/
│       └── prompts.jsonl
├── configs/
│   └── local.example.yaml
├── src/
│   ├── config.py
│   ├── htfsd_types.py
│   ├── benchmarks/
│   ├── cli/
│   ├── dflash/
│   ├── low_tier/
│   ├── metrics/
│   ├── runtime/
│   └── tokenization/
├── tests/
├── pyproject.toml
├── pyrightconfig.json
└── README.md
```

Layout rules for contributors and agents:

- Do not recreate `src/htfsd`.
- Do not create `src/types.py`; use `src/htfsd_types.py`.
- Keep CLI wrappers thin. Core logic belongs in the Python API modules.
- Keep generated run outputs under `runs/` and do not commit them by default.

## Installation

Create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

Install the package for local development:

```bash
pip install -e ".[dev]"
```

Editable installs remember the source checkout path. If this repo is moved,
renamed, copied into another machine, or used from a different Python
environment, rerun the install command from the active checkout before using
the `htfsd-*` CLI entry points. A stale editable install can leave the CLI
script installed while imports such as `cli.generate` still point at the old
checkout. If a moved `.venv` launcher reports a `bad interpreter` path, recreate
the virtual environment in its new location.

For benchmark dataset experiments:

```bash
pip install -e ".[dev,benchmark]"
```

The runtime dependency list includes `vllm`. Unit tests are designed so the
optional vLLM/GPU path does not need to run during normal CPU-only validation.

## Model Preparation

Runtime commands need three model entries:

| Config key                                   | Role                                    | Example value       |
| -------------------------------------------- | --------------------------------------- | ------------------- |
| `models.qwen_drafter.model_id_or_path`       | Low Tier D-Flash drafter                | `Qwen/Qwen3-0.6B`   |
| `models.gemma_e2b.model_id_or_path`          | Low Tier greedy verifier/fallback model | `/models/gemma-e2b` |
| `models.gemma_e4b_baseline.model_id_or_path` | Separate autoregressive baseline        | `/models/gemma-e4b` |

`model_id_or_path` can be either:

- a Hugging Face model ID that vLLM can download/cache at runtime; or
- a local directory containing the downloaded model files.

### Option A: Let vLLM Use Hugging Face IDs

Use this when the machine has network access and the model license/access is
already configured:

```yaml
models:
  qwen_drafter:
    model_id_or_path: "Qwen/Qwen3-0.6B"

  gemma_e2b:
    model_id_or_path: "<gemma-e2b-huggingface-repo>"

  gemma_e4b_baseline:
    model_id_or_path: "<gemma-e4b-huggingface-repo>"
```

For gated models, authenticate with Hugging Face before running vLLM:

```bash
pip install "huggingface_hub[cli]"
hf auth login
```

Or provide a token through the environment:

```bash
export HF_TOKEN="<your-hugging-face-token>"
```

### Option B: Pre-Download Models To Local Paths

Use this when you want reproducible local paths or the runtime machine should
not download models during benchmark runs:

```bash
mkdir -p ./models

hf download Qwen/Qwen3-0.6B \
  --local-dir ./models/qwen3-0.6b

hf download google/gemma-4-E2B-it \
  --local-dir ./models/gemma-4-e2b-it

hf download google/gemma-4-E4B-it \
  --local-dir ./models/gemma-4-e4b-it
```

The current `hf download` command does not accept
`--local-dir-use-symlinks`. If you are using a token without interactive login,
add `--token "$HF_TOKEN"` to each `hf download` command.

Then point `configs/local.yaml` at those directories:

```yaml
models:
  qwen_drafter:
    model_id_or_path: "/models/qwen3-0.6b"

  gemma_e2b:
    model_id_or_path: "/models/gemma-e2b"

  gemma_e4b_baseline:
    model_id_or_path: "/models/gemma-e4b"
```

Notes:

- Replace the Gemma placeholders with the exact repositories or local model
  directories available in your environment.
- Keep E2B and E4B paths separate. A Gemma E4B repository should not be
  downloaded into the `gemma_e2b` path.
- The Gemma E4B model is only for the separate baseline command. It must not be
  routed into the Low Tier interactive generation loop.
- GPU/vLLM integration runs may require substantial VRAM. If concurrent Qwen +
  Gemma E2B loading does not fit, use `runtime.execution_mode: "sequential"`
  only as a debug/non-comparable mode.

## Configuration

Start from the example config:

```bash
cp configs/local.example.yaml configs/local.yaml
```

Then update model paths for your environment:

```yaml
models:
  qwen_drafter:
    model_id_or_path: "Qwen/Qwen3-0.6B"

  gemma_e2b:
    model_id_or_path: "/models/gemma-e2b"

  gemma_e4b_baseline:
    model_id_or_path: "/models/gemma-e4b"
```

Default runtime choices:

- `runtime.execution_mode: "concurrent"`
- `generation.stop_on_eos: true`
- `decoding.default: "greedy"`
- `low_tier.acceptance_policy: "greedy_exact_match"`
- `low_tier.fallback_policy: "single_token_greedy"`

`sequential` execution mode is debug/non-comparable and should not be used for
primary latency or speedup claims.

## Usage

`htfsd-generate` uses `configs/local.yaml` by default; pass
`--config <path>` only when running a different config file.

Run one prompt through the Low Tier path:

```bash
htfsd-generate --prompt "Liệt kê các tỉnh Việt Nam"
```

Run interactive prompt mode:

```bash
htfsd-generate
```

Inside the prompt loop:

```text
htfsd> Liệt kê các tỉnh Việt Nam
htfsd> quit
```

Write a per-cycle debug trace:

```bash
htfsd-generate \
  --config configs/local.yaml \
  --prompt "Explain speculative decoding briefly." \
  --debug-trace runs/trace.jsonl
```

Sampling is experimental and only for interactive exploration:

```bash
htfsd-generate \
  --config configs/local.yaml \
  --prompt "Write a short story opening." \
  --decoding sampling \
  --temperature 0.7
```

Do not use sampling for correctness metrics or benchmark speedup claims.

For development checkouts without an editable install, use the file-backed
module invocation:

```bash
PYTHONPATH=src python -m cli.generate --prompt "Hello"
```

## Run Logs

Each HTFSD CLI invocation writes a structured JSON run log under
`logs/runs/*.json`. Run logs store command metadata, timing, artifact pointers,
runtime and config metadata when available, and traceback or error details on
CLI failure.

Raw `--prompt` text and generated model output are not stored by default.
Benchmark JSONL and `--debug-trace` JSONL stay separate artifacts; the run log
points to their paths.

## Benchmarking

Run the Low Tier greedy benchmark:

```bash
htfsd-benchmark-low \
  --config configs/local.yaml \
  --fixtures benchmarks/fixtures/prompts.jsonl \
  --output runs/low_tier.jsonl
```

Run the Gemma E4B autoregressive baseline benchmark:

```bash
htfsd-baseline-e4b \
  --config configs/local.yaml \
  --fixtures benchmarks/fixtures/prompts.jsonl \
  --output runs/e4b_baseline.jsonl
```

Benchmark outputs are JSONL artifacts. They should normally stay under `runs/`
and remain uncommitted.

Low Tier benchmark validity depends on the vLLM verification adapter matching a
Gemma E2B greedy autoregressive reference. If the verification adapter does not
pass equivalence checks, acceptance-rate and speedup metrics must be treated as
invalid.

## Testing and Quality Gates

Run CPU/local tests without GPU or vLLM integration tests:

```bash
PYTHONPATH=src pytest -m "not gpu and not vllm" -v
```

Run Pyright:

```bash
pyright
```

Run Pylint:

```bash
pylint src
```

Expected gate before merging code changes:

```bash
PYTHONPATH=src pytest -m "not gpu and not vllm" -v
pyright
pylint src
```

If tools are installed only in the local virtual environment, use:

```bash
PYTHONPATH=src .venv/bin/python -m pytest -m "not gpu and not vllm" -v
.venv/bin/python -m pyright
.venv/bin/python -m pylint src
```

## Research Guardrails

Current MVP claims:

- Low Tier greedy output is Gemma E2B greedy-equivalent.
- Gemma E4B is a separate autoregressive baseline benchmark.
- Acceptance rate is measured over Gemma candidate tokens after retokenization
  and max-token capping.

Current MVP must not claim:

- Lossless equivalence against Gemma E4B.
- Speedup against Gemma E4B from the Low Tier loop alone.
- Sampling-based correctness.
- High Tier behavior.
- EAGLE/EAGLE-2 behavior.
- Hidden-state promotion.

Future research may add High Tier, but it must be designed and tested as a
separate phase.

## Documentation for Agents

Agent-facing handoff and design docs live in `.agents/`:

```text
.agents/agent/CODEX.md
.agents/docs/instruction.md
.agents/docs/superpowers/specs/
.agents/docs/superpowers/plans/
```

Recommended reading order for agents:

1. `.agents/agent/CODEX.md`
2. `.agents/docs/superpowers/specs/2026-05-15-htfsd-phase-0-2-mvp-design.md`
3. `.agents/docs/superpowers/plans/2026-05-15-htfsd-phase-0-2-mvp-implementation-plan.md`
4. `.agents/docs/instruction.md`

Treat `.agents/docs/instruction.md` as the broader research overview. For
current implementation work, follow the Phase 0-2 MVP spec and the guardrails
in `.agents/agent/CODEX.md`.

## Contributing

Before opening or merging changes:

- Keep Python API/core logic separate from CLI wrappers.
- Preserve Low Tier greedy semantics.
- Keep optional vLLM imports from becoming hard requirements for unit tests.
- Add or update fake-adapter tests before changing engine behavior.
- Run the full local gate:

```bash
PYTHONPATH=src pytest -m "not gpu and not vllm" -v
pyright
pylint src
```

## License

This project is licensed under the [MIT License](LICENSE).

## Contact

Maintainer: Onsra

Project repository: `Hybrid-Token-Feature-Speculative-Decoding`


