# CODEX Agent Instructions: HTFSD

Last updated: 2026-05-18

This file is the handoff guide for agents working on this repository. Read it
before changing code. It summarizes the project goal, current implementation
state, architecture, guardrails, and verification workflow.

## Project Identity

Repository: `Hybrid-Token-Feature-Speculative-Decoding`

Project name: HTFSD, Hierarchical Token-Feature Speculative Decoding.

The research direction is a hierarchical speculative decoding system:

```text
Qwen3-0.6B -> Gemma E2B -> Gemma E4B
```

Long-term research idea:

- Low Tier: Qwen3-0.6B proposes text candidates through D-Flash.
- Mid Tier: Gemma E2B verifies Low Tier candidates in Gemma token space.
- High Tier: Gemma E2B hidden states may later feed EAGLE-style feature
  speculation for Gemma E4B.

Current implemented scope is only MVP Phase 0-2. High Tier is intentionally not
implemented.

## Current Status

Implemented and merged into `main`:

- Phase 0 config and Gemma E4B autoregressive baseline benchmark.
- Phase 1 strict D-Flash parser, D-Flash prompt template, Qwen drafter adapter.
- Phase 2 Low Tier engine, Gemma E2B greedy verifier adapter, interactive
  generate CLI, Low Tier batch benchmark CLI.
- Pyright and Pylint gates.
- Flattened source layout: code lives directly under `src/`, not `src/htfsd/`.
- Source docstrings are now required by Pylint.

Current latest important commits on `main`:

```text
b0c4e09 chore: add source docstrings
09cf651 refactor: flatten source layout
9011cd8 docs: add full flatten src layout implementation plan
a289ac9 docs: add full flatten src layout design
c0763ef chore: finalize pyright check on main
```

The old `src/htfsd/` package must not be recreated. The project distribution
name remains `htfsd`, but live imports are top-level imports from `src`.

## Source Layout

Current source tree:

```text
src/
  config.py
  htfsd_types.py
  benchmarks/
  cli/
  dflash/
  low_tier/
  metrics/
  runtime/
  tokenization/
```

Important layout rules:

- Do not recreate `src/htfsd`.
- Do not create `src/types.py`; it would shadow the Python standard-library
  `types` module when `PYTHONPATH=src` is active.
- Shared dataclasses and result shapes live in `src/htfsd_types.py`.
- Import implementation modules with top-level imports, for example:

```python
from config import load_config
from htfsd_types import GenerateResult
from low_tier.engine import LowTierEngine
from runtime.vllm_adapter import VllmVerificationAdapter
```

Do not use:

```python
from htfsd.config import load_config
from htfsd.types import GenerateResult
```

## Documentation Location

Project documentation lives under:

```text
.agents/docs/
```

Important docs:

```text
.agents/docs/htfsd.md
.agents/docs/superpowers/specs/2026-05-15-htfsd-phase-0-2-mvp-design.md
.agents/docs/superpowers/plans/2026-05-15-htfsd-phase-0-2-mvp-implementation-plan.md
.agents/docs/superpowers/specs/2026-05-17-htfsd-pylance-pylint-cleanup-design.md
.agents/docs/superpowers/plans/2026-05-17-htfsd-pylance-pylint-cleanup-implementation-plan.md
.agents/docs/superpowers/specs/2026-05-17-htfsd-full-flatten-src-layout-design.md
.agents/docs/superpowers/plans/2026-05-17-htfsd-full-flatten-src-layout-implementation-plan.md
```

`htfsd.md` is a research overview and includes long-term High Tier ideas. For
current implementation scope, follow the Phase 0-2 MVP design spec and the
guardrails in this file.

## Core Architecture

### Config

File: `src/config.py`

Responsibilities:

- Load YAML config.
- Map config into dataclasses from `htfsd_types.py`.
- Clamp D-Flash `max_tokens`.
- Reject sampling for benchmark-low.

Example config:

```text
configs/local.example.yaml
```

### Shared Types

File: `src/htfsd_types.py`

Contains:

- `ModelConfig`
- `RuntimeConfig`
- `GenerationConfig`
- `DFlashConfig`
- `LowTierConfig`
- `SamplingConfig`
- `DecodingConfig`
- `BenchmarkConfig`
- `AppConfig`
- `DFlashParseResult`
- `TokenResult`
- `VerificationResult`
- `CycleTrace`
- `GenerationMetrics`
- `GenerateResult`

Keep result shapes centralized here. Do not scatter JSON/result schemas across
CLI and engine code.

### D-Flash

Files:

```text
src/dflash/parser.py
src/dflash/prompts.py
```

D-Flash is a strict JSON side-channel proposal format. The required field is:

```json
{"draft_text": "..."}
```

Optional fields:

- `confidence`: logged only, does not affect acceptance.
- `max_tokens`: caps how many Gemma candidate tokens are verified.

Parser guardrails:

- Strict JSON object only.
- No regex repair.
- No semantic content rewrite.
- Minimal normalization only: strip leading/trailing whitespace and normalize
  CRLF to LF where needed.
- Reject empty `draft_text`.

### Tokenization Boundary

File: `src/tokenization/gemma.py`

Responsibilities:

- Encode prompts with the Gemma tokenizer.
- Retokenize D-Flash `draft_text` into Gemma token IDs.
- Decode final Gemma token IDs.

Acceptance metrics must count Gemma candidate tokens after retokenization and
after max-token capping, not Qwen token counts.

### Low Tier Engine

File: `src/low_tier/engine.py`

The Low Tier greedy loop is:

```text
prompt
-> Qwen D-Flash draft
-> strict D-Flash parse
-> Gemma retokenization
-> Gemma E2B greedy exact-match verification
-> append accepted prefix
-> if reject, append one Gemma E2B greedy fallback token
-> continue until EOS or max_new_tokens
```

Critical semantics:

- Full candidate match: append accepted prefix, no fallback.
- Reject at first token: append one Gemma E2B greedy fallback token.
- Partial reject: append accepted prefix, then append one Gemma E2B greedy
  fallback token at the rejection position.
- Malformed D-Flash must not fail generation. Fallback one Gemma E2B greedy
  token and continue unless EOS or max token limit is reached.
- EOS inside accepted prefix must stop generation when `stop_on_eos=true`.
- If accepted tokens are truncated by `max_new_tokens`, metrics count only
  tokens actually appended.

Low Tier greedy output is Gemma E2B greedy-equivalent, not Gemma E4B-equivalent.

### vLLM Runtime

File: `src/runtime/vllm_adapter.py`

vLLM is optional for CPU/unit-test environments. Do not make vLLM mandatory for
unit tests.

Adapter responsibilities:

- Lazy-load vLLM models through `VllmModelHandle`.
- Generate Qwen D-Flash text through `VllmGenerationAdapter`.
- Verify Gemma E2B greedy prefixes and fallback tokens through
  `VllmVerificationAdapter`.

The verification adapter is the highest-risk runtime integration point.
Acceptance metrics are not trustworthy until the adapter passes an equivalence
test against Gemma E2B autoregressive greedy reference.

### Benchmarks

Files:

```text
src/benchmarks/low_tier.py
src/benchmarks/baseline_e4b.py
src/benchmarks/fixtures.py
src/benchmarks/rows.py
```

Benchmark paths:

1. Low Tier benchmark:

```text
prompt fixtures -> Qwen D-Flash -> Gemma E2B verify/fallback -> metrics JSONL
```

2. Gemma E4B baseline:

```text
prompt fixtures -> Gemma E4B autoregressive generation -> metrics JSONL
```

Gemma E4B baseline is separate. It is not inside the Low Tier loop.

### CLI

Files:

```text
src/cli/generate.py
src/cli/benchmark_low.py
src/cli/baseline_e4b.py
```

Console commands:

```text
htfsd-generate
htfsd-benchmark-low
htfsd-baseline-e4b
```

Entrypoints in `pyproject.toml`:

```toml
htfsd-generate = "cli.generate:main"
htfsd-benchmark-low = "cli.benchmark_low:main"
htfsd-baseline-e4b = "cli.baseline_e4b:main"
```

CLI must remain a thin wrapper over Python API/core logic. Do not move decoding
logic into argparse code.

## Required Verification

Before claiming a change is complete, run:

```bash
PYTHONPATH=src pytest -m "not gpu and not vllm" -v
pyright
pylint src
```

Expected current result:

```text
33 passed, 2 deselected
0 errors, 0 warnings, 0 informations
Your code has been rated at 10.00/10
```

Run stale-reference and scope audit after structural or import changes:

```bash
rg -n "from htfsd|import htfsd|src/htfsd|htfsd\\.types|High Tier|EAGLE|hidden-state promotion" src tests pyproject.toml pyrightconfig.json || true
```

Expected: no output for live code/tooling paths.

Docstring policy:

- Pylint docstring warnings are enabled.
- Public modules, public classes, and public functions in `src` need concise
  docstrings.
- Keep docstrings factual and short. Do not add narrative filler.

## Current Pylint/Pyright Setup

`pyrightconfig.json` checks:

```json
{
  "include": ["src", "tests"]
}
```

Pylint gate:

```bash
pylint src
```

The Pylint docstring disables have been removed:

```toml
[tool.pylint.messages_control]
disable = []
```

## Scope Guardrails

Do not implement in MVP without a new approved spec and plan:

- High Tier.
- EAGLE head.
- Hidden-state promotion.
- Gemma E4B verification inside the HTFSD loop.
- Lossless or speedup claims against Gemma E4B.
- Sampling-based correctness metrics or speedup claims.

Allowed in current MVP:

- Interactive greedy generate path.
- Experimental interactive sampling mode, not used for correctness metrics.
- Batch Low Tier benchmark in greedy mode.
- Separate Gemma E4B autoregressive baseline benchmark.
- Fake-adapter unit tests for engine and boundaries.
- Optional/marked vLLM/GPU integration tests.

Sequential execution mode is debug/non-comparable only. Do not use it for main
latency or speedup claims.

## Development Workflow

Use an isolated worktree for feature work. Do not start implementation directly
on `main` unless the user explicitly asks.

Preferred sequence:

1. Understand current branch and status:

```bash
git status --short --untracked-files=all
git branch --show-current
```

2. Read relevant specs/plans under `.agents/docs/superpowers/`.
3. Make narrowly scoped changes.
4. Run required verification.
5. Run stale-reference/scope audit if imports/layout changed.
6. Review `git diff`.
7. Commit focused changes.

Never revert user changes you did not make. There may be untracked files such as
research notes; inspect before deleting.

## Copy/Windows Handoff Notes

This repository may be copied to Windows drive `E:\` through WSL path:

```text
/mnt/e/
```

When copying for handoff, preserve:

- `.agents/agent/CODEX.md`
- `.agents/docs/`
- `src/`
- `tests/`
- `configs/`
- `benchmarks/`
- `pyproject.toml`
- `pyrightconfig.json`
- `README.md`

Do not rely on ignored generated files such as `__pycache__`, `.pytest_cache`,
or virtual environments. A fresh agent should recreate its environment and run
the verification commands above.
