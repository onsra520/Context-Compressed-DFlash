# File-Backed CLI Invocation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `htfsd-generate --prompt "Hello"` use `configs/local.yaml` by default and avoid the vLLM-on-WSL `<stdin>` spawn failure by using real console-script or module invocations.

**Architecture:** Keep the fix at the CLI/package workflow boundary. `src/cli/generate.py` owns the default config path and clear pre-model-load error, while run logging continues to record the effective config path. The Low Tier engine, D-Flash parser, verifier, acceptance/fallback policy, benchmark JSONL rows, and generated stdout behavior stay unchanged.

**Tech Stack:** Python 3.11+, argparse, pytest, setuptools console scripts, existing HTFSD CLI run logging.

---

## File Structure

- Modify `src/cli/generate.py`
  - Add `DEFAULT_CONFIG_PATH = "configs/local.yaml"`.
  - Make `--config` optional with that default.
  - Add a small resolver/helper that raises a clear `FileNotFoundError` when the default config is missing before model loading.
  - Keep `main`, `run_single_prompt`, and `run_prompt_loop` behavior otherwise unchanged.
- Modify `tests/test_cli.py`
  - Add no-GPU tests for parser default, explicit config override, missing default config behavior, and run-log effective config path.
  - Use fake engine/config where generation reaches `run_single_prompt`.
- Optionally modify `README.md`
  - Only if implementation chooses to update usage docs.
  - `README.md` is already dirty before this plan; inspect its existing diff first and stage only the intended new hunks.
- Do not modify `LowTierEngine`, D-Flash parser, verifier, benchmark runners, or model adapters for this fix.

## Guardrails

- Do not use heredoc `python - <<'PY'` for any smoke test that initializes vLLM.
- Do not change `LowTierEngine` semantics.
- Do not change D-Flash parser behavior.
- Do not change verifier behavior.
- Do not change greedy acceptance/fallback behavior.
- Do not change benchmark JSONL row shape.
- Do not route Low Tier generation through Gemma E4B.
- Do not add High Tier, EAGLE, or hidden-state promotion.
- Do not stage or overwrite unrelated pre-existing `README.md` edits.

---

### Task 1: Add Generate CLI Default Config Tests

**Files:**
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Add parser/default tests**

Add these tests near the existing generate CLI tests in `tests/test_cli.py`:

```python
def test_generate_parser_defaults_to_local_config():
    args = generate.build_parser().parse_args(["--prompt", "Hello"])

    assert args.config == "configs/local.yaml"
    assert args.prompt == "Hello"


def test_generate_parser_explicit_config_overrides_default():
    args = generate.build_parser().parse_args(
        ["--config", "configs/other.yaml", "--prompt", "Hello"]
    )

    assert args.config == "configs/other.yaml"
```

- [ ] **Step 2: Run the new parser tests and confirm they fail**

Run:

```bash
pytest tests/test_cli.py::test_generate_parser_defaults_to_local_config \
  tests/test_cli.py::test_generate_parser_explicit_config_overrides_default -v
```

Expected:

```text
test_generate_parser_defaults_to_local_config FAILED
test_generate_parser_explicit_config_overrides_default PASSED
```

The first test should fail because `--config` is currently required.

- [ ] **Step 3: Add default run-log and missing-default tests**

Add these tests after `test_generate_main_records_run_log_without_model_output`:

```python
def test_generate_default_config_records_effective_path(tmp_path, monkeypatch, capsys):
    config_path = tmp_path / "configs" / "local.yaml"
    config_path.parent.mkdir(parents=True)
    write_config(config_path)
    monkeypatch.chdir(tmp_path)

    class FakeEngine:
        def generate(self, *_args, **_kwargs):
            return fake_generate_result("generated model output")

    monkeypatch.setattr(generate, "_build_engine", lambda _config: FakeEngine())

    assert generate.main(["--prompt", "private prompt"]) == 0

    assert "generated model output" in capsys.readouterr().out
    log_text = latest_log(tmp_path / "logs" / "runs").read_text(encoding="utf-8")
    row = json.loads(log_text)
    assert row["status"] == "ok"
    assert row["paths"]["config_path"] == "configs/local.yaml"
    assert "private prompt" not in log_text
    assert "generated model output" not in log_text


def test_generate_missing_default_config_fails_before_model_load(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    def fail_if_called(_config):
        raise AssertionError("_build_engine must not be called when default config is missing")

    monkeypatch.setattr(generate, "_build_engine", fail_if_called)

    with pytest.raises(FileNotFoundError, match="configs/local.yaml"):
        generate.main(["--prompt", "private prompt"])

    log_text = latest_log(tmp_path / "logs" / "runs").read_text(encoding="utf-8")
    row = json.loads(log_text)
    assert row["status"] == "error"
    assert row["paths"]["config_path"] == "configs/local.yaml"
    assert row["error"]["exception_type"] == "FileNotFoundError"
    assert "private prompt" not in log_text
```

- [ ] **Step 4: Run the new default-config tests and confirm they fail**

Run:

```bash
pytest tests/test_cli.py::test_generate_default_config_records_effective_path \
  tests/test_cli.py::test_generate_missing_default_config_fails_before_model_load -v
```

Expected:

```text
FAILED
```

The tests should fail because `--config` is required and there is no explicit default missing-file handling yet.

- [ ] **Step 5: Commit the failing tests**

Commit only the test changes:

```bash
git add tests/test_cli.py
git commit -m "test: cover generate default config behavior"
```

---

### Task 2: Implement Generate CLI Default Config

**Files:**
- Modify: `src/cli/generate.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Add the default config constant**

At the top of `src/cli/generate.py`, after imports, add:

```python
DEFAULT_CONFIG_PATH = "configs/local.yaml"
```

- [ ] **Step 2: Make `--config` optional in the parser**

Change `build_parser()` from:

```python
parser.add_argument("--config", required=True)
```

to:

```python
parser.add_argument("--config", default=DEFAULT_CONFIG_PATH)
```

- [ ] **Step 3: Add a default-config resolver**

Add this helper above `_build_engine`:

```python
def resolve_config_path(config_path: str) -> str:
    """Return the effective config path or raise a clear default-config error."""

    path = Path(config_path)
    if path.exists():
        return config_path
    if config_path == DEFAULT_CONFIG_PATH:
        raise FileNotFoundError(
            "Default config configs/local.yaml was not found. "
            "Create it from configs/local.example.yaml or pass --config <path>."
        )
    return config_path
```

This preserves explicit missing-file behavior: if the user passes `--config missing.yaml`, `load_config` raises the normal file error.

- [ ] **Step 4: Use the resolver before config loading**

In `main`, replace:

```python
config = load_config(args.config)
run_log.record_config(config, config_path=args.config)
```

with:

```python
config_path = resolve_config_path(args.config)
config = load_config(config_path)
run_log.record_config(config, config_path=config_path)
```

Leave `run_log.record_cli_args(args)` before this block so the run log still records `configs/local.yaml` when the default is missing.

- [ ] **Step 5: Run focused tests**

Run:

```bash
pytest tests/test_cli.py::test_generate_parser_defaults_to_local_config \
  tests/test_cli.py::test_generate_parser_explicit_config_overrides_default \
  tests/test_cli.py::test_generate_default_config_records_effective_path \
  tests/test_cli.py::test_generate_missing_default_config_fails_before_model_load \
  tests/test_cli.py::test_generate_config_load_failure_still_records_run_log -v
```

Expected:

```text
5 passed
```

- [ ] **Step 6: Commit implementation**

```bash
git add src/cli/generate.py tests/test_cli.py
git commit -m "fix: default generate CLI to local config"
```

---

### Task 3: Verify Packaging Entry Point And File-Backed Invocation

**Files:**
- Modify only if necessary: `pyproject.toml`
- No test file changes expected unless packaging is broken.

- [ ] **Step 1: Inspect current script declaration**

Run:

```bash
grep -n "htfsd-generate\\|project.scripts" pyproject.toml
```

Expected includes:

```text
[project.scripts]
htfsd-generate = "cli.generate:main"
```

- [ ] **Step 2: Install editable package in the active environment**

Run:

```bash
python -m pip install -e .
```

Expected:

```text
Successfully installed htfsd-0.1.0
```

The exact pip wording may differ. The command must exit 0.

- [ ] **Step 3: Verify console script exists**

Run:

```bash
command -v htfsd-generate
htfsd-generate --help
```

Expected:

```text
.../htfsd-generate
usage: htfsd-generate ...
```

The help text should show `--config CONFIG` but it should no longer be listed as required.

- [ ] **Step 4: Verify file-backed module fallback exists**

Run:

```bash
PYTHONPATH=src python -m cli.generate --help
```

Expected:

```text
usage: generate.py ...
```

This command must exit 0 and must not use stdin heredoc.

- [ ] **Step 5: Fix packaging only if needed**

If Step 3 fails because the console script is not installed, inspect editable install output and `pyproject.toml`. Keep any fix minimal. The expected `pyproject.toml` script block is:

```toml
[project.scripts]
htfsd-generate = "cli.generate:main"
htfsd-benchmark-low = "cli.benchmark_low:main"
htfsd-baseline-e4b = "cli.baseline_e4b:main"
```

If packaging already works, do not edit `pyproject.toml`.

- [ ] **Step 6: Commit packaging fix only if there was one**

If `pyproject.toml` changed:

```bash
git add pyproject.toml
git commit -m "fix: expose HTFSD console scripts"
```

If `pyproject.toml` did not change, do not create a commit for this task.

---

### Task 4: Update Usage Docs Without Staging Unrelated README Edits

**Files:**
- Modify: `README.md`
- Modify: `.agents/docs/logs/2026-05-23-low-tier-cli-test.md`

- [ ] **Step 1: Inspect the pre-existing README diff**

Run:

```bash
git diff -- README.md | sed -n '1,220p'
```

Expected:

```text
Existing user edits may already be present.
```

Do not revert or stage unrelated README changes.

- [ ] **Step 2: Update README usage commands minimally**

In the README usage section, change the single-prompt command from:

```bash
htfsd-generate \
  --config configs/local.yaml \
  --prompt "Liệt kê các tỉnh Việt Nam"
```

to:

```bash
htfsd-generate --prompt "Liệt kê các tỉnh Việt Nam"
```

Change interactive mode from:

```bash
htfsd-generate --config configs/local.yaml
```

to:

```bash
htfsd-generate
```

Add this sentence near the usage examples:

```markdown
`htfsd-generate` uses `configs/local.yaml` by default; pass `--config <path>` only when running a different config file.
```

Add this fallback command near the usage examples:

```bash
PYTHONPATH=src python -m cli.generate --prompt "Hello"
```

Make no README changes outside this local usage guidance.

- [ ] **Step 3: Update the incident report resolution**

Append this section to `.agents/docs/logs/2026-05-23-low-tier-cli-test.md` after the current recommendation:

```markdown

## Planned Resolution

- Make `--config` optional for `htfsd-generate`, defaulting to `configs/local.yaml`.
- Use file-backed invocations for vLLM smoke tests:
  - `htfsd-generate --prompt "Hello"`
  - `PYTHONPATH=src python -m cli.generate --prompt "Hello"`
- Do not use stdin heredoc for commands that initialize vLLM under WSL.
```

- [ ] **Step 4: Commit only intended docs hunks**

Because `.agents/` is ignored and `README.md` was dirty before this task, review the diff before staging:

```bash
git diff -- README.md .agents/docs/logs/2026-05-23-low-tier-cli-test.md
```

Stage only intended hunks. If using interactive staging:

```bash
git add -p README.md
git add -f .agents/docs/logs/2026-05-23-low-tier-cli-test.md
git commit -m "docs: document file-backed generate invocation"
```

If the README diff is too tangled to stage safely, skip the README change, commit only the incident report with `git add -f`, and mention the skipped README edit in the final summary.

---

### Task 5: Full Verification And Runtime Smoke

**Files:**
- No source changes expected.
- Generated logs under `logs/` must remain untracked.

- [ ] **Step 1: Run non-GPU unit tests**

Run:

```bash
pytest -m "not gpu and not vllm" -v
```

Expected:

```text
passed
```

- [ ] **Step 2: Run type and lint gates if tools are available**

Run:

```bash
pyright
pylint src
```

Expected:

```text
0 errors
```

If repo policy is still `pylint src/htfsd` from an old layout, use the current flattened layout command that the repo accepts. Do not broaden lint-driven refactors in this fix.

- [ ] **Step 3: Run primary runtime smoke through console script**

Run:

```bash
timeout 600 htfsd-generate --prompt "Hello"
```

Expected:

```text
command exits 0
generated text is printed
metrics JSON is printed
```

If a new vLLM/model/GPU error appears, do not make an unplanned fix. Inspect the newest `logs/runs/*.json`, append the new error to `.agents/docs/logs/2026-05-23-low-tier-cli-test.md`, and stop for review.

- [ ] **Step 4: Run fallback runtime smoke through module invocation**

Run:

```bash
timeout 600 env PYTHONPATH=src python -m cli.generate --prompt "Hello"
```

Expected:

```text
command exits 0
generated text is printed
metrics JSON is printed
```

This command must not use stdin heredoc.

- [ ] **Step 5: Inspect latest run logs for privacy and effective config path**

Run:

```bash
LATEST_LOG=$(find logs/runs -maxdepth 1 -type f -name '*.json' | sort | tail -n 1)
python -m json.tool "$LATEST_LOG" | sed -n '1,180p'
rg -n "Hello|generated model output" "$LATEST_LOG" || true
```

Expected:

```text
"status": "ok"
"exit_code": 0
"config_path": "configs/local.yaml"
no raw prompt text in the run log
```

- [ ] **Step 6: Scope audit**

Run:

```bash
rg -n "python - <<'PY'|LowTierEngine|D-Flash|EAGLE|hidden-state|Gemma E4B" src tests README.md .agents/docs/superpowers/specs/2026-05-23-file-backed-cli-invocation-design.md .agents/docs/logs/2026-05-23-low-tier-cli-test.md
git status --short --untracked-files=all
git diff --stat HEAD
```

Expected:

```text
No new heredoc vLLM smoke instructions.
No source changes outside generate CLI/default config behavior and docs.
logs/ remains untracked/ignored.
```

- [ ] **Step 7: Final commit if verification documentation changed**

If Task 5 appended new runtime findings to the incident report:

```bash
git add -f .agents/docs/logs/2026-05-23-low-tier-cli-test.md
git commit -m "docs: record generate CLI smoke verification"
```

If no files changed in Task 5, do not create an empty commit.

---

## Self-Review Checklist

- Spec coverage:
  - Default `configs/local.yaml` for `htfsd-generate`: Task 1 and Task 2.
  - Explicit `--config` override: Task 1 and Task 2.
  - Clear missing-default failure before model loading: Task 1 and Task 2.
  - Editable install and console script verification: Task 3.
  - File-backed fallback invocation: Task 3 and Task 5.
  - No heredoc vLLM smoke path: Task 4 and Task 5.
  - Run-log effective config path and privacy: Task 1, Task 2, and Task 5.
  - No Low Tier semantic changes: guardrails and scope audit.
- Placeholder scan:
  - No placeholder markers or unspecified edge handling remains.
- Type consistency:
  - `DEFAULT_CONFIG_PATH`, `resolve_config_path`, `build_parser`, and `main` names match the current `src/cli/generate.py` structure.
