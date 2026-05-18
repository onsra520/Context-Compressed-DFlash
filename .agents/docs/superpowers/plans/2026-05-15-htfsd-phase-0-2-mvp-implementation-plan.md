# HTFSD Phase 0-2 MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Phase 0-2 HTFSD MVP: Gemma E4B baseline benchmarking, strict D-Flash drafting, and a vLLM-native Low Tier engine whose greedy path is Gemma E2B greedy-equivalent.

**Architecture:** Python API is the core; CLI commands are thin wrappers. Unit tests use fake adapters first, while vLLM integration tests are optional and marked because they need GPU/model access. Low Tier generation never routes through Gemma E4B and implements only Qwen D-Flash -> Gemma E2B greedy verification/fallback.

**Tech Stack:** Python 3.11+, vLLM, PyYAML, pytest, dataclasses, argparse, JSONL artifacts.

---

## References And Hard Guardrails

Approved design spec:

- `docs/superpowers/specs/2026-05-15-htfsd-phase-0-2-mvp-design.md`

vLLM API references to check while implementing `VllmVerificationAdapter`:

- `SamplingParams` supports `logprobs` and `prompt_logprobs`: https://docs.vllm.ai/en/latest/api/vllm/sampling_params.html
- `TokensPrompt` supports `prompt_token_ids`: https://docs.vllm.ai/en/stable/api/vllm/inputs/data/

Guardrails:

- Do not implement High Tier.
- Do not implement EAGLE.
- Do not implement hidden-state promotion.
- Do not route Low Tier generation through Gemma E4B.
- Do not claim Phase 0-2 speedup or lossless behavior against Gemma E4B.
- Greedy is the default correctness path.
- Sampling is interactive experimental only.
- Sequential execution is debug/non-comparable only.
- Unit tests use fake adapters first.
- vLLM integration tests are optional/marked.

## File Structure

Create this structure:

```text
pyproject.toml
.gitignore
configs/local.example.yaml
benchmarks/fixtures/prompts.jsonl

src/htfsd/__init__.py
src/htfsd/config.py
src/htfsd/types.py

src/htfsd/dflash/__init__.py
src/htfsd/dflash/parser.py
src/htfsd/dflash/prompts.py

src/htfsd/runtime/__init__.py
src/htfsd/runtime/vllm_adapter.py

src/htfsd/tokenization/__init__.py
src/htfsd/tokenization/gemma.py

src/htfsd/low_tier/__init__.py
src/htfsd/low_tier/acceptance.py
src/htfsd/low_tier/drafter.py
src/htfsd/low_tier/engine.py
src/htfsd/low_tier/verifier.py

src/htfsd/metrics/__init__.py
src/htfsd/metrics/counters.py
src/htfsd/metrics/timers.py

src/htfsd/benchmarks/__init__.py
src/htfsd/benchmarks/baseline_e4b.py
src/htfsd/benchmarks/fixtures.py
src/htfsd/benchmarks/low_tier.py

src/htfsd/cli/__init__.py
src/htfsd/cli/baseline_e4b.py
src/htfsd/cli/benchmark_low.py
src/htfsd/cli/generate.py

tests/test_acceptance_policy.py
tests/test_cli.py
tests/test_config.py
tests/test_dflash_parser.py
tests/test_low_tier_engine.py
tests/test_metrics.py
tests/test_tokenization.py
tests/test_vllm_adapter_optional.py
```

Responsibility map:

- `types.py`: all result, metric, token, trace, and config dataclasses.
- `config.py`: YAML loading, validation, config-derived helpers.
- `dflash/parser.py`: strict JSON parser and minimal normalization.
- `dflash/prompts.py`: compact JSON-only prompt template for Qwen.
- `tokenization/gemma.py`: Gemma tokenizer boundary; encode/decode logic stays out of engine/verifier.
- `low_tier/acceptance.py`: pure greedy prefix acceptance helper used by fake tests and adapter validation.
- `low_tier/drafter.py`: Qwen D-Flash drafter interface and vLLM-backed implementation wrapper.
- `low_tier/verifier.py`: Gemma E2B verifier interface.
- `low_tier/engine.py`: owns the Low Tier generate loop.
- `runtime/vllm_adapter.py`: all vLLM-specific generation, token prompts, logprobs, and version metadata handling.
- `metrics/*`: timing and counter aggregation.
- `benchmarks/*`: JSONL fixtures, Low Tier batch benchmark, Gemma E4B baseline benchmark.
- `cli/*`: argparse only; no decoding loop logic.

## Task 1: Package Scaffold, Config Example, Fixtures

**Files:**

- Create: `pyproject.toml`
- Modify: `.gitignore`
- Create: `configs/local.example.yaml`
- Create: `benchmarks/fixtures/prompts.jsonl`
- Create: package `__init__.py` files

- [ ] **Step 1: Write package metadata and console scripts**

Create `pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=69", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "htfsd"
version = "0.1.0"
description = "HTFSD Phase 0-2 MVP: vLLM-native baseline, D-Flash, and Low Tier verification"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
  "pyyaml>=6.0.1",
  "vllm>=0.5.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0"]
benchmark = ["datasets>=2.19"]

[project.scripts]
htfsd-generate = "htfsd.cli.generate:main"
htfsd-benchmark-low = "htfsd.cli.benchmark_low:main"
htfsd-baseline-e4b = "htfsd.cli.baseline_e4b:main"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
markers = [
  "gpu: requires GPU and local model access",
  "vllm: requires vLLM runtime and model access",
]
```

- [ ] **Step 2: Make generated run artifacts ignored**

Append these lines to `.gitignore` if they are not already present:

```gitignore
# HTFSD generated outputs
runs/
*.jsonl.tmp
```

Run:

```bash
tail -20 .gitignore
```

Expected: output includes `runs/`.

- [ ] **Step 3: Add example config**

Create `configs/local.example.yaml`:

```yaml
models:
  qwen_drafter:
    model_id_or_path: "Qwen/Qwen3-0.6B"
    tensor_parallel_size: 1
    dtype: "auto"
    gpu_memory_utilization: 0.35

  gemma_e2b:
    model_id_or_path: "/models/gemma-e2b"
    tensor_parallel_size: 1
    dtype: "auto"
    gpu_memory_utilization: 0.55

  gemma_e4b_baseline:
    model_id_or_path: "/models/gemma-e4b"
    tensor_parallel_size: 1
    dtype: "auto"
    gpu_memory_utilization: 0.90

runtime:
  backend: "vllm"
  execution_mode: "concurrent"
  max_context_tokens: 4096
  seed: 1234

generation:
  max_new_tokens: 128
  stop_on_eos: true

dflash:
  parser: "strict_json"
  required_fields: ["draft_text"]
  default_max_tokens: 8
  hard_max_tokens: 16
  experimental_repair: false

low_tier:
  acceptance_policy: "greedy_exact_match"
  fallback_policy: "single_token_greedy"
  fallback_tokens_per_cycle: 1

decoding:
  default: "greedy"
  sampling:
    enabled: true
    experimental: true
    temperature: 0.7
    top_p: 0.9

benchmark:
  fixture_path: "benchmarks/fixtures/prompts.jsonl"
  dataset:
    enabled: false
    name: null
    split: null
```

- [ ] **Step 4: Add smoke-test fixtures**

Create `benchmarks/fixtures/prompts.jsonl`:

```jsonl
{"id":"vn-provinces","prompt":"Liet ke mot vai tinh thanh cua Viet Nam.","max_new_tokens":64}
{"id":"python-fib","prompt":"Viet ham Python tinh Fibonacci bang vong lap.","max_new_tokens":96}
{"id":"short-summary","prompt":"Tom tat loi ich cua speculative decoding trong ba cau ngan.","max_new_tokens":96}
```

- [ ] **Step 5: Add package init files**

Create these files with the shown content:

```python
# src/htfsd/__init__.py
"""HTFSD Phase 0-2 MVP package."""

__all__ = ["__version__"]
__version__ = "0.1.0"
```

```python
# src/htfsd/dflash/__init__.py
"""D-Flash parsing and prompt templates."""
```

```python
# src/htfsd/runtime/__init__.py
"""Runtime adapters for model backends."""
```

```python
# src/htfsd/tokenization/__init__.py
"""Tokenizer boundaries."""
```

```python
# src/htfsd/low_tier/__init__.py
"""Low Tier Qwen-to-Gemma E2B components."""
```

```python
# src/htfsd/metrics/__init__.py
"""Metric helpers."""
```

```python
# src/htfsd/benchmarks/__init__.py
"""Benchmark runners."""
```

```python
# src/htfsd/cli/__init__.py
"""CLI wrappers for HTFSD."""
```

- [ ] **Step 6: Run scaffold check**

Run:

```bash
python -m compileall src
```

Expected: command exits 0.

- [ ] **Step 7: Commit scaffold**

```bash
git add pyproject.toml .gitignore configs/local.example.yaml benchmarks/fixtures/prompts.jsonl src/htfsd
git commit -m "chore: scaffold HTFSD package"
```

## Task 2: Shared Types And Metric Counters

**Files:**

- Create: `src/htfsd/types.py`
- Create: `src/htfsd/metrics/counters.py`
- Create: `src/htfsd/metrics/timers.py`
- Test: `tests/test_metrics.py`

- [ ] **Step 1: Write failing metric tests**

Create `tests/test_metrics.py`:

```python
from htfsd.metrics.counters import GenerationCounter
from htfsd.types import CycleTrace, GenerationMetrics


def test_generation_counter_acceptance_and_fallback_rates():
    counter = GenerationCounter(execution_mode="concurrent", decoding_mode="greedy")
    counter.add_cycle(drafted_candidate_tokens=4, accepted_tokens=3, fallback_tokens=0, malformed_reason=None)
    counter.add_cycle(drafted_candidate_tokens=2, accepted_tokens=0, fallback_tokens=1, malformed_reason="parse_fail")

    metrics = counter.to_metrics(total_ms=100.0, generated_tokens=4)

    assert metrics.generated_tokens == 4
    assert metrics.cycles == 2
    assert metrics.drafted_candidate_tokens == 6
    assert metrics.accepted_tokens == 3
    assert metrics.fallback_tokens == 1
    assert metrics.malformed_dflash_count == 1
    assert metrics.dflash_parse_fail_count == 1
    assert metrics.low_acceptance_rate == 0.5
    assert metrics.fallback_rate == 0.25
    assert metrics.tokens_per_second == 40.0
    assert metrics.latency_per_token_ms == 25.0
    assert metrics.execution_mode == "concurrent"
    assert metrics.decoding_mode == "greedy"


def test_generation_counter_zero_denominators_are_safe():
    counter = GenerationCounter(execution_mode="sequential", decoding_mode="greedy")
    metrics = counter.to_metrics(total_ms=0.0, generated_tokens=0)

    assert metrics.low_acceptance_rate == 0.0
    assert metrics.fallback_rate == 0.0
    assert metrics.tokens_per_second == 0.0
    assert metrics.latency_per_token_ms == 0.0


def test_cycle_trace_reject_metadata_full_match():
    trace = CycleTrace(
        cycle_index=0,
        context_tokens=5,
        dflash_parse_ok=True,
        malformed_dflash=False,
        draft_text_chars=12,
        draft_candidate_tokens=3,
        accepted_tokens=3,
        reject_position=None,
        candidate_exhausted=True,
        fallback_used=False,
        qwen_draft_ms=1.0,
        dflash_parse_ms=0.1,
        gemma_retokenize_ms=0.1,
        e2b_verify_ms=2.0,
        cycle_ms=3.2,
    )

    assert trace.reject_position is None
    assert trace.candidate_exhausted is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/test_metrics.py -v
```

Expected: FAIL with import errors for `htfsd.metrics.counters` or missing dataclasses.

- [ ] **Step 3: Implement shared dataclasses**

Create `src/htfsd/types.py`:

```python
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class ModelConfig:
    model_id_or_path: str
    tensor_parallel_size: int = 1
    dtype: str = "auto"
    gpu_memory_utilization: float | None = None


@dataclass(frozen=True)
class RuntimeConfig:
    backend: str
    execution_mode: str
    max_context_tokens: int
    seed: int


@dataclass(frozen=True)
class GenerationConfig:
    max_new_tokens: int
    stop_on_eos: bool


@dataclass(frozen=True)
class DFlashConfig:
    parser: str
    required_fields: list[str]
    default_max_tokens: int
    hard_max_tokens: int
    experimental_repair: bool


@dataclass(frozen=True)
class LowTierConfig:
    acceptance_policy: str
    fallback_policy: str
    fallback_tokens_per_cycle: int


@dataclass(frozen=True)
class SamplingConfig:
    enabled: bool
    experimental: bool
    temperature: float
    top_p: float


@dataclass(frozen=True)
class DecodingConfig:
    default: str
    sampling: SamplingConfig


@dataclass(frozen=True)
class BenchmarkDatasetConfig:
    enabled: bool
    name: str | None
    split: str | None


@dataclass(frozen=True)
class BenchmarkConfig:
    fixture_path: str
    dataset: BenchmarkDatasetConfig


@dataclass(frozen=True)
class AppConfig:
    qwen_drafter: ModelConfig
    gemma_e2b: ModelConfig
    gemma_e4b_baseline: ModelConfig
    runtime: RuntimeConfig
    generation: GenerationConfig
    dflash: DFlashConfig
    low_tier: LowTierConfig
    decoding: DecodingConfig
    benchmark: BenchmarkConfig


@dataclass(frozen=True)
class DraftResult:
    raw_text: str
    draft_text: str | None
    confidence: float | None
    max_tokens: int | None
    parse_ok: bool
    error_reason: str | None = None


@dataclass(frozen=True)
class DFlashParseResult:
    draft_text: str | None
    confidence: float | None
    max_tokens: int | None
    parse_ok: bool
    error_reason: str | None = None


@dataclass(frozen=True)
class TokenResult:
    token_id: int
    text: str
    is_eos: bool = False


@dataclass(frozen=True)
class VerificationResult:
    accepted_token_ids: list[int]
    rejected_token_id: int | None
    reject_position: int | None
    candidate_exhausted: bool


@dataclass(frozen=True)
class CycleTrace:
    cycle_index: int
    context_tokens: int
    dflash_parse_ok: bool
    malformed_dflash: bool
    draft_text_chars: int
    draft_candidate_tokens: int
    accepted_tokens: int
    reject_position: int | None
    candidate_exhausted: bool
    fallback_used: bool
    qwen_draft_ms: float
    dflash_parse_ms: float
    gemma_retokenize_ms: float
    e2b_verify_ms: float
    cycle_ms: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class GenerationMetrics:
    generated_tokens: int
    cycles: int
    drafted_candidate_tokens: int
    accepted_tokens: int
    fallback_tokens: int
    malformed_dflash_count: int
    dflash_parse_fail_count: int
    dflash_schema_invalid_count: int
    dflash_empty_draft_count: int
    retokenized_empty_count: int
    low_acceptance_rate: float
    fallback_rate: float
    total_ms: float
    tokens_per_second: float
    latency_per_token_ms: float
    execution_mode: str
    decoding_mode: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class GenerateResult:
    text: str
    token_ids: list[int]
    metrics: GenerationMetrics
    trace: list[CycleTrace] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "token_ids": self.token_ids,
            "metrics": self.metrics.to_dict(),
            "trace": [item.to_dict() for item in self.trace],
        }
```

- [ ] **Step 4: Implement metric counter and timer**

Create `src/htfsd/metrics/counters.py`:

```python
from __future__ import annotations

from dataclasses import dataclass

from htfsd.types import GenerationMetrics


@dataclass
class GenerationCounter:
    execution_mode: str
    decoding_mode: str
    cycles: int = 0
    drafted_candidate_tokens: int = 0
    accepted_tokens: int = 0
    fallback_tokens: int = 0
    malformed_dflash_count: int = 0
    dflash_parse_fail_count: int = 0
    dflash_schema_invalid_count: int = 0
    dflash_empty_draft_count: int = 0
    retokenized_empty_count: int = 0

    def add_cycle(
        self,
        *,
        drafted_candidate_tokens: int,
        accepted_tokens: int,
        fallback_tokens: int,
        malformed_reason: str | None,
    ) -> None:
        self.cycles += 1
        self.drafted_candidate_tokens += drafted_candidate_tokens
        self.accepted_tokens += accepted_tokens
        self.fallback_tokens += fallback_tokens
        if malformed_reason is None:
            return
        self.malformed_dflash_count += 1
        if malformed_reason == "parse_fail":
            self.dflash_parse_fail_count += 1
        elif malformed_reason == "schema_invalid":
            self.dflash_schema_invalid_count += 1
        elif malformed_reason == "empty_draft":
            self.dflash_empty_draft_count += 1
        elif malformed_reason == "retokenized_empty":
            self.retokenized_empty_count += 1
        else:
            self.dflash_schema_invalid_count += 1

    def to_metrics(self, *, total_ms: float, generated_tokens: int) -> GenerationMetrics:
        low_acceptance_rate = (
            self.accepted_tokens / self.drafted_candidate_tokens
            if self.drafted_candidate_tokens
            else 0.0
        )
        fallback_rate = self.fallback_tokens / generated_tokens if generated_tokens else 0.0
        tokens_per_second = generated_tokens / (total_ms / 1000.0) if total_ms > 0 else 0.0
        latency_per_token_ms = total_ms / generated_tokens if generated_tokens else 0.0
        return GenerationMetrics(
            generated_tokens=generated_tokens,
            cycles=self.cycles,
            drafted_candidate_tokens=self.drafted_candidate_tokens,
            accepted_tokens=self.accepted_tokens,
            fallback_tokens=self.fallback_tokens,
            malformed_dflash_count=self.malformed_dflash_count,
            dflash_parse_fail_count=self.dflash_parse_fail_count,
            dflash_schema_invalid_count=self.dflash_schema_invalid_count,
            dflash_empty_draft_count=self.dflash_empty_draft_count,
            retokenized_empty_count=self.retokenized_empty_count,
            low_acceptance_rate=low_acceptance_rate,
            fallback_rate=fallback_rate,
            total_ms=total_ms,
            tokens_per_second=tokens_per_second,
            latency_per_token_ms=latency_per_token_ms,
            execution_mode=self.execution_mode,
            decoding_mode=self.decoding_mode,
        )
```

Create `src/htfsd/metrics/timers.py`:

```python
from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator


@dataclass
class TimerValue:
    elapsed_ms: float = 0.0


@contextmanager
def timer_ms() -> Iterator[TimerValue]:
    value = TimerValue()
    start = time.perf_counter()
    try:
        yield value
    finally:
        value.elapsed_ms = (time.perf_counter() - start) * 1000.0
```

- [ ] **Step 5: Run metric tests**

Run:

```bash
pytest tests/test_metrics.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit types and metrics**

```bash
git add src/htfsd/types.py src/htfsd/metrics/counters.py src/htfsd/metrics/timers.py tests/test_metrics.py
git commit -m "feat: add shared result types and metrics"
```

## Task 3: Config Loader And Config Tests

**Files:**

- Create: `src/htfsd/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write failing config tests**

Create `tests/test_config.py`:

```python
import pytest

from htfsd.config import clamp_dflash_max_tokens, load_config, validate_benchmark_decoding


def test_load_config_maps_yaml_to_dataclasses(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        """
models:
  qwen_drafter: {model_id_or_path: "qwen-local", tensor_parallel_size: 1, dtype: "auto", gpu_memory_utilization: 0.35}
  gemma_e2b: {model_id_or_path: "e2b-local", tensor_parallel_size: 1, dtype: "auto", gpu_memory_utilization: 0.55}
  gemma_e4b_baseline: {model_id_or_path: "e4b-local", tensor_parallel_size: 1, dtype: "auto", gpu_memory_utilization: 0.90}
runtime: {backend: "vllm", execution_mode: "concurrent", max_context_tokens: 4096, seed: 1234}
generation: {max_new_tokens: 128, stop_on_eos: true}
dflash: {parser: "strict_json", required_fields: ["draft_text"], default_max_tokens: 8, hard_max_tokens: 16, experimental_repair: false}
low_tier: {acceptance_policy: "greedy_exact_match", fallback_policy: "single_token_greedy", fallback_tokens_per_cycle: 1}
decoding:
  default: "greedy"
  sampling: {enabled: true, experimental: true, temperature: 0.7, top_p: 0.9}
benchmark:
  fixture_path: "benchmarks/fixtures/prompts.jsonl"
  dataset: {enabled: false, name: null, split: null}
""",
        encoding="utf-8",
    )

    config = load_config(config_file)

    assert config.qwen_drafter.model_id_or_path == "qwen-local"
    assert config.gemma_e2b.model_id_or_path == "e2b-local"
    assert config.gemma_e4b_baseline.model_id_or_path == "e4b-local"
    assert config.runtime.execution_mode == "concurrent"
    assert config.decoding.default == "greedy"
    assert config.decoding.sampling.experimental is True


def test_dflash_max_tokens_clamps_to_hard_limit():
    assert clamp_dflash_max_tokens(requested=32, default=8, hard=16) == 16
    assert clamp_dflash_max_tokens(requested=4, default=8, hard=16) == 4
    assert clamp_dflash_max_tokens(requested=None, default=8, hard=16) == 8


def test_benchmark_low_rejects_sampling_mode():
    with pytest.raises(ValueError, match="benchmark-low only supports greedy"):
        validate_benchmark_decoding("sampling")


def test_sequential_mode_label_is_debug_non_comparable(tmp_path):
    config_file = tmp_path / "config.yaml"
    text = open("configs/local.example.yaml", encoding="utf-8").read()
    config_file.write_text(text.replace('execution_mode: "concurrent"', 'execution_mode: "sequential"'), encoding="utf-8")

    config = load_config(config_file)

    assert config.runtime.execution_mode == "sequential"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/test_config.py -v
```

Expected: FAIL because `htfsd.config` does not exist.

- [ ] **Step 3: Implement config loader**

Create `src/htfsd/config.py`:

```python
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from htfsd.types import (
    AppConfig,
    BenchmarkConfig,
    BenchmarkDatasetConfig,
    DecodingConfig,
    DFlashConfig,
    GenerationConfig,
    LowTierConfig,
    ModelConfig,
    RuntimeConfig,
    SamplingConfig,
)


def _model_config(data: dict[str, Any]) -> ModelConfig:
    return ModelConfig(
        model_id_or_path=str(data["model_id_or_path"]),
        tensor_parallel_size=int(data.get("tensor_parallel_size", 1)),
        dtype=str(data.get("dtype", "auto")),
        gpu_memory_utilization=(
            float(data["gpu_memory_utilization"])
            if data.get("gpu_memory_utilization") is not None
            else None
        ),
    )


def load_config(path: str | Path) -> AppConfig:
    with Path(path).open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    models = raw["models"]
    runtime = raw["runtime"]
    generation = raw["generation"]
    dflash = raw["dflash"]
    low_tier = raw["low_tier"]
    decoding = raw["decoding"]
    sampling = decoding["sampling"]
    benchmark = raw["benchmark"]
    dataset = benchmark["dataset"]

    return AppConfig(
        qwen_drafter=_model_config(models["qwen_drafter"]),
        gemma_e2b=_model_config(models["gemma_e2b"]),
        gemma_e4b_baseline=_model_config(models["gemma_e4b_baseline"]),
        runtime=RuntimeConfig(
            backend=str(runtime["backend"]),
            execution_mode=str(runtime["execution_mode"]),
            max_context_tokens=int(runtime["max_context_tokens"]),
            seed=int(runtime["seed"]),
        ),
        generation=GenerationConfig(
            max_new_tokens=int(generation["max_new_tokens"]),
            stop_on_eos=bool(generation["stop_on_eos"]),
        ),
        dflash=DFlashConfig(
            parser=str(dflash["parser"]),
            required_fields=list(dflash["required_fields"]),
            default_max_tokens=int(dflash["default_max_tokens"]),
            hard_max_tokens=int(dflash["hard_max_tokens"]),
            experimental_repair=bool(dflash["experimental_repair"]),
        ),
        low_tier=LowTierConfig(
            acceptance_policy=str(low_tier["acceptance_policy"]),
            fallback_policy=str(low_tier["fallback_policy"]),
            fallback_tokens_per_cycle=int(low_tier["fallback_tokens_per_cycle"]),
        ),
        decoding=DecodingConfig(
            default=str(decoding["default"]),
            sampling=SamplingConfig(
                enabled=bool(sampling["enabled"]),
                experimental=bool(sampling["experimental"]),
                temperature=float(sampling["temperature"]),
                top_p=float(sampling["top_p"]),
            ),
        ),
        benchmark=BenchmarkConfig(
            fixture_path=str(benchmark["fixture_path"]),
            dataset=BenchmarkDatasetConfig(
                enabled=bool(dataset["enabled"]),
                name=dataset["name"],
                split=dataset["split"],
            ),
        ),
    )


def clamp_dflash_max_tokens(*, requested: int | None, default: int, hard: int) -> int:
    value = default if requested is None else requested
    if value < 0:
        return 0
    return min(value, hard)


def validate_benchmark_decoding(decoding_mode: str) -> None:
    if decoding_mode != "greedy":
        raise ValueError("benchmark-low only supports greedy decoding in the MVP")
```

- [ ] **Step 4: Run config tests**

Run:

```bash
pytest tests/test_config.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit config loader**

```bash
git add src/htfsd/config.py tests/test_config.py
git commit -m "feat: add MVP config loader"
```

## Task 4: D-Flash Parser And Prompt Template

**Files:**

- Create: `src/htfsd/dflash/parser.py`
- Create: `src/htfsd/dflash/prompts.py`
- Test: `tests/test_dflash_parser.py`

- [ ] **Step 1: Write failing parser tests**

Create `tests/test_dflash_parser.py`:

```python
from htfsd.dflash.parser import parse_dflash
from htfsd.dflash.prompts import build_dflash_prompt


def test_parse_valid_minimal_envelope():
    result = parse_dflash('{"draft_text":"hello world"}')

    assert result.parse_ok is True
    assert result.draft_text == "hello world"
    assert result.confidence is None
    assert result.max_tokens is None


def test_parse_valid_optional_fields():
    result = parse_dflash('{"draft_text":"abc","confidence":0.5,"max_tokens":6}')

    assert result.parse_ok is True
    assert result.confidence == 0.5
    assert result.max_tokens == 6


def test_parse_malformed_json_rejects_without_repair():
    result = parse_dflash('draft_text: "abc"')

    assert result.parse_ok is False
    assert result.error_reason == "parse_fail"
    assert result.draft_text is None


def test_parse_empty_draft_rejects():
    result = parse_dflash('{"draft_text":"   "}')

    assert result.parse_ok is False
    assert result.error_reason == "empty_draft"


def test_parse_crlf_normalization():
    result = parse_dflash('{"draft_text":"a\\r\\nb"}')

    assert result.parse_ok is True
    assert result.draft_text == "a\nb"


def test_parse_invalid_confidence_rejects():
    result = parse_dflash('{"draft_text":"abc","confidence":2}')

    assert result.parse_ok is False
    assert result.error_reason == "schema_invalid"


def test_prompt_requests_json_only():
    prompt = build_dflash_prompt("Say hello", max_tokens=8)

    assert "JSON" in prompt
    assert "draft_text" in prompt
    assert "```" not in prompt
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/test_dflash_parser.py -v
```

Expected: FAIL because parser and prompts do not exist.

- [ ] **Step 3: Implement strict parser**

Create `src/htfsd/dflash/parser.py`:

```python
from __future__ import annotations

import json
from typing import Any

from htfsd.types import DFlashParseResult


def _normalize_draft_text(value: str) -> str:
    return value.replace("\r\n", "\n").strip()


def parse_dflash(raw_text: str) -> DFlashParseResult:
    try:
        payload: Any = json.loads(raw_text)
    except json.JSONDecodeError:
        return DFlashParseResult(
            draft_text=None,
            confidence=None,
            max_tokens=None,
            parse_ok=False,
            error_reason="parse_fail",
        )

    if not isinstance(payload, dict):
        return DFlashParseResult(None, None, None, False, "schema_invalid")

    draft_value = payload.get("draft_text")
    if not isinstance(draft_value, str):
        return DFlashParseResult(None, None, None, False, "schema_invalid")

    draft_text = _normalize_draft_text(draft_value)
    if not draft_text:
        return DFlashParseResult(None, None, None, False, "empty_draft")

    confidence = payload.get("confidence")
    if confidence is not None:
        if not isinstance(confidence, int | float) or not 0.0 <= float(confidence) <= 1.0:
            return DFlashParseResult(None, None, None, False, "schema_invalid")
        confidence = float(confidence)

    max_tokens = payload.get("max_tokens")
    if max_tokens is not None:
        if not isinstance(max_tokens, int) or max_tokens < 0:
            return DFlashParseResult(None, None, None, False, "schema_invalid")

    return DFlashParseResult(
        draft_text=draft_text,
        confidence=confidence,
        max_tokens=max_tokens,
        parse_ok=True,
        error_reason=None,
    )
```

- [ ] **Step 4: Implement Qwen prompt template**

Create `src/htfsd/dflash/prompts.py`:

```python
from __future__ import annotations


def build_dflash_prompt(context: str, *, max_tokens: int) -> str:
    return (
        "Return only one compact JSON object. "
        "Do not use Markdown fences. Do not explain. "
        'The object must contain "draft_text" and may contain "confidence" and "max_tokens". '
        f'Use at most {max_tokens} continuation tokens. '
        "Context:\n"
        f"{context}\n"
        'JSON shape: {"draft_text":"...","confidence":0.7,"max_tokens":'
        f"{max_tokens}"
        "}"
    )
```

- [ ] **Step 5: Run D-Flash tests**

Run:

```bash
pytest tests/test_dflash_parser.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit parser and prompt**

```bash
git add src/htfsd/dflash/parser.py src/htfsd/dflash/prompts.py tests/test_dflash_parser.py
git commit -m "feat: add strict D-Flash parser"
```

## Task 5: Tokenization Boundary

**Files:**

- Create: `src/htfsd/tokenization/gemma.py`
- Test: `tests/test_tokenization.py`

- [ ] **Step 1: Write failing tokenization tests**

Create `tests/test_tokenization.py`:

```python
import pytest

from htfsd.tokenization.gemma import GemmaTokenizer, RetokenizedDraft, reject_empty_draft


class FakeTokenizer:
    eos_token_id = 0

    def encode(self, text, add_special_tokens=False):
        if text == "":
            return []
        return [ord(char) for char in text]

    def decode(self, token_ids, skip_special_tokens=True):
        return "".join(chr(token_id) for token_id in token_ids if token_id != self.eos_token_id)


def test_retokenize_non_empty_draft_text():
    tokenizer = GemmaTokenizer(FakeTokenizer())

    result = tokenizer.retokenize_draft("ab", max_tokens=8)

    assert result == RetokenizedDraft(token_ids=[97, 98], empty=False)


def test_retokenize_caps_candidate_tokens():
    tokenizer = GemmaTokenizer(FakeTokenizer())

    result = tokenizer.retokenize_draft("abcd", max_tokens=2)

    assert result.token_ids == [97, 98]


def test_empty_draft_rejected_before_verify():
    with pytest.raises(ValueError, match="empty draft_text"):
        reject_empty_draft("   ")


def test_decode_final_token_ids():
    tokenizer = GemmaTokenizer(FakeTokenizer())

    assert tokenizer.decode([97, 98, 0]) == "ab"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/test_tokenization.py -v
```

Expected: FAIL because `htfsd.tokenization.gemma` does not exist.

- [ ] **Step 3: Implement tokenization boundary**

Create `src/htfsd/tokenization/gemma.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class TokenizerLike(Protocol):
    eos_token_id: int | None

    def encode(self, text: str, add_special_tokens: bool = False) -> list[int]:
        ...

    def decode(self, token_ids: list[int], skip_special_tokens: bool = True) -> str:
        ...


@dataclass(frozen=True)
class RetokenizedDraft:
    token_ids: list[int]
    empty: bool


def reject_empty_draft(draft_text: str) -> str:
    normalized = draft_text.strip()
    if not normalized:
        raise ValueError("empty draft_text")
    return normalized


class GemmaTokenizer:
    def __init__(self, tokenizer: TokenizerLike):
        self._tokenizer = tokenizer

    @property
    def eos_token_id(self) -> int | None:
        return self._tokenizer.eos_token_id

    def encode_prompt(self, prompt: str) -> list[int]:
        return self._tokenizer.encode(prompt, add_special_tokens=False)

    def retokenize_draft(self, draft_text: str, *, max_tokens: int) -> RetokenizedDraft:
        normalized = reject_empty_draft(draft_text)
        token_ids = self._tokenizer.encode(normalized, add_special_tokens=False)
        capped = token_ids[:max_tokens]
        return RetokenizedDraft(token_ids=capped, empty=len(capped) == 0)

    def decode(self, token_ids: list[int]) -> str:
        return self._tokenizer.decode(token_ids, skip_special_tokens=True)
```

- [ ] **Step 4: Run tokenization tests**

Run:

```bash
pytest tests/test_tokenization.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit tokenization boundary**

```bash
git add src/htfsd/tokenization/gemma.py tests/test_tokenization.py
git commit -m "feat: add Gemma tokenization boundary"
```

## Task 6: Acceptance Policy

**Files:**

- Create: `src/htfsd/low_tier/acceptance.py`
- Test: `tests/test_acceptance_policy.py`

- [ ] **Step 1: Write failing acceptance tests**

Create `tests/test_acceptance_policy.py`:

```python
from htfsd.low_tier.acceptance import greedy_exact_match


def test_accepts_full_matching_prefix():
    result = greedy_exact_match(candidate_token_ids=[1, 2, 3], greedy_token_ids=[1, 2, 3])

    assert result.accepted_token_ids == [1, 2, 3]
    assert result.reject_position is None
    assert result.candidate_exhausted is True
    assert result.rejected_token_id is None


def test_stops_on_first_mismatch():
    result = greedy_exact_match(candidate_token_ids=[1, 9, 3], greedy_token_ids=[1, 2, 3])

    assert result.accepted_token_ids == [1]
    assert result.reject_position == 1
    assert result.candidate_exhausted is False
    assert result.rejected_token_id == 9


def test_immediate_reject_reports_zero_position():
    result = greedy_exact_match(candidate_token_ids=[9, 2], greedy_token_ids=[1, 2])

    assert result.accepted_token_ids == []
    assert result.reject_position == 0
    assert result.candidate_exhausted is False
    assert result.rejected_token_id == 9


def test_empty_candidate_exhausted_with_empty_prefix():
    result = greedy_exact_match(candidate_token_ids=[], greedy_token_ids=[1, 2])

    assert result.accepted_token_ids == []
    assert result.reject_position is None
    assert result.candidate_exhausted is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/test_acceptance_policy.py -v
```

Expected: FAIL because `htfsd.low_tier.acceptance` does not exist.

- [ ] **Step 3: Implement acceptance policy**

Create `src/htfsd/low_tier/acceptance.py`:

```python
from __future__ import annotations

from htfsd.types import VerificationResult


def greedy_exact_match(
    *,
    candidate_token_ids: list[int],
    greedy_token_ids: list[int],
) -> VerificationResult:
    accepted: list[int] = []
    for index, candidate_token_id in enumerate(candidate_token_ids):
        if index >= len(greedy_token_ids):
            return VerificationResult(
                accepted_token_ids=accepted,
                rejected_token_id=candidate_token_id,
                reject_position=index,
                candidate_exhausted=False,
            )
        if candidate_token_id != greedy_token_ids[index]:
            return VerificationResult(
                accepted_token_ids=accepted,
                rejected_token_id=candidate_token_id,
                reject_position=index,
                candidate_exhausted=False,
            )
        accepted.append(candidate_token_id)

    return VerificationResult(
        accepted_token_ids=accepted,
        rejected_token_id=None,
        reject_position=None,
        candidate_exhausted=True,
    )
```

- [ ] **Step 4: Run acceptance tests**

Run:

```bash
pytest tests/test_acceptance_policy.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit acceptance policy**

```bash
git add src/htfsd/low_tier/acceptance.py tests/test_acceptance_policy.py
git commit -m "feat: add greedy acceptance policy"
```

## Task 7: Low Tier Engine With Fake Adapters

**Files:**

- Create: `src/htfsd/low_tier/engine.py`
- Create: `src/htfsd/low_tier/verifier.py`
- Test: `tests/test_low_tier_engine.py`

- [ ] **Step 1: Write failing engine tests with fakes**

Create `tests/test_low_tier_engine.py`:

```python
from htfsd.low_tier.engine import LowTierEngine
from htfsd.types import TokenResult, VerificationResult


class FakeTokenizer:
    eos_token_id = 0

    def encode_prompt(self, prompt):
        return [ord(char) for char in prompt]

    def retokenize_draft(self, draft_text, *, max_tokens):
        class Result:
            def __init__(self, token_ids):
                self.token_ids = token_ids
                self.empty = len(token_ids) == 0

        return Result([ord(char) for char in draft_text][:max_tokens])

    def decode(self, token_ids):
        return "".join(chr(token_id) for token_id in token_ids if token_id != 0)


class SequenceDrafter:
    def __init__(self, outputs):
        self.outputs = list(outputs)

    def draft(self, context_text, *, max_tokens):
        if self.outputs:
            return self.outputs.pop(0)
        return '{"draft_text":"x"}'


class FakeVerifier:
    def __init__(self, verification_results, fallback_tokens):
        self.verification_results = list(verification_results)
        self.fallback_tokens = list(fallback_tokens)

    def verify_greedy_prefix(self, context_token_ids, candidate_token_ids):
        return self.verification_results.pop(0)

    def greedy_next_token(self, context_token_ids):
        token_id = self.fallback_tokens.pop(0)
        return TokenResult(token_id=token_id, text=chr(token_id), is_eos=token_id == 0)


def test_engine_accepts_full_match_without_fallback():
    engine = LowTierEngine(
        drafter=SequenceDrafter(['{"draft_text":"ab"}']),
        verifier=FakeVerifier(
            [VerificationResult([97, 98], None, None, True)],
            fallback_tokens=[],
        ),
        tokenizer=FakeTokenizer(),
        execution_mode="concurrent",
        default_draft_max_tokens=8,
        hard_draft_max_tokens=16,
    )

    result = engine.generate("P", max_new_tokens=2, decoding="greedy")

    assert result.text == "Pab"
    assert result.token_ids[-2:] == [97, 98]
    assert result.metrics.accepted_tokens == 2
    assert result.metrics.fallback_tokens == 0
    assert result.trace[0].candidate_exhausted is True


def test_engine_fallbacks_on_immediate_reject_and_continues():
    engine = LowTierEngine(
        drafter=SequenceDrafter(['{"draft_text":"z"}', '{"draft_text":"b"}']),
        verifier=FakeVerifier(
            [
                VerificationResult([], 122, 0, False),
                VerificationResult([98], None, None, True),
            ],
            fallback_tokens=[97],
        ),
        tokenizer=FakeTokenizer(),
        execution_mode="concurrent",
        default_draft_max_tokens=8,
        hard_draft_max_tokens=16,
    )

    result = engine.generate("P", max_new_tokens=2, decoding="greedy")

    assert result.text == "Pab"
    assert result.metrics.fallback_tokens == 1
    assert result.metrics.accepted_tokens == 1
    assert result.trace[0].reject_position == 0
    assert result.trace[0].fallback_used is True


def test_engine_appends_partial_accept_then_fallback_on_reject():
    engine = LowTierEngine(
        drafter=SequenceDrafter(['{"draft_text":"az"}']),
        verifier=FakeVerifier(
            [VerificationResult([97], 122, 1, False)],
            fallback_tokens=[98],
        ),
        tokenizer=FakeTokenizer(),
        execution_mode="concurrent",
        default_draft_max_tokens=8,
        hard_draft_max_tokens=16,
    )

    result = engine.generate("P", max_new_tokens=2, decoding="greedy")

    assert result.text == "Pab"
    assert result.metrics.accepted_tokens == 1
    assert result.metrics.fallback_tokens == 1
    assert result.trace[0].reject_position == 1
    assert result.trace[0].candidate_exhausted is False
    assert result.trace[0].fallback_used is True


def test_engine_stops_on_eos_in_accepted_prefix():
    engine = LowTierEngine(
        drafter=SequenceDrafter(['{"draft_text":"a\\u0000x"}']),
        verifier=FakeVerifier(
            [VerificationResult([97, 0, 120], None, None, True)],
            fallback_tokens=[],
        ),
        tokenizer=FakeTokenizer(),
        execution_mode="concurrent",
        default_draft_max_tokens=8,
        hard_draft_max_tokens=16,
    )

    result = engine.generate("P", max_new_tokens=5, decoding="greedy", stop_on_eos=True)

    assert result.token_ids[-1] == 0
    assert result.token_ids == [80, 97, 0]
    assert result.metrics.accepted_tokens == 2
    assert result.metrics.fallback_tokens == 0
    assert result.metrics.cycles == 1
    assert result.trace[0].accepted_tokens == 2
    assert result.trace[0].fallback_used is False


def test_engine_fallbacks_on_malformed_dflash():
    engine = LowTierEngine(
        drafter=SequenceDrafter(["not json"]),
        verifier=FakeVerifier([], fallback_tokens=[97]),
        tokenizer=FakeTokenizer(),
        execution_mode="concurrent",
        default_draft_max_tokens=8,
        hard_draft_max_tokens=16,
    )

    result = engine.generate("P", max_new_tokens=1, decoding="greedy")

    assert result.text == "Pa"
    assert result.metrics.malformed_dflash_count == 1
    assert result.metrics.dflash_parse_fail_count == 1
    assert result.metrics.fallback_tokens == 1


def test_engine_stops_on_eos_fallback():
    engine = LowTierEngine(
        drafter=SequenceDrafter(["not json"]),
        verifier=FakeVerifier([], fallback_tokens=[0]),
        tokenizer=FakeTokenizer(),
        execution_mode="concurrent",
        default_draft_max_tokens=8,
        hard_draft_max_tokens=16,
    )

    result = engine.generate("P", max_new_tokens=5, decoding="greedy", stop_on_eos=True)

    assert result.token_ids[-1] == 0
    assert result.metrics.generated_tokens == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/test_low_tier_engine.py -v
```

Expected: FAIL because `LowTierEngine` does not exist.

- [ ] **Step 3: Add verifier protocol**

Create `src/htfsd/low_tier/verifier.py`:

```python
from __future__ import annotations

from typing import Protocol

from htfsd.types import TokenResult, VerificationResult


class GemmaE2BVerifier(Protocol):
    def verify_greedy_prefix(
        self,
        context_token_ids: list[int],
        candidate_token_ids: list[int],
    ) -> VerificationResult:
        ...

    def greedy_next_token(self, context_token_ids: list[int]) -> TokenResult:
        ...
```

- [ ] **Step 4: Implement LowTierEngine**

Create `src/htfsd/low_tier/engine.py`:

```python
from __future__ import annotations

import time
from typing import Protocol

from htfsd.config import clamp_dflash_max_tokens
from htfsd.dflash.parser import parse_dflash
from htfsd.metrics.counters import GenerationCounter
from htfsd.metrics.timers import timer_ms
from htfsd.types import CycleTrace, GenerateResult, VerificationResult


class Drafter(Protocol):
    def draft(self, context_text: str, *, max_tokens: int) -> str:
        ...


class TokenizerBoundary(Protocol):
    eos_token_id: int | None

    def encode_prompt(self, prompt: str) -> list[int]:
        ...

    def retokenize_draft(self, draft_text: str, *, max_tokens: int):
        ...

    def decode(self, token_ids: list[int]) -> str:
        ...


class Verifier(Protocol):
    def verify_greedy_prefix(
        self,
        context_token_ids: list[int],
        candidate_token_ids: list[int],
    ) -> VerificationResult:
        ...

    def greedy_next_token(self, context_token_ids: list[int]):
        ...


class LowTierEngine:
    def __init__(
        self,
        *,
        drafter: Drafter,
        verifier: Verifier,
        tokenizer: TokenizerBoundary,
        execution_mode: str,
        default_draft_max_tokens: int,
        hard_draft_max_tokens: int,
    ) -> None:
        self._drafter = drafter
        self._verifier = verifier
        self._tokenizer = tokenizer
        self._execution_mode = execution_mode
        self._default_draft_max_tokens = default_draft_max_tokens
        self._hard_draft_max_tokens = hard_draft_max_tokens

    def generate(
        self,
        prompt: str,
        *,
        max_new_tokens: int,
        decoding: str = "greedy",
        stop_on_eos: bool = True,
        debug_trace: bool = True,
    ) -> GenerateResult:
        if decoding != "greedy":
            raise ValueError("LowTierEngine correctness path only supports greedy decoding")

        context_token_ids = self._tokenizer.encode_prompt(prompt)
        initial_context_len = len(context_token_ids)
        trace: list[CycleTrace] = []
        counter = GenerationCounter(
            execution_mode=self._execution_mode,
            decoding_mode=decoding,
        )

        with timer_ms() as total_timer:
            cycle_index = 0
            while len(context_token_ids) - initial_context_len < max_new_tokens:
                cycle_start = time.perf_counter()
                with timer_ms() as draft_timer:
                    raw_dflash = self._drafter.draft(
                        self._tokenizer.decode(context_token_ids),
                        max_tokens=self._default_draft_max_tokens,
                    )

                with timer_ms() as parse_timer:
                    parse_result = parse_dflash(raw_dflash)

                malformed_reason = parse_result.error_reason if not parse_result.parse_ok else None
                candidate_token_ids: list[int] = []
                verification = VerificationResult([], None, None, True)
                fallback_used = False
                accepted_count = 0
                stop_now = False

                if parse_result.parse_ok and parse_result.draft_text is not None:
                    max_tokens = clamp_dflash_max_tokens(
                        requested=parse_result.max_tokens,
                        default=self._default_draft_max_tokens,
                        hard=self._hard_draft_max_tokens,
                    )
                    with timer_ms() as retokenize_timer:
                        retokenized = self._tokenizer.retokenize_draft(
                            parse_result.draft_text,
                            max_tokens=max_tokens,
                        )
                    candidate_token_ids = list(retokenized.token_ids)
                    if retokenized.empty:
                        malformed_reason = "retokenized_empty"
                else:
                    retokenize_timer = _static_timer()

                if candidate_token_ids and malformed_reason is None:
                    with timer_ms() as verify_timer:
                        verification = self._verifier.verify_greedy_prefix(
                            context_token_ids,
                            candidate_token_ids,
                        )
                    room = max_new_tokens - (len(context_token_ids) - initial_context_len)
                    accepted = self._accepted_until_limit_or_eos(
                        verification.accepted_token_ids,
                        room=room,
                        stop_on_eos=stop_on_eos,
                    )
                    if accepted:
                        context_token_ids.extend(accepted)
                        accepted_count = len(accepted)
                        if stop_on_eos and accepted[-1] == self._tokenizer.eos_token_id:
                            stop_now = True

                    room = max_new_tokens - (len(context_token_ids) - initial_context_len)
                    if not stop_now and not verification.candidate_exhausted and room > 0:
                        fallback_used = True
                        fallback = self._verifier.greedy_next_token(context_token_ids)
                        context_token_ids.append(fallback.token_id)
                        if stop_on_eos and fallback.is_eos:
                            stop_now = True
                else:
                    verify_timer = _static_timer()
                    room = max_new_tokens - (len(context_token_ids) - initial_context_len)
                    if room > 0:
                        fallback_used = True
                        fallback = self._verifier.greedy_next_token(context_token_ids)
                        context_token_ids.append(fallback.token_id)
                        if stop_on_eos and fallback.is_eos:
                            stop_now = True

                cycle_ms = (time.perf_counter() - cycle_start) * 1000.0
                counter.add_cycle(
                    drafted_candidate_tokens=len(candidate_token_ids),
                    accepted_tokens=accepted_count,
                    fallback_tokens=1 if fallback_used else 0,
                    malformed_reason=malformed_reason,
                )
                trace.append(
                    self._cycle_trace(
                        cycle_index,
                        context_token_ids,
                        parse_result.parse_ok,
                        malformed_reason,
                        parse_result.draft_text,
                        candidate_token_ids,
                        verification,
                        accepted_count,
                        fallback_used,
                        draft_timer.elapsed_ms,
                        parse_timer.elapsed_ms,
                        retokenize_timer.elapsed_ms,
                        verify_timer.elapsed_ms,
                        cycle_ms,
                    )
                )
                cycle_index += 1
                if stop_now:
                    break

        generated_token_count = len(context_token_ids) - initial_context_len
        return GenerateResult(
            text=self._tokenizer.decode(context_token_ids),
            token_ids=context_token_ids,
            metrics=counter.to_metrics(
                total_ms=total_timer.elapsed_ms,
                generated_tokens=generated_token_count,
            ),
            trace=trace if debug_trace else [],
        )

    def _accepted_until_limit_or_eos(
        self,
        accepted_token_ids: list[int],
        *,
        room: int,
        stop_on_eos: bool,
    ) -> list[int]:
        accepted = list(accepted_token_ids[:room])
        eos_token_id = self._tokenizer.eos_token_id
        if stop_on_eos and eos_token_id is not None and eos_token_id in accepted:
            eos_index = accepted.index(eos_token_id)
            return accepted[: eos_index + 1]
        return accepted

    def _cycle_trace(
        self,
        cycle_index: int,
        context_token_ids: list[int],
        parse_ok: bool,
        malformed_reason: str | None,
        draft_text: str | None,
        candidate_token_ids: list[int],
        verification: VerificationResult,
        accepted_count: int,
        fallback_used: bool,
        qwen_draft_ms: float,
        dflash_parse_ms: float,
        gemma_retokenize_ms: float,
        e2b_verify_ms: float,
        cycle_ms: float,
    ) -> CycleTrace:
        return CycleTrace(
            cycle_index=cycle_index,
            context_tokens=len(context_token_ids),
            dflash_parse_ok=parse_ok,
            malformed_dflash=malformed_reason is not None,
            draft_text_chars=len(draft_text or ""),
            draft_candidate_tokens=len(candidate_token_ids),
            accepted_tokens=accepted_count,
            reject_position=verification.reject_position,
            candidate_exhausted=verification.candidate_exhausted,
            fallback_used=fallback_used,
            qwen_draft_ms=qwen_draft_ms,
            dflash_parse_ms=dflash_parse_ms,
            gemma_retokenize_ms=gemma_retokenize_ms,
            e2b_verify_ms=e2b_verify_ms,
            cycle_ms=cycle_ms,
        )


class _static_timer:
    elapsed_ms = 0.0
```

- [ ] **Step 5: Run engine tests**

Run:

```bash
pytest tests/test_low_tier_engine.py -v
```

Expected: PASS.

- [ ] **Step 6: Run related unit tests**

Run:

```bash
pytest tests/test_metrics.py tests/test_config.py tests/test_dflash_parser.py tests/test_tokenization.py tests/test_acceptance_policy.py tests/test_low_tier_engine.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit engine with fake adapter coverage**

```bash
git add src/htfsd/low_tier/engine.py src/htfsd/low_tier/verifier.py tests/test_low_tier_engine.py
git commit -m "feat: add Low Tier engine with fake adapter tests"
```

## Task 8: vLLM Runtime Adapter And Qwen Drafter

**Files:**

- Create: `src/htfsd/runtime/vllm_adapter.py`
- Create: `src/htfsd/low_tier/drafter.py`
- Test: `tests/test_vllm_adapter_optional.py`

- [ ] **Step 1: Write optional vLLM import tests**

Create `tests/test_vllm_adapter_optional.py`:

```python
import pytest

from htfsd.runtime.vllm_adapter import VLLM_AVAILABLE, VllmModelHandle


def test_vllm_availability_flag_is_boolean():
    assert isinstance(VLLM_AVAILABLE, bool)


@pytest.mark.vllm
def test_vllm_model_handle_requires_vllm_when_constructed_without_runtime():
    if VLLM_AVAILABLE:
        pytest.skip("This smoke test is for environments without vLLM imports")
    with pytest.raises(RuntimeError, match="vLLM is not available"):
        VllmModelHandle(model_id_or_path="missing")
```

- [ ] **Step 2: Run optional adapter tests to verify they fail**

Run:

```bash
pytest tests/test_vllm_adapter_optional.py -v
```

Expected: FAIL because `htfsd.runtime.vllm_adapter` does not exist.

- [ ] **Step 3: Implement vLLM adapter with lazy imports**

Create `src/htfsd/runtime/vllm_adapter.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from importlib import metadata
from typing import Any

from htfsd.low_tier.acceptance import greedy_exact_match
from htfsd.types import ModelConfig, TokenResult, VerificationResult

try:
    from vllm import LLM, SamplingParams
except Exception:
    LLM = None
    SamplingParams = None

VLLM_AVAILABLE = LLM is not None and SamplingParams is not None
VERIFICATION_ADAPTER_VERSION = "prompt-logprobs-v1"


def vllm_version() -> str:
    try:
        return metadata.version("vllm")
    except metadata.PackageNotFoundError:
        return "not-installed"


@dataclass
class VllmModelHandle:
    model_id_or_path: str
    tensor_parallel_size: int = 1
    dtype: str = "auto"
    gpu_memory_utilization: float | None = None
    llm: Any | None = None

    @classmethod
    def from_config(cls, config: ModelConfig) -> "VllmModelHandle":
        return cls(
            model_id_or_path=config.model_id_or_path,
            tensor_parallel_size=config.tensor_parallel_size,
            dtype=config.dtype,
            gpu_memory_utilization=config.gpu_memory_utilization,
        )

    def load(self) -> Any:
        if self.llm is not None:
            return self.llm
        if not VLLM_AVAILABLE:
            raise RuntimeError("vLLM is not available in this environment")
        kwargs: dict[str, Any] = {
            "model": self.model_id_or_path,
            "tensor_parallel_size": self.tensor_parallel_size,
            "dtype": self.dtype,
        }
        if self.gpu_memory_utilization is not None:
            kwargs["gpu_memory_utilization"] = self.gpu_memory_utilization
        self.llm = LLM(**kwargs)
        return self.llm


class VllmGenerationAdapter:
    def __init__(self, handle: VllmModelHandle):
        self._handle = handle

    def generate_text(
        self,
        prompt: str,
        *,
        max_tokens: int,
        temperature: float = 0.0,
        top_p: float = 1.0,
    ) -> str:
        llm = self._handle.load()
        params = SamplingParams(
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
        )
        outputs = llm.generate([prompt], params)
        return outputs[0].outputs[0].text


class VllmVerificationAdapter:
    def __init__(self, handle: VllmModelHandle, tokenizer):
        self._handle = handle
        self._tokenizer = tokenizer

    def verify_greedy_prefix(
        self,
        context_token_ids: list[int],
        candidate_token_ids: list[int],
    ) -> VerificationResult:
        greedy_ids = self._greedy_ids_for_positions(
            context_token_ids=context_token_ids,
            positions=len(candidate_token_ids),
        )
        return greedy_exact_match(
            candidate_token_ids=candidate_token_ids,
            greedy_token_ids=greedy_ids,
        )

    def greedy_next_token(self, context_token_ids: list[int]) -> TokenResult:
        greedy_ids = self._greedy_ids_for_positions(context_token_ids=context_token_ids, positions=1)
        token_id = greedy_ids[0]
        text = self._tokenizer.decode([token_id], skip_special_tokens=True)
        return TokenResult(
            token_id=token_id,
            text=text,
            is_eos=token_id == getattr(self._tokenizer, "eos_token_id", None),
        )

    def _greedy_ids_for_positions(self, *, context_token_ids: list[int], positions: int) -> list[int]:
        llm = self._handle.load()
        params = SamplingParams(
            temperature=0.0,
            max_tokens=positions,
            logprobs=1,
        )
        prompt = {"prompt_token_ids": context_token_ids}
        outputs = llm.generate([prompt], params)
        generated = outputs[0].outputs[0].token_ids
        return list(generated[:positions])
```

This adapter uses generated greedy token IDs as the MVP route for verification. During implementation, run the optional GPU equivalence test before trusting Low Tier benchmark metrics. If the pinned vLLM version exposes a better prompt-logprobs path, keep the public methods unchanged and replace only `_greedy_ids_for_positions`.

- [ ] **Step 4: Implement Qwen D-Flash drafter**

Create `src/htfsd/low_tier/drafter.py`:

```python
from __future__ import annotations

from htfsd.dflash.prompts import build_dflash_prompt
from htfsd.runtime.vllm_adapter import VllmGenerationAdapter


class QwenDFlashDrafter:
    def __init__(self, generation: VllmGenerationAdapter):
        self._generation = generation

    def draft(self, context_text: str, *, max_tokens: int) -> str:
        prompt = build_dflash_prompt(context_text, max_tokens=max_tokens)
        return self._generation.generate_text(
            prompt,
            max_tokens=max_tokens * 8,
            temperature=0.0,
            top_p=1.0,
        )
```

- [ ] **Step 5: Run adapter tests**

Run:

```bash
pytest tests/test_vllm_adapter_optional.py -v
```

Expected: PASS or SKIP for environment-dependent test branches.

- [ ] **Step 6: Commit runtime adapter and drafter**

```bash
git add src/htfsd/runtime/vllm_adapter.py src/htfsd/low_tier/drafter.py tests/test_vllm_adapter_optional.py
git commit -m "feat: add vLLM adapters and Qwen drafter"
```

## Task 9: CLI Thin Wrapper For Interactive Generate

**Files:**

- Create: `src/htfsd/cli/generate.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write failing CLI tests**

Create `tests/test_cli.py`:

```python
import json

from htfsd.cli.generate import write_trace_jsonl
from htfsd.types import CycleTrace


def test_write_trace_jsonl(tmp_path):
    output = tmp_path / "trace.jsonl"
    trace = [
        CycleTrace(
            cycle_index=0,
            context_tokens=2,
            dflash_parse_ok=True,
            malformed_dflash=False,
            draft_text_chars=1,
            draft_candidate_tokens=1,
            accepted_tokens=1,
            reject_position=None,
            candidate_exhausted=True,
            fallback_used=False,
            qwen_draft_ms=1.0,
            dflash_parse_ms=0.1,
            gemma_retokenize_ms=0.1,
            e2b_verify_ms=1.0,
            cycle_ms=2.2,
        )
    ]

    write_trace_jsonl(output, trace)

    rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    assert rows[0]["cycle_index"] == 0
    assert rows[0]["candidate_exhausted"] is True
```

- [ ] **Step 2: Run CLI tests to verify they fail**

Run:

```bash
pytest tests/test_cli.py -v
```

Expected: FAIL because `htfsd.cli.generate` does not exist.

- [ ] **Step 3: Implement trace writer and CLI entrypoint**

Create `src/htfsd/cli/generate.py`:

```python
from __future__ import annotations

import argparse
import json
from pathlib import Path

from htfsd.config import load_config
from htfsd.low_tier.drafter import QwenDFlashDrafter
from htfsd.low_tier.engine import LowTierEngine
from htfsd.runtime.vllm_adapter import VllmGenerationAdapter, VllmModelHandle, VllmVerificationAdapter
from htfsd.tokenization.gemma import GemmaTokenizer


def write_trace_jsonl(path: str | Path, trace) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for item in trace:
            handle.write(json.dumps(item.to_dict(), ensure_ascii=False) + "\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run HTFSD Low Tier generation")
    parser.add_argument("--config", required=True)
    parser.add_argument("--prompt")
    parser.add_argument("--max-new-tokens", type=int)
    parser.add_argument("--decoding", default=None, choices=["greedy", "sampling"])
    parser.add_argument("--temperature", type=float, default=None)
    parser.add_argument("--debug-trace")
    return parser


def _build_engine(config) -> LowTierEngine:
    qwen_handle = VllmModelHandle.from_config(config.qwen_drafter)
    e2b_handle = VllmModelHandle.from_config(config.gemma_e2b)
    e2b_llm = e2b_handle.load()
    tokenizer = GemmaTokenizer(e2b_llm.get_tokenizer())
    drafter = QwenDFlashDrafter(VllmGenerationAdapter(qwen_handle))
    verifier = VllmVerificationAdapter(e2b_handle, e2b_llm.get_tokenizer())
    return LowTierEngine(
        drafter=drafter,
        verifier=verifier,
        tokenizer=tokenizer,
        execution_mode=config.runtime.execution_mode,
        default_draft_max_tokens=config.dflash.default_max_tokens,
        hard_draft_max_tokens=config.dflash.hard_max_tokens,
    )


def run_single_prompt(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    decoding = args.decoding or config.decoding.default
    if decoding == "sampling":
        print("sampling mode is experimental and not used for correctness metrics")
    engine = _build_engine(config)
    result = engine.generate(
        args.prompt,
        max_new_tokens=args.max_new_tokens or config.generation.max_new_tokens,
        decoding="greedy" if decoding == "sampling" else decoding,
        stop_on_eos=config.generation.stop_on_eos,
        debug_trace=bool(args.debug_trace),
    )
    print(result.text)
    print(json.dumps(result.metrics.to_dict(), ensure_ascii=False, indent=2))
    if args.debug_trace:
        write_trace_jsonl(args.debug_trace, result.trace)
    return 0


def run_prompt_loop(args: argparse.Namespace) -> int:
    while True:
        prompt = input("htfsd> ").strip()
        if prompt in {"exit", "quit"}:
            return 0
        if not prompt:
            continue
        args.prompt = prompt
        run_single_prompt(args)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.prompt:
        return run_single_prompt(args)
    return run_prompt_loop(args)


if __name__ == "__main__":
    raise SystemExit(main())
```

This CLI is intentionally thin. It builds adapters, delegates the loop to `LowTierEngine`, prints output/metrics, and writes trace JSONL.

- [ ] **Step 4: Run CLI tests**

Run:

```bash
pytest tests/test_cli.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit generate CLI**

```bash
git add src/htfsd/cli/generate.py tests/test_cli.py
git commit -m "feat: add interactive generate CLI"
```

## Task 10: Low Tier Batch Benchmark

**Files:**

- Create: `src/htfsd/benchmarks/fixtures.py`
- Create: `src/htfsd/benchmarks/low_tier.py`
- Create: `src/htfsd/cli/benchmark_low.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Add failing fixture and JSONL writer tests**

Append to `tests/test_cli.py`:

```python
from htfsd.benchmarks.fixtures import load_prompt_fixtures
from htfsd.benchmarks.low_tier import write_benchmark_row


def test_load_prompt_fixtures(tmp_path):
    fixture = tmp_path / "prompts.jsonl"
    fixture.write_text('{"id":"a","prompt":"Hello","max_new_tokens":3}\n', encoding="utf-8")

    rows = load_prompt_fixtures(fixture)

    assert rows == [{"id": "a", "prompt": "Hello", "max_new_tokens": 3}]


def test_write_benchmark_row_jsonl(tmp_path):
    output = tmp_path / "low.jsonl"
    write_benchmark_row(
        output,
        {
            "prompt_id": "a",
            "status": "ok",
            "error": None,
            "metrics": {"generated_tokens": 1},
        },
    )

    rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    assert rows[0]["prompt_id"] == "a"
    assert rows[0]["status"] == "ok"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/test_cli.py -v
```

Expected: FAIL because benchmark modules do not exist.

- [ ] **Step 3: Implement fixture loader**

Create `src/htfsd/benchmarks/fixtures.py`:

```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_prompt_fixtures(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            payload = json.loads(stripped)
            rows.append(
                {
                    "id": str(payload["id"]),
                    "prompt": str(payload["prompt"]),
                    "max_new_tokens": int(payload.get("max_new_tokens", 128)),
                }
            )
    return rows
```

- [ ] **Step 4: Implement Low Tier benchmark JSONL writer and runner**

Create `src/htfsd/benchmarks/low_tier.py`:

```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from htfsd.benchmarks.fixtures import load_prompt_fixtures
from htfsd.config import validate_benchmark_decoding


def write_benchmark_row(path: str | Path, row: dict[str, Any]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def run_low_tier_benchmark(
    *,
    engine,
    fixture_path: str | Path,
    output_path: str | Path,
    decoding: str = "greedy",
) -> None:
    validate_benchmark_decoding(decoding)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text("", encoding="utf-8")
    for fixture in load_prompt_fixtures(fixture_path):
        try:
            result = engine.generate(
                fixture["prompt"],
                max_new_tokens=fixture["max_new_tokens"],
                decoding="greedy",
            )
            row = {
                "prompt_id": fixture["id"],
                "status": "ok",
                "error": None,
                "prompt": fixture["prompt"],
                "metrics": result.metrics.to_dict(),
                "output_text": result.text,
            }
        except Exception as exc:
            row = {
                "prompt_id": fixture["id"],
                "status": "error",
                "error": str(exc),
                "prompt": fixture["prompt"],
            }
        write_benchmark_row(output_path, row)
```

- [ ] **Step 5: Implement benchmark-low CLI**

Create `src/htfsd/cli/benchmark_low.py`:

```python
from __future__ import annotations

import argparse

from htfsd.benchmarks.low_tier import run_low_tier_benchmark
from htfsd.cli.generate import _build_engine
from htfsd.config import load_config, validate_benchmark_decoding


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Low Tier batch benchmark")
    parser.add_argument("--config", required=True)
    parser.add_argument("--fixtures")
    parser.add_argument("--output", required=True)
    parser.add_argument("--decoding", default="greedy")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    validate_benchmark_decoding(args.decoding)
    config = load_config(args.config)
    engine = _build_engine(config)
    run_low_tier_benchmark(
        engine=engine,
        fixture_path=args.fixtures or config.benchmark.fixture_path,
        output_path=args.output,
        decoding=args.decoding,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 6: Run benchmark tests**

Run:

```bash
pytest tests/test_cli.py tests/test_config.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit Low Tier benchmark**

```bash
git add src/htfsd/benchmarks/fixtures.py src/htfsd/benchmarks/low_tier.py src/htfsd/cli/benchmark_low.py tests/test_cli.py
git commit -m "feat: add Low Tier batch benchmark"
```

## Task 11: Gemma E4B Baseline Benchmark

**Files:**

- Create: `src/htfsd/benchmarks/baseline_e4b.py`
- Create: `src/htfsd/cli/baseline_e4b.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Add failing baseline writer test**

Append to `tests/test_cli.py`:

```python
from htfsd.benchmarks.baseline_e4b import baseline_row


def test_baseline_row_shape():
    row = baseline_row(
        prompt_id="p1",
        prompt_tokens=5,
        generated_tokens=7,
        total_ms=100.0,
        output_text="hello",
    )

    assert row["prompt_id"] == "p1"
    assert row["tokens_per_second"] == 70.0
    assert row["latency_per_token_ms"] == 100.0 / 7
    assert row["output_text"] == "hello"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/test_cli.py -v
```

Expected: FAIL because `htfsd.benchmarks.baseline_e4b` does not exist.

- [ ] **Step 3: Implement baseline row and runner**

Create `src/htfsd/benchmarks/baseline_e4b.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from htfsd.benchmarks.fixtures import load_prompt_fixtures
from htfsd.metrics.timers import timer_ms


def baseline_row(
    *,
    prompt_id: str,
    prompt_tokens: int,
    generated_tokens: int,
    total_ms: float,
    output_text: str,
    peak_vram_mb: float | None = None,
) -> dict:
    return {
        "prompt_id": prompt_id,
        "prompt_tokens": prompt_tokens,
        "generated_tokens": generated_tokens,
        "total_ms": total_ms,
        "tokens_per_second": generated_tokens / (total_ms / 1000.0) if total_ms > 0 else 0.0,
        "latency_per_token_ms": total_ms / generated_tokens if generated_tokens else 0.0,
        "peak_vram_mb": peak_vram_mb,
        "output_text": output_text,
    }


def run_e4b_baseline(
    *,
    generation_adapter,
    tokenizer,
    fixture_path: str | Path,
    output_path: str | Path,
) -> None:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("", encoding="utf-8")
    with output.open("a", encoding="utf-8") as handle:
        for fixture in load_prompt_fixtures(fixture_path):
            try:
                prompt_token_ids = tokenizer.encode(fixture["prompt"], add_special_tokens=False)
                with timer_ms() as elapsed:
                    text = generation_adapter.generate_text(
                        fixture["prompt"],
                        max_tokens=fixture["max_new_tokens"],
                        temperature=0.0,
                        top_p=1.0,
                    )
                generated_token_ids = tokenizer.encode(text, add_special_tokens=False)
                row = baseline_row(
                    prompt_id=fixture["id"],
                    prompt_tokens=len(prompt_token_ids),
                    generated_tokens=len(generated_token_ids),
                    total_ms=elapsed.elapsed_ms,
                    output_text=text,
                )
                row["status"] = "ok"
                row["error"] = None
            except Exception as exc:
                row = {
                    "prompt_id": fixture["id"],
                    "status": "error",
                    "error": str(exc),
                }
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
```

- [ ] **Step 4: Implement baseline CLI**

Create `src/htfsd/cli/baseline_e4b.py`:

```python
from __future__ import annotations

import argparse

from htfsd.benchmarks.baseline_e4b import run_e4b_baseline
from htfsd.config import load_config
from htfsd.runtime.vllm_adapter import VllmGenerationAdapter, VllmModelHandle


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Gemma E4B autoregressive baseline")
    parser.add_argument("--config", required=True)
    parser.add_argument("--fixtures")
    parser.add_argument("--output", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = load_config(args.config)
    handle = VllmModelHandle.from_config(config.gemma_e4b_baseline)
    llm = handle.load()
    run_e4b_baseline(
        generation_adapter=VllmGenerationAdapter(handle),
        tokenizer=llm.get_tokenizer(),
        fixture_path=args.fixtures or config.benchmark.fixture_path,
        output_path=args.output,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Run baseline tests**

Run:

```bash
pytest tests/test_cli.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit E4B baseline**

```bash
git add src/htfsd/benchmarks/baseline_e4b.py src/htfsd/cli/baseline_e4b.py tests/test_cli.py
git commit -m "feat: add Gemma E4B baseline benchmark"
```

## Task 12: Optional GPU Equivalence Test For vLLM Verification

**Files:**

- Modify: `tests/test_vllm_adapter_optional.py`

- [ ] **Step 1: Add marked equivalence test skeleton with real assertions**

Append to `tests/test_vllm_adapter_optional.py`:

```python
import os

from htfsd.runtime.vllm_adapter import VllmVerificationAdapter


@pytest.mark.gpu
@pytest.mark.vllm
def test_vllm_verification_adapter_matches_greedy_generation_for_one_token():
    model_path = os.environ.get("HTFSD_TEST_GEMMA_E2B")
    if not model_path:
        pytest.skip("Set HTFSD_TEST_GEMMA_E2B to run GPU vLLM equivalence test")

    handle = VllmModelHandle(model_id_or_path=model_path)
    llm = handle.load()
    tokenizer = llm.get_tokenizer()
    adapter = VllmVerificationAdapter(handle, tokenizer)
    context_token_ids = tokenizer.encode("Hello", add_special_tokens=False)

    token = adapter.greedy_next_token(context_token_ids)
    verification = adapter.verify_greedy_prefix(context_token_ids, [token.token_id])

    assert verification.accepted_token_ids == [token.token_id]
    assert verification.reject_position is None
    assert verification.candidate_exhausted is True
```

- [ ] **Step 2: Run optional test without GPU env**

Run:

```bash
pytest tests/test_vllm_adapter_optional.py -v
```

Expected: PASS with the GPU test skipped if `HTFSD_TEST_GEMMA_E2B` is unset.

- [ ] **Step 3: Commit optional integration test**

```bash
git add tests/test_vllm_adapter_optional.py
git commit -m "test: add optional vLLM verification equivalence test"
```

## Task 13: Full Fast Unit Verification

**Files:**

- Verify all non-GPU tests.

- [ ] **Step 1: Run compile check**

Run:

```bash
python -m compileall src tests
```

Expected: exit 0.

- [ ] **Step 2: Run fast tests**

Run:

```bash
pytest -m "not gpu and not vllm" -v
```

Expected: PASS for all fast tests.

- [ ] **Step 3: Check git status**

Run:

```bash
git status --short
```

Expected: no unstaged implementation changes.

## Task 14: Manual Smoke Commands

**Files:**

- No new files unless user creates `configs/local.yaml` from the example.

- [ ] **Step 1: Prepare local config manually**

Run:

```bash
cp configs/local.example.yaml configs/local.yaml
```

Edit only `model_id_or_path` values in `configs/local.yaml` for the local machine.

- [ ] **Step 2: Run E4B baseline smoke command**

Run:

```bash
htfsd-baseline-e4b --config configs/local.yaml --fixtures benchmarks/fixtures/prompts.jsonl --output runs/e4b_baseline.jsonl
```

Expected:

- `runs/e4b_baseline.jsonl` exists.
- Each line is valid JSON.
- Prompt-level failures are encoded as `status: "error"` and do not erase the file.

- [ ] **Step 3: Run Low Tier batch smoke command**

Run:

```bash
htfsd-benchmark-low --config configs/local.yaml --fixtures benchmarks/fixtures/prompts.jsonl --output runs/low_tier.jsonl
```

Expected:

- `runs/low_tier.jsonl` exists.
- `decoding_mode` is `greedy`.
- Low Tier output is described only as Gemma E2B greedy-equivalent.

- [ ] **Step 4: Run interactive single-prompt smoke command**

Run:

```bash
htfsd-generate --config configs/local.yaml --prompt "Liet ke mot vai tinh thanh cua Viet Nam" --debug-trace runs/trace.jsonl
```

Expected:

- command prints generated text and metrics.
- `runs/trace.jsonl` exists.
- trace rows include `reject_position`, `candidate_exhausted`, `fallback_used`, and stage latencies.

## Task 15: Final Scope Audit

**Files:**

- No code files unless audit finds a specific mismatch.

- [ ] **Step 1: Search for forbidden MVP surfaces**

Run:

```bash
rg -n "High Tier|EAGLE|hidden-state promotion|Gemma E4B verification|lossless|speedup" src tests README.md docs || true
```

Expected:

- No implementation files expose High Tier, EAGLE, or hidden-state promotion.
- Any `lossless` or `speedup` references are guardrails or design text, not claims.

- [ ] **Step 2: Search generated artifacts**

Run:

```bash
git status --short
```

Expected:

- No `runs/*.jsonl` file is staged.
- `docs/htfsd.md` may remain untracked if it was already untracked before this implementation stream.

- [ ] **Step 3: Final commit if audit changed files**

If the audit required code edits, run the affected tests, then commit:

```bash
git add <changed-files>
git commit -m "chore: align MVP scope guardrails"
```

If the audit did not require code edits, do not create an empty commit.

## Self-Review Checklist

- Spec coverage:
  - Phase 0 config and Gemma E4B baseline are covered by Tasks 1, 3, 11, and 14.
  - Phase 1 strict D-Flash parser, prompt, and Qwen drafter are covered by Tasks 4 and 8.
  - Phase 2 engine, verifier adapter, generate CLI, and benchmark-low CLI are covered by Tasks 7, 8, 9, 10, 12, and 14.
  - Python API core and thin CLI wrappers are covered by Tasks 7, 9, 10, and 11.
  - Fake-adapter tests are covered by Task 7.
  - Optional vLLM tests are covered by Tasks 8 and 12.
  - Greedy default, sampling experimental, and sequential debug/non-comparable are covered by Tasks 1, 3, 9, 10, and 15.

- Placeholder scan:
  - The plan must not contain empty placeholder markers or vague instructions.
  - Each task names exact files and commands.
  - Code steps include concrete code snippets.

- Type consistency:
  - `GenerateResult`, `VerificationResult`, `TokenResult`, `CycleTrace`, and `GenerationMetrics` are defined in Task 2 and used consistently afterward.
  - `verify_greedy_prefix(context_token_ids, candidate_token_ids)` is the stable verifier signature.
  - `low_acceptance_rate` is computed from Gemma candidate tokens after retokenization and cap.

- Scope consistency:
  - No task implements High Tier.
  - No task implements EAGLE.
  - No task implements hidden-state promotion.
  - No task routes Low Tier generation through Gemma E4B.
  - No task claims Gemma E4B speedup or lossless generation for Phase 0-2.
