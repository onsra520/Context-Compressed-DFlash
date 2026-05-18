# HTFSD Full Flatten Src Layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move HTFSD implementation code out of `src/htfsd/` and directly under `src/` with no compatibility wrapper.

**Architecture:** This is a structural refactor only: move files, rewrite imports, update console entrypoints, update tool scopes, and verify behavior stays unchanged. The flattened layout uses `PYTHONPATH=src` with top-level packages like `low_tier`, `dflash`, and `runtime`, plus top-level modules `config` and `htfsd_types`.

**Tech Stack:** Python 3.13 local venv, setuptools, pytest, Pyright, Pylint.

---

## File Structure

Create or move to this target layout:

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

Remove completely:

```text
src/htfsd/
```

Do not create:

```text
src/types.py
```

`src/types.py` would shadow the Python standard-library `types` module when `PYTHONPATH=src` is active.

## Guardrails

- Do not keep a compatibility package under `src/htfsd`.
- Do not create `src/types.py`.
- Do not change Low Tier loop semantics.
- Do not change D-Flash parser behavior.
- Do not change greedy acceptance/fallback semantics.
- Do not change benchmark output contracts.
- Do not make optional vLLM a hard requirement.
- Do not add High Tier, EAGLE, or hidden-state promotion.
- Leave the untracked `docs/htfsd.md` alone unless the user explicitly asks otherwise.

## Task 1: Move Source Layout

**Files:**
- Move: `src/htfsd/config.py` -> `src/config.py`
- Move: `src/htfsd/types.py` -> `src/htfsd_types.py`
- Move: `src/htfsd/benchmarks/` -> `src/benchmarks/`
- Move: `src/htfsd/cli/` -> `src/cli/`
- Move: `src/htfsd/dflash/` -> `src/dflash/`
- Move: `src/htfsd/low_tier/` -> `src/low_tier/`
- Move: `src/htfsd/metrics/` -> `src/metrics/`
- Move: `src/htfsd/runtime/` -> `src/runtime/`
- Move: `src/htfsd/tokenization/` -> `src/tokenization/`
- Delete: `src/htfsd/__init__.py`

- [ ] **Step 1: Confirm branch and generated files**

Run:

```bash
git branch --show-current
git status --short --untracked-files=all
find src tests -type d -name __pycache__ -print
```

Expected:

```text
main
?? docs/htfsd.md
```

There may be `__pycache__` directories. They are generated files and should not be committed.

- [ ] **Step 2: Remove generated Python caches**

Run:

```bash
find src tests -type d -name __pycache__ -prune -exec rm -rf {} +
```

Expected: command exits 0.

- [ ] **Step 3: Move tracked implementation files**

Run:

```bash
git mv src/htfsd/config.py src/config.py
git mv src/htfsd/types.py src/htfsd_types.py
git mv src/htfsd/benchmarks src/benchmarks
git mv src/htfsd/cli src/cli
git mv src/htfsd/dflash src/dflash
git mv src/htfsd/low_tier src/low_tier
git mv src/htfsd/metrics src/metrics
git mv src/htfsd/runtime src/runtime
git mv src/htfsd/tokenization src/tokenization
git rm src/htfsd/__init__.py
rmdir src/htfsd
```

Expected: `rmdir src/htfsd` exits 0. If it fails, run:

```bash
find src/htfsd -maxdepth 2 -print
```

Only generated ignored files may be removed; do not leave wrapper files under `src/htfsd`.

- [ ] **Step 4: Verify target layout exists**

Run:

```bash
test -f src/config.py
test -f src/htfsd_types.py
test -d src/benchmarks
test -d src/cli
test -d src/dflash
test -d src/low_tier
test -d src/metrics
test -d src/runtime
test -d src/tokenization
test ! -e src/htfsd
test ! -e src/types.py
```

Expected: all commands exit 0.

Do not commit yet. Imports and tooling still reference the old layout until Task 2.

## Task 2: Rewrite Imports And Entrypoints

**Files:**
- Modify: `src/**/*.py`
- Modify: `tests/**/*.py`
- Modify: `pyproject.toml`
- Modify: `pyrightconfig.json`

- [ ] **Step 1: Rewrite implementation imports**

Apply these import replacements in all Python files under `src/`:

```text
from htfsd.benchmarks.  -> from benchmarks.
from htfsd.cli.         -> from cli.
from htfsd.config       -> from config
from htfsd.dflash.      -> from dflash.
from htfsd.low_tier.    -> from low_tier.
from htfsd.metrics.     -> from metrics.
from htfsd.runtime.     -> from runtime.
from htfsd.tokenization. -> from tokenization.
from htfsd.types        -> from htfsd_types
```

Also replace any `import htfsd...` form if found:

```text
import htfsd.benchmarks  -> import benchmarks
import htfsd.cli         -> import cli
import htfsd.config      -> import config
import htfsd.dflash      -> import dflash
import htfsd.low_tier    -> import low_tier
import htfsd.metrics     -> import metrics
import htfsd.runtime     -> import runtime
import htfsd.tokenization -> import tokenization
import htfsd.types       -> import htfsd_types
```

Recommended command for discovery:

```bash
rg -n "from htfsd|import htfsd|htfsd\\.types" src tests
```

Expected before editing: old imports are listed. Expected after editing: no output.

- [ ] **Step 2: Rewrite test imports**

Apply the same replacements in all Python files under `tests/`.

Examples:

```python
from htfsd.low_tier.engine import LowTierEngine
from htfsd.types import TokenResult, VerificationResult
```

become:

```python
from low_tier.engine import LowTierEngine
from htfsd_types import TokenResult, VerificationResult
```

- [ ] **Step 3: Update console script entrypoints**

Modify `pyproject.toml`:

```toml
[project.scripts]
htfsd-generate = "cli.generate:main"
htfsd-benchmark-low = "cli.benchmark_low:main"
htfsd-baseline-e4b = "cli.baseline_e4b:main"
```

Keep the command names unchanged.

- [ ] **Step 4: Ensure top-level modules are packaged**

Modify `pyproject.toml` so setuptools includes top-level modules `config` and `htfsd_types`.

Expected setuptools section:

```toml
[tool.setuptools]
py-modules = ["config", "htfsd_types"]

[tool.setuptools.packages.find]
where = ["src"]
```

Do not change the project distribution name:

```toml
name = "htfsd"
```

- [ ] **Step 5: Update Pyright scope**

Modify `pyrightconfig.json`:

```json
{
  "include": ["src", "tests"],
  "exclude": ["**/__pycache__", ".venv", "build", "dist"],
  "venvPath": ".",
  "venv": ".venv",
  "pythonVersion": "3.11",
  "typeCheckingMode": "basic",
  "reportMissingImports": "warning",
  "reportMissingTypeStubs": "none"
}
```

- [ ] **Step 6: Verify stale import references are gone**

Run:

```bash
rg -n "from htfsd|import htfsd|htfsd\\.types" src tests || true
rg -n "src/htfsd" pyproject.toml pyrightconfig.json src tests || true
test ! -e src/htfsd
test ! -e src/types.py
```

Expected: the `rg` commands print no stale implementation references. The `test` commands exit 0.

- [ ] **Step 7: Run import smoke checks**

Run:

```bash
PYTHONPATH=src python - <<'PY'
from config import load_config
from htfsd_types import GenerateResult
from low_tier.engine import LowTierEngine
from dflash.parser import parse_dflash
from cli.generate import main as generate_main

print(load_config.__name__)
print(GenerateResult.__name__)
print(LowTierEngine.__name__)
print(parse_dflash.__name__)
print(generate_main.__name__)
PY
```

Expected output:

```text
load_config
GenerateResult
LowTierEngine
parse_dflash
main
```

- [ ] **Step 8: Run fast tests**

Run:

```bash
PYTHONPATH=src pytest -m "not gpu and not vllm" -v
```

Expected:

```text
33 passed, 2 deselected
```

The exact pytest duration may vary.

- [ ] **Step 9: Commit layout and import rewrite**

Run:

```bash
git add src tests pyproject.toml pyrightconfig.json
git commit -m "refactor: flatten source layout"
```

Expected: commit succeeds. The untracked `docs/htfsd.md` remains untracked.

## Task 3: Update Lint And Type Gates For Flattened Src

**Files:**
- Modify only if tool output requires it: `src/**/*.py`
- Modify only if tool output requires it: `tests/**/*.py`
- Modify only if tool output requires it: `pyproject.toml`
- Modify only if tool output requires it: `pyrightconfig.json`

- [ ] **Step 1: Run Pyright**

Run:

```bash
pyright
```

Expected: `0 errors, 0 warnings, 0 informations`.

If Pyright reports stale imports or missing source paths, fix only the import/config issue that caused the diagnostic. Do not reintroduce `htfsd.*` imports or `src/htfsd`.

- [ ] **Step 2: Run Pylint on flattened source root**

Run:

```bash
pylint src
```

Expected:

```text
Your code has been rated at 10.00/10
```

If Pylint reports generated/cache files, delete generated files and keep them untracked. If Pylint reports import-order or module-name issues caused by flattening, fix those narrowly.

- [ ] **Step 3: Run tests after lint/type fixes**

Run:

```bash
PYTHONPATH=src pytest -m "not gpu and not vllm" -v
```

Expected:

```text
33 passed, 2 deselected
```

The exact pytest duration may vary.

- [ ] **Step 4: Commit gate fixes if any files changed**

Run:

```bash
git status --short --untracked-files=all
```

If only `docs/htfsd.md` is untracked and no tracked files changed, do not commit.

If tracked files changed for gate fixes, run:

```bash
git add src tests pyproject.toml pyrightconfig.json
git commit -m "chore: update gates for flattened src layout"
```

Expected: commit succeeds only when there are tracked changes.

## Task 4: Final Verification And Scope Audit

**Files:**
- No edits expected.

- [ ] **Step 1: Run required verification gates**

Run:

```bash
PYTHONPATH=src pytest -m "not gpu and not vllm" -v
pyright
pylint src
```

Expected:

```text
33 passed, 2 deselected
0 errors, 0 warnings, 0 informations
Your code has been rated at 10.00/10
```

The exact pytest duration may vary.

- [ ] **Step 2: Run stale-reference and scope audit**

Run:

```bash
rg -n "from htfsd|import htfsd|src/htfsd|htfsd\\.types|High Tier|EAGLE|hidden-state promotion" src tests pyproject.toml pyrightconfig.json || true
```

Expected: no output.

Then run:

```bash
rg -n "htfsd" src tests pyproject.toml pyrightconfig.json || true
```

Expected: allowed output only for:

```text
pyproject.toml:name = "htfsd"
pyproject.toml:py-modules = ["config", "htfsd_types"]
pyproject.toml:htfsd-generate = "cli.generate:main"
pyproject.toml:htfsd-benchmark-low = "cli.benchmark_low:main"
pyproject.toml:htfsd-baseline-e4b = "cli.baseline_e4b:main"
```

No `src/htfsd/` path should exist.

- [ ] **Step 3: Inspect git status and diff**

Run:

```bash
git status --short --untracked-files=all
PLAN_SHA=$(git log -1 --format=%H -- docs/superpowers/plans/2026-05-17-htfsd-full-flatten-src-layout-implementation-plan.md)
git diff --stat "$PLAN_SHA"..HEAD
git diff --check "$PLAN_SHA"..HEAD
```

Expected:

```text
?? docs/htfsd.md
```

or a clean status if the user has handled that file separately. `git diff --check` exits 0.

- [ ] **Step 4: Confirm no behavior refactor slipped in**

Review the final diff:

```bash
PLAN_SHA=$(git log -1 --format=%H -- docs/superpowers/plans/2026-05-17-htfsd-full-flatten-src-layout-implementation-plan.md)
git diff "$PLAN_SHA"..HEAD -- src tests pyproject.toml pyrightconfig.json
```

Confirm:

- Low Tier loop control flow is unchanged except import paths.
- D-Flash parser logic is unchanged except import paths.
- Acceptance/fallback logic is unchanged except import paths.
- Benchmark row shape logic is unchanged except import paths.
- vLLM optional import behavior is unchanged except import paths.
- No High Tier, EAGLE, or hidden-state promotion code was added.

- [ ] **Step 5: Report completion**

Report:

```text
Flattened src layout complete.
Verification:
- PYTHONPATH=src pytest -m "not gpu and not vllm" -v: 33 passed, 2 deselected
- pyright: 0 errors, 0 warnings, 0 informations
- pylint src: 10.00/10
Scope audit: no stale htfsd package imports and no src/htfsd wrapper.
Remaining untracked files: report the exact `git status --short --untracked-files=all` output.
```
