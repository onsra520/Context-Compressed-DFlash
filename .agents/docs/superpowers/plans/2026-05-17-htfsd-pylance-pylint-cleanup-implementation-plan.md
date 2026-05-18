# HTFSD Pylance/Pylint Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add repo-enforced Pyright/Pylint gates and make the existing HTFSD Phase 0-2 package pass them without changing runtime behavior.

**Architecture:** This is a tooling and cleanup pass only. Pyright checks both `src/htfsd` and `tests`; Pylint gates `src/htfsd`. Optional vLLM remains lazy/optional, and cleanup is limited to findings reported by the tools.

**Tech Stack:** Python 3.13 in the current worktree `.venv`, Pyright, Pylint, pytest, PyYAML.

---

## Files

- Modify: `pyproject.toml`
- Create: `pyrightconfig.json`
- Modify as needed after tool output: `src/htfsd/**/*.py`
- Modify as needed after Pyright output: `tests/**/*.py`

Do not create High Tier, EAGLE, or hidden-state promotion files.

## Guardrails

- Do not change Low Tier loop semantics.
- Do not change D-Flash parser behavior.
- Do not change greedy acceptance/fallback policy.
- Do not change benchmark output contract.
- Do not make optional vLLM a hard requirement for unit tests.
- Do not add High Tier, EAGLE, or hidden-state promotion.
- Do not add `pyright` or `pylint` to runtime dependencies.
- Do not add tests to the primary Pylint gate in this pass.

## Task 1: Add Tooling Configuration

**Files:**

- Modify: `pyproject.toml`
- Create: `pyrightconfig.json`

- [ ] **Step 1: Add dev dependencies and Pylint config**

Modify `pyproject.toml` so the dev dependencies and Pylint config look like this:

```toml
[project.optional-dependencies]
dev = [
  "pytest>=8.0",
  "pylint>=3.3",
  "pyright>=1.1",
]
benchmark = ["datasets>=2.19"]

[tool.pylint.main]
py-version = "3.11"
jobs = 0

[tool.pylint.messages_control]
disable = [
  "missing-module-docstring",
  "missing-class-docstring",
  "missing-function-docstring",
]

[tool.pylint.format]
max-line-length = 120
```

Keep existing `[tool.pytest.ini_options]` intact.

- [ ] **Step 2: Add Pyright config**

Create `pyrightconfig.json`:

```json
{
  "include": ["src/htfsd", "tests"],
  "exclude": ["**/__pycache__", ".venv", "build", "dist"],
  "venvPath": ".",
  "venv": ".venv",
  "pythonVersion": "3.11",
  "typeCheckingMode": "basic",
  "reportMissingImports": "warning",
  "reportMissingTypeStubs": "none"
}
```

This keeps Pyright scoped to `src/htfsd` and `tests`, and it avoids making optional vLLM import warnings fatal.

- [ ] **Step 3: Install dev tools into current worktree venv**

Run:

```bash
. .venv/bin/activate
python -m pip install pylint pyright
```

Expected: command exits 0.

- [ ] **Step 4: Run initial tool discovery**

Run:

```bash
. .venv/bin/activate
pyright
pylint src/htfsd
```

Expected: one or both tools may fail. Capture the exact findings and fix only those findings in later tasks.

- [ ] **Step 5: Commit tooling configuration**

If only config/dev dependency changes are present, commit them:

```bash
git add pyproject.toml pyrightconfig.json
git commit -m "chore: add lint and type-check tooling"
```

If tool discovery already forced immediate cleanup edits, include those cleanup files in the later cleanup commit instead of mixing them into this config commit.

## Task 2: Fix Pyright Findings

**Files:**

- Modify based on `pyright` output: `src/htfsd/**/*.py`
- Modify based on `pyright` output: `tests/**/*.py`

- [ ] **Step 1: Run Pyright before editing**

Run:

```bash
. .venv/bin/activate
pyright
```

Expected: if Pyright reports issues, record file paths and line numbers before editing.

- [ ] **Step 2: Apply targeted type cleanup**

Use these rules while editing:

```text
1. Prefer Protocols or local type narrowing over type ignores.
2. Use Any only at dynamic boundaries such as vLLM model handles or tokenizer objects.
3. If a Pyright ignore is unavoidable, put it on the exact line and include a short reason.
4. Do not change test assertions or test intent.
5. Do not change Low Tier, D-Flash, acceptance/fallback, or benchmark behavior.
```

Likely targeted edits:

```python
# For dynamic tokenizer/model boundaries:
from typing import Any, Protocol

# For optional vLLM imports:
try:
    from vllm import LLM, SamplingParams
except Exception:
    LLM = None
    SamplingParams = None
```

If Pyright complains about calling possibly-`None` `SamplingParams` or `LLM`, narrow after `VLLM_AVAILABLE` checks:

```python
if not VLLM_AVAILABLE or LLM is None or SamplingParams is None:
    raise RuntimeError("vLLM is not available in this environment")
```

- [ ] **Step 3: Verify Pyright passes**

Run:

```bash
. .venv/bin/activate
pyright
```

Expected: `0 errors`.

- [ ] **Step 4: Run fast tests after type cleanup**

Run:

```bash
. .venv/bin/activate
PYTHONPATH=src pytest -m "not gpu and not vllm" -v
```

Expected: all selected tests pass.

- [ ] **Step 5: Commit Pyright cleanup**

If files changed, commit:

```bash
git add src tests
git commit -m "chore: satisfy pyright gate"
```

If no files changed because Pyright passed after Task 1 config, do not create an empty commit.

## Task 3: Fix Pylint Findings For `src/htfsd`

**Files:**

- Modify based on `pylint src/htfsd` output: `src/htfsd/**/*.py`
- Modify only if a config adjustment is needed: `pyproject.toml`

- [ ] **Step 1: Run Pylint before editing**

Run:

```bash
. .venv/bin/activate
pylint src/htfsd
```

Expected: if Pylint reports issues, record file paths and message codes before editing.

- [ ] **Step 2: Apply targeted Pylint cleanup**

Use these rules while editing:

```text
1. Fix unused imports, unused variables, naming, line length, and obvious style issues.
2. Keep docstring policy in config instead of adding noisy docstrings everywhere.
3. Targeted disables are allowed only near the specific line/module and must include a reason.
4. Do not add broad global disables for undefined-variable, unused-import, broad-exception-caught, or similar quality warnings.
5. Do not change runtime behavior.
```

If Pylint flags a dynamic optional dependency boundary that cannot be expressed cleanly, use a narrow comment like:

```python
# pylint: disable=import-error  # vLLM is optional and imported lazily for GPU runtime.
```

Use such comments only when needed by actual tool output.

- [ ] **Step 3: Verify Pylint passes**

Run:

```bash
. .venv/bin/activate
pylint src/htfsd
```

Expected: Pylint exits 0.

- [ ] **Step 4: Run fast tests after Pylint cleanup**

Run:

```bash
. .venv/bin/activate
PYTHONPATH=src pytest -m "not gpu and not vllm" -v
```

Expected: all selected tests pass.

- [ ] **Step 5: Commit Pylint cleanup**

If files changed, commit:

```bash
git add src pyproject.toml
git commit -m "chore: satisfy pylint gate"
```

If no files changed because Pylint passed after Task 1 config, do not create an empty commit.

## Task 4: Final Verification And Scope Audit

**Files:**

- No code changes expected unless verification exposes a specific issue.

- [ ] **Step 1: Run required gates**

Run:

```bash
. .venv/bin/activate
PYTHONPATH=src pytest -m "not gpu and not vllm" -v
pyright
pylint src/htfsd
```

Expected:

- pytest selected tests pass.
- Pyright reports 0 errors.
- Pylint exits 0.

- [ ] **Step 2: Run scope audit**

Run:

```bash
rg -n "High Tier|EAGLE|hidden-state promotion|Gemma E4B verification|lossless|speedup" src tests README.md || true
```

Expected: no implementation/test hits that add forbidden MVP surfaces or overclaims.

- [ ] **Step 3: Review diff for behavior changes**

Run:

```bash
git diff HEAD~3..HEAD -- src tests pyproject.toml pyrightconfig.json
```

Review expected:

- tooling config changes are present.
- type/lint cleanup changes are present if tools required them.
- no Low Tier loop semantics change.
- no D-Flash parser behavior change.
- no acceptance/fallback policy change.
- no benchmark output contract change.
- no High Tier/EAGLE/hidden-state promotion code.

- [ ] **Step 4: Check final git status**

Run:

```bash
git status --short
```

Expected: clean worktree. If verification fixes were needed, commit them with:

```bash
git add src tests pyproject.toml pyrightconfig.json
git commit -m "chore: finalize lint and type-check gates"
```

## Self-Review Checklist

- Spec coverage:
  - Dev dependencies are covered by Task 1.
  - Pyright config for `src/htfsd` and `tests` is covered by Task 1.
  - Pylint gate for `src/htfsd` is covered by Task 1 and Task 3.
  - Required gates are covered by Task 4.
  - Scope audit and diff self-review are covered by Task 4.

- Placeholder scan:
  - This plan must not contain empty placeholder markers or vague implementation instructions.
  - Every command has an expected result.
  - Cleanup instructions are constrained by actual tool output.

- Type and behavior consistency:
  - Optional vLLM remains optional.
  - Pyright fixes must prefer Protocol/type narrowing before ignores.
  - Pylint disables must be targeted, not broad global hides.
  - Runtime behavior contracts remain unchanged.
