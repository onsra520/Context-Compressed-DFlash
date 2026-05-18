# HTFSD Pylance/Pylint Cleanup Design

Date: 2026-05-17

## Scope

This is a pre-merge code-quality gate for the existing HTFSD Phase 0-2 MVP branch. It is not feature work and must not change runtime behavior.

Required gates:

```bash
pytest -m "not gpu and not vllm" -v
pyright
pylint src/htfsd
```

Tooling changes:

- Add `pyright` and `pylint` only to dev dependencies.
- Do not add either tool to runtime dependencies.
- Configure Pyright to check:
  - `src/htfsd`
  - `tests`
- Configure Pylint so the main gate is:
  - `pylint src/htfsd`
- Do not add tests to the primary Pylint gate in this pass.

## Configuration

Use one clear Pyright configuration location. Prefer `pyrightconfig.json` if it keeps the scope more explicit; do not duplicate the same settings in both `pyproject.toml` and `pyrightconfig.json`.

Pylint configuration should be minimal and focused on the package. It may disable low-value docstring noise if needed:

- `missing-module-docstring`
- `missing-class-docstring`
- `missing-function-docstring`

Do not use broad global disables to hide quality issues. Targeted disables are allowed only near the relevant line/module and only when there is a clear reason, such as an optional dependency or dynamic API boundary.

## Allowed Cleanup

Fix only issues reported by Pyright/Pylint or directly required to support their configuration:

- unused imports or variables
- small naming/style issues
- Protocol/`Any`/type narrowing issues
- optional vLLM import typing
- module exports if needed
- docstring policy/config, or meaningful docstrings where useful

For Pyright, prefer type narrowing, Protocols, or local wrappers before using ignores. Use a targeted ignore only when an optional dependency or dynamic API cannot be typed cleanly without making vLLM a hard unit-test dependency.

## Non-Goals

Do not:

- change Low Tier loop semantics
- change D-Flash parser behavior
- change greedy acceptance or fallback policy
- change benchmark output contract
- make optional vLLM a hard requirement for unit tests
- add High Tier, EAGLE, or hidden-state promotion
- expand into a strict typing push beyond what the tools require
- weaken test intent just to satisfy Pyright

## Implementation Shape

1. Add `pyright` and `pylint` to dev dependencies.
2. Add one repo-local Pyright config.
3. Add minimal Pylint config for `src/htfsd`.
4. Install dev tools into the existing worktree `.venv`.
5. Run `pyright` and `pylint src/htfsd` before editing to capture real findings.
6. Apply targeted cleanup only for reported issues.
7. Run the required gates.
8. Run the scope audit:

   ```bash
   rg -n "High Tier|EAGLE|hidden-state promotion|Gemma E4B verification|lossless|speedup" src tests README.md || true
   ```

9. Self-review `git diff` to confirm the pass is tooling/type/lint cleanup only.
10. Commit with:

   ```bash
   git commit -m "chore: add lint and type-check gates"
   ```

## Acceptance Criteria

The pass is complete when:

- `pytest -m "not gpu and not vllm" -v` passes.
- `pyright` passes using repo config.
- `pylint src/htfsd` passes cleanly.
- vLLM remains optional for unit tests.
- No High Tier/EAGLE/hidden-state promotion code is added.
- `git diff` review shows no behavior change to Low Tier, D-Flash, acceptance/fallback, or benchmark output contracts.
