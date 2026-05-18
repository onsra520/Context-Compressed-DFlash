# HTFSD Full Flatten Src Layout Design

## Goal

Move HTFSD implementation code out of `src/htfsd/` and directly under `src/`, with no `src/htfsd` compatibility wrapper.

This is a structural refactor only. It must not change Low Tier decoding behavior, D-Flash parsing behavior, greedy acceptance/fallback semantics, benchmark output contracts, or optional vLLM behavior.

## Chosen Approach

Use a full flatten with no compatibility package.

The previous package root:

```text
src/htfsd/
```

will be removed after its contents are moved. Consumers in this repo will import from top-level modules and packages through `PYTHONPATH=src`.

Console command names stay unchanged:

```text
htfsd-generate
htfsd-benchmark-low
htfsd-baseline-e4b
```

Only their entrypoint targets change.

## Target Layout

The implementation layout after refactor:

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

Do not keep:

```text
src/htfsd/
```

Do not create `src/types.py`. A top-level `types.py` would shadow the Python standard-library `types` module when running with `PYTHONPATH=src`, which can break tests, Pyright, or dependencies. The existing result/dataclass module becomes:

```text
src/htfsd_types.py
```

## File Move Mapping

```text
src/htfsd/config.py          -> src/config.py
src/htfsd/types.py           -> src/htfsd_types.py
src/htfsd/benchmarks/        -> src/benchmarks/
src/htfsd/cli/               -> src/cli/
src/htfsd/dflash/            -> src/dflash/
src/htfsd/low_tier/          -> src/low_tier/
src/htfsd/metrics/           -> src/metrics/
src/htfsd/runtime/           -> src/runtime/
src/htfsd/tokenization/      -> src/tokenization/
```

Any empty `src/htfsd/` directory must be removed. No wrapper modules should remain under `src/htfsd`.

## Import Rewrite

All repo imports must be rewritten from `htfsd.*` to top-level modules/packages.

Examples:

```python
from htfsd.config import load_config
from htfsd.types import GenerateResult
from htfsd.low_tier.engine import LowTierEngine
```

become:

```python
from config import load_config
from htfsd_types import GenerateResult
from low_tier.engine import LowTierEngine
```

The same pattern applies across implementation code and tests:

```text
htfsd.benchmarks.*    -> benchmarks.*
htfsd.cli.*           -> cli.*
htfsd.config          -> config
htfsd.dflash.*        -> dflash.*
htfsd.low_tier.*      -> low_tier.*
htfsd.metrics.*       -> metrics.*
htfsd.runtime.*       -> runtime.*
htfsd.tokenization.*  -> tokenization.*
htfsd.types           -> htfsd_types
```

## Packaging And Tooling

Update `pyproject.toml` console script entrypoints:

```toml
htfsd-generate = "cli.generate:main"
htfsd-benchmark-low = "cli.benchmark_low:main"
htfsd-baseline-e4b = "cli.baseline_e4b:main"
```

Keep the command names unchanged.

Setuptools should continue to discover packages under `src`, but it must also include the top-level modules:

```text
config
htfsd_types
```

If automatic discovery does not include those modules, add an explicit setuptools py-modules configuration.

Update `pyrightconfig.json` to check the flattened layout:

```json
{
  "include": ["src", "tests"]
}
```

Keep the existing venv, Python version, type-checking mode, and optional dependency diagnostic policy unless tool output proves a narrow change is required.

Pylint gate changes from:

```bash
pylint src/htfsd
```

to:

```bash
pylint src
```

because the implementation is no longer nested under `src/htfsd`.

## Verification

Required verification after implementation:

```bash
PYTHONPATH=src pytest -m "not gpu and not vllm" -v
pyright
pylint src
```

The optional GPU/vLLM tests remain marked and excluded from the default non-GPU gate.

## Scope Audit

Run a stale-reference and scope audit:

```bash
rg -n "from htfsd|import htfsd|src/htfsd|htfsd\\.types|High Tier|EAGLE|hidden-state promotion" src tests pyproject.toml pyrightconfig.json
```

Expected results:

- no stale `from htfsd...` or `import htfsd` imports;
- no `src/htfsd` tooling path references;
- no `htfsd.types` references;
- no new High Tier, EAGLE, or hidden-state promotion implementation.

The project distribution name may remain `htfsd` in `pyproject.toml`, and CLI command names may remain prefixed with `htfsd-`.

## Guardrails

- Do not keep a compatibility package under `src/htfsd`.
- Do not create `src/types.py`.
- Do not change Low Tier loop semantics.
- Do not change D-Flash parser behavior.
- Do not change greedy acceptance/fallback semantics.
- Do not change benchmark output contracts.
- Do not make optional vLLM a hard requirement.
- Do not add High Tier, EAGLE, or hidden-state promotion.
- Limit implementation to file moves, import rewrites, packaging entrypoint updates, and tool config updates needed by the new layout.
