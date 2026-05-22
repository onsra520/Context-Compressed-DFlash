# HTFSD CLI Run Logging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add structured, privacy-aware JSON run logs around HTFSD CLI commands so local failures can be inspected after command exit.

**Architecture:** Keep run logging strictly in the flattened `src/cli` boundary. A shared `RunLogSession` context manager owns schema versioning, timing, status/error capture, argv sanitization, artifact pointers, and best-effort config/runtime metadata; each CLI `main` wraps its existing behavior without changing Low Tier, verifier, benchmark, or stdout contracts.

**Tech Stack:** Python 3.13, argparse, pathlib, JSON, pytest with monkeypatch/fakes, Pyright, Pylint, vLLM version metadata only.

---

## Current Working Tree Notes

Before this plan was written, the checkout already had a dirty README diff from
editable-install/debugging notes:

```text
 M README.md
```

Inspect that diff before editing README during this plan:

```bash
git diff -- README.md
```

Add only the run logging note required by this feature. Do not revert or rewrite
the existing editable-install note unless the user explicitly asks.

`src/htfsd.egg-info/PKG-INFO` may change when running `pip install -e .`.
Treat that as generated package metadata and do not include it accidentally in
run logging commits. Check it before each commit:

```bash
git diff -- src/htfsd.egg-info/PKG-INFO
```

## Files

- Create: `src/cli/run_logging.py`
- Modify: `src/cli/generate.py`
- Modify: `src/cli/benchmark_low.py`
- Modify: `src/cli/baseline_e4b.py`
- Create: `tests/test_run_logging.py`
- Modify: `tests/test_cli.py`
- Modify: `.gitignore`
- Modify minimally: `README.md`

Do not modify:

- `src/low_tier/engine.py`
- `src/dflash/**`
- verifier or acceptance/fallback modules
- benchmark JSONL row shapes
- generated stdout behavior
- High Tier/EAGLE/hidden-state code

Terminal transcript capture remains deferred unless a separate approved task
adds a tested tee implementation. This plan implements structured JSON run logs
only.

## Task 1: Add The RunLogSession Core With Error-Safe JSON Output

**Files:**

- Create: `tests/test_run_logging.py`
- Create: `src/cli/run_logging.py`

- [ ] **Step 1: Write failing session lifecycle tests**

Create `tests/test_run_logging.py` with these first tests:

```python
import json

import pytest

from cli.run_logging import RunLogSession


def read_log(session: RunLogSession) -> dict:
    return json.loads(session.path.read_text(encoding="utf-8"))


def test_run_log_session_writes_success_json(tmp_path):
    with RunLogSession("htfsd-generate", ["--config", "configs/local.yaml"], log_dir=tmp_path) as session:
        assert session.path.parent == tmp_path

    row = read_log(session)
    assert row["schema_version"] == 1
    assert row["command"] == "htfsd-generate"
    assert row["status"] == "ok"
    assert row["exit_code"] == 0
    assert row["error"] is None
    assert row["start_time"]
    assert row["end_time"]
    assert row["duration_ms"] >= 0.0


def test_run_log_session_records_exception_and_reraises(tmp_path):
    with pytest.raises(RuntimeError, match="boom"):
        with RunLogSession("htfsd-generate", [], log_dir=tmp_path) as session:
            raise RuntimeError("boom")

    row = read_log(session)
    assert row["status"] == "error"
    assert row["exit_code"] == 1
    assert row["error"]["exception_type"] == "RuntimeError"
    assert row["error"]["message"] == "boom"
    assert "RuntimeError: boom" in row["error"]["traceback"]
```

- [ ] **Step 2: Run the lifecycle tests to verify RED**

Run:

```bash
PYTHONPATH=src .venv/bin/python -m pytest \
  tests/test_run_logging.py::test_run_log_session_writes_success_json \
  tests/test_run_logging.py::test_run_log_session_records_exception_and_reraises \
  -v
```

Expected: FAIL during collection with `ModuleNotFoundError: No module named 'cli.run_logging'`.

- [ ] **Step 3: Implement the minimal RunLogSession skeleton**

Create `src/cli/run_logging.py`:

```python
"""Structured run logging for HTFSD console commands."""

from __future__ import annotations

import json
import sys
import traceback
from datetime import datetime
from pathlib import Path
from time import perf_counter
from types import TracebackType
from typing import Any, Sequence
from uuid import uuid4

JsonValue = Any


class RunLogSession:  # pylint: disable=too-many-instance-attributes
    """Collect one structured JSON run log for a CLI invocation."""

    def __init__(
        self,
        command_name: str,
        argv: Sequence[str],
        log_dir: Path = Path("logs/runs"),
    ) -> None:
        self.command_name = command_name
        self.argv = list(argv)
        self.log_dir = Path(log_dir)
        self.run_id = uuid4().hex[:8]
        self.started_at = datetime.now().astimezone()
        self.started_perf = perf_counter()
        timestamp = self.started_at.strftime("%Y%m%d-%H%M%S")
        self._path = self.log_dir / f"{timestamp}-{command_name}-{self.run_id}.json"
        self._row: dict[str, JsonValue] = {
            "schema_version": 1,
            "run_id": self.run_id,
            "command": command_name,
            "status": "ok",
            "exit_code": 0,
            "start_time": self.started_at.isoformat(),
            "end_time": None,
            "duration_ms": None,
            "argv": {"sanitized": self.argv, "prompt_present": False, "prompt_chars": None, "prompt_sha256": None},
            "paths": {
                "config_path": None,
                "benchmark_output_path": None,
                "baseline_output_path": None,
                "debug_trace_path": None,
                "terminal_log_path": None,
            },
            "runtime": {},
            "models": {},
            "error": None,
        }

    @property
    def path(self) -> Path:
        """Return the JSON artifact path for this run."""

        return self._path

    def __enter__(self) -> "RunLogSession":
        """Start the logging context."""

        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> bool:
        """Finalize the log while preserving the command exception."""

        if exc_type is not None and exc is not None:
            self._record_exception(exc_type, exc, tb)
        self._finish()
        return False

    def _record_exception(
        self,
        exc_type: type[BaseException],
        exc: BaseException,
        tb: TracebackType | None,
    ) -> None:
        self._row["status"] = "error"
        self._row["exit_code"] = 1
        self._row["error"] = {
            "exception_type": exc_type.__name__,
            "message": str(exc),
            "traceback": "".join(traceback.format_exception(exc_type, exc, tb)),
        }

    def _finish(self) -> None:
        ended_at = datetime.now().astimezone()
        self._row["end_time"] = ended_at.isoformat()
        self._row["duration_ms"] = (perf_counter() - self.started_perf) * 1000.0
        try:
            self.log_dir.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self._row, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        except OSError as error:
            print(f"warning: failed to write HTFSD run log: {error}", file=sys.stderr)
```

This first implementation writes the lifecycle fields only. Later task steps
replace raw argv with sanitizer output and add metadata/artifact methods.

- [ ] **Step 4: Run the lifecycle tests to verify GREEN**

Run:

```bash
PYTHONPATH=src .venv/bin/python -m pytest \
  tests/test_run_logging.py::test_run_log_session_writes_success_json \
  tests/test_run_logging.py::test_run_log_session_records_exception_and_reraises \
  -v
```

Expected: PASS.

- [ ] **Step 5: Add failing `SystemExit` and explicit nonzero status tests**

Append to `tests/test_run_logging.py`:

```python
def test_run_log_session_treats_system_exit_zero_as_ok(tmp_path):
    with pytest.raises(SystemExit) as exit_info:
        with RunLogSession("htfsd-generate", ["--help"], log_dir=tmp_path) as session:
            raise SystemExit(0)

    assert exit_info.value.code == 0
    row = read_log(session)
    assert row["status"] == "ok"
    assert row["exit_code"] == 0
    assert row["error"] is None


def test_run_log_session_records_nonzero_system_exit(tmp_path):
    with pytest.raises(SystemExit) as exit_info:
        with RunLogSession("htfsd-generate", [], log_dir=tmp_path) as session:
            raise SystemExit(2)

    assert exit_info.value.code == 2
    row = read_log(session)
    assert row["status"] == "error"
    assert row["exit_code"] == 2
    assert row["error"]["exception_type"] == "SystemExit"
    assert row["error"]["message"] == "2"


def test_run_log_session_mark_error_for_nonzero_return(tmp_path):
    with RunLogSession("htfsd-generate", [], log_dir=tmp_path) as session:
        session.mark_error("runner returned nonzero", exit_code=7)

    row = read_log(session)
    assert row["status"] == "error"
    assert row["exit_code"] == 7
    assert row["error"]["exception_type"] == "CommandReturnedNonZero"
    assert row["error"]["message"] == "runner returned nonzero"
```

- [ ] **Step 6: Run the status tests to verify RED**

Run:

```bash
PYTHONPATH=src .venv/bin/python -m pytest \
  tests/test_run_logging.py::test_run_log_session_treats_system_exit_zero_as_ok \
  tests/test_run_logging.py::test_run_log_session_records_nonzero_system_exit \
  tests/test_run_logging.py::test_run_log_session_mark_error_for_nonzero_return \
  -v
```

Expected: FAIL because `SystemExit(0)` is treated as error and `mark_error`
does not exist yet.

- [ ] **Step 7: Implement `SystemExit` and `mark_error` semantics**

Update `src/cli/run_logging.py`:

```python
    def mark_error(
        self,
        message: str,
        exception_type: str = "CommandReturnedNonZero",
        exit_code: int = 1,
    ) -> None:
        """Mark a returned nonzero command result as an error."""

        self._row["status"] = "error"
        self._row["exit_code"] = exit_code
        self._row["error"] = {
            "exception_type": exception_type,
            "message": message,
            "traceback": None,
        }
```

Replace `_record_exception` with:

```python
    def _record_exception(
        self,
        exc_type: type[BaseException],
        exc: BaseException,
        tb: TracebackType | None,
    ) -> None:
        if isinstance(exc, SystemExit) and exc.code in (None, 0):
            self._row["status"] = "ok"
            self._row["exit_code"] = 0
            self._row["error"] = None
            return
        exit_code = exc.code if isinstance(exc, SystemExit) and isinstance(exc.code, int) else 1
        self._row["status"] = "error"
        self._row["exit_code"] = exit_code
        self._row["error"] = {
            "exception_type": exc_type.__name__,
            "message": str(exc),
            "traceback": "".join(traceback.format_exception(exc_type, exc, tb)),
        }
```

This keeps traceback capture for nonzero `SystemExit` and ordinary exceptions.

- [ ] **Step 8: Run the full logger test file**

Run:

```bash
PYTHONPATH=src .venv/bin/python -m pytest tests/test_run_logging.py -v
```

Expected: PASS for all logger tests written so far.

- [ ] **Step 9: Commit lifecycle logging**

Check that generated package metadata is not staged:

```bash
git diff -- src/htfsd.egg-info/PKG-INFO
git add src/cli/run_logging.py tests/test_run_logging.py
git commit -m "feat: add CLI run log session"
```

## Task 2: Add Argv Sanitization, Artifact Paths, And Metadata Recording

**Files:**

- Modify: `tests/test_run_logging.py`
- Modify: `src/cli/run_logging.py`

- [ ] **Step 1: Write failing sanitization tests**

Append to `tests/test_run_logging.py`:

```python
@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (["--prompt", "private prompt"], ["--prompt", "<redacted>"]),
        (["--prompt=private prompt"], ["--prompt=<redacted>"]),
    ],
)
def test_run_log_redacts_prompt_forms(tmp_path, argv, expected):
    with RunLogSession("htfsd-generate", argv, log_dir=tmp_path) as session:
        pass

    row = read_log(session)
    assert row["argv"]["sanitized"] == expected
    assert row["argv"]["prompt_present"] is True
    assert row["argv"]["prompt_chars"] == len("private prompt")
    assert "private prompt" not in session.path.read_text(encoding="utf-8")


@pytest.mark.parametrize("flag", ["--hf-token", "--token", "--api-key", "--password"])
def test_run_log_redacts_sensitive_value_flags(tmp_path, flag):
    with RunLogSession("htfsd-generate", [flag, "secret", f"{flag}=also-secret"], log_dir=tmp_path) as session:
        pass

    row = read_log(session)
    assert row["argv"]["sanitized"] == [flag, "<redacted>", f"{flag}=<redacted>"]
    raw = session.path.read_text(encoding="utf-8")
    assert "secret" not in raw
```

- [ ] **Step 2: Run sanitization tests to verify RED**

Run:

```bash
PYTHONPATH=src .venv/bin/python -m pytest \
  tests/test_run_logging.py::test_run_log_redacts_prompt_forms \
  tests/test_run_logging.py::test_run_log_redacts_sensitive_value_flags \
  -v
```

Expected: FAIL because the initial row still stores raw argv.

- [ ] **Step 3: Implement sanitizer helpers**

Add constants and helpers near the top of `src/cli/run_logging.py`:

```python
SENSITIVE_VALUE_FLAGS = {"--prompt", "--hf-token", "--token", "--api-key", "--password"}


def sanitize_argv(argv: Sequence[str]) -> dict[str, JsonValue]:
    """Redact prompt and token-like argv values before writing a run log."""

    sanitized: list[str] = []
    prompt_value: str | None = None
    index = 0
    while index < len(argv):
        item = argv[index]
        flag, separator, value = item.partition("=")
        if separator and flag in SENSITIVE_VALUE_FLAGS:
            sanitized.append(f"{flag}=<redacted>")
            if flag == "--prompt":
                prompt_value = value
            index += 1
            continue
        if item in SENSITIVE_VALUE_FLAGS and index + 1 < len(argv):
            sanitized.extend([item, "<redacted>"])
            if item == "--prompt":
                prompt_value = argv[index + 1]
            index += 2
            continue
        sanitized.append(item)
        index += 1
    return {
        "sanitized": sanitized,
        "prompt_present": prompt_value is not None,
        "prompt_chars": len(prompt_value) if prompt_value is not None else None,
        "prompt_sha256": None,
    }
```

Use it in `RunLogSession.__init__`:

```python
            "argv": sanitize_argv(self.argv),
```

- [ ] **Step 4: Run sanitization tests to verify GREEN**

Run:

```bash
PYTHONPATH=src .venv/bin/python -m pytest \
  tests/test_run_logging.py::test_run_log_redacts_prompt_forms \
  tests/test_run_logging.py::test_run_log_redacts_sensitive_value_flags \
  -v
```

Expected: PASS.

- [ ] **Step 5: Write failing artifact/config/metadata tests**

Add helpers and tests to `tests/test_run_logging.py`:

```python
from argparse import Namespace
from dataclasses import dataclass


@dataclass
class FakeModel:
    model_id_or_path: str


@dataclass
class FakeRuntime:
    execution_mode: str = "concurrent"


@dataclass
class FakeDecoding:
    default: str = "greedy"


@dataclass
class FakeConfig:
    qwen_drafter: FakeModel
    gemma_e2b: FakeModel
    gemma_e4b_baseline: FakeModel
    runtime: FakeRuntime
    decoding: FakeDecoding


def test_run_log_records_known_paths_and_config_metadata(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with RunLogSession("htfsd-benchmark-low", [], log_dir=tmp_path / "logs" / "runs") as session:
        session.record_cli_args(Namespace(config="configs/local.yaml"))
        session.record_artifact("benchmark_output_path", tmp_path / "runs" / "low.jsonl")
        session.record_config(
            FakeConfig(
                FakeModel("qwen-local"),
                FakeModel("e2b-local"),
                FakeModel("e4b-local"),
                FakeRuntime(),
                FakeDecoding(),
            ),
            config_path=tmp_path / "configs" / "local.yaml",
        )

    row = read_log(session)
    assert row["paths"]["config_path"] == "configs/local.yaml"
    assert row["paths"]["benchmark_output_path"] == "runs/low.jsonl"
    assert row["runtime"]["execution_mode"] == "concurrent"
    assert row["runtime"]["decoding_mode"] == "greedy"
    assert row["models"]["gemma_e2b"] == "e2b-local"


def test_run_log_rejects_unknown_artifact_key(tmp_path):
    with RunLogSession("htfsd-generate", [], log_dir=tmp_path) as session:
        with pytest.raises(ValueError, match="unknown artifact key"):
            session.record_artifact("error", "hijack.json")


def test_run_log_metadata_is_best_effort_json(tmp_path):
    with RunLogSession("htfsd-generate", [], log_dir=tmp_path) as session:
        session.record_metadata(fixture_path=object())
        session.record_config(object(), config_path="configs/missing-shape.yaml")

    row = read_log(session)
    assert isinstance(row["runtime"]["fixture_path"], str)
    assert row["paths"]["config_path"] == "configs/missing-shape.yaml"


def test_run_log_records_best_effort_versions(tmp_path, monkeypatch):
    from cli import run_logging

    monkeypatch.setattr(run_logging, "_git_commit", lambda: "abc123")
    monkeypatch.setattr(run_logging, "_vllm_version", lambda: "0.21.0")
    with RunLogSession("htfsd-generate", [], log_dir=tmp_path) as session:
        pass

    row = read_log(session)
    assert row["runtime"]["git_commit"] == "abc123"
    assert row["runtime"]["vllm_version"] == "0.21.0"
```

- [ ] **Step 6: Run metadata tests to verify RED**

Run:

```bash
PYTHONPATH=src .venv/bin/python -m pytest \
  tests/test_run_logging.py::test_run_log_records_known_paths_and_config_metadata \
  tests/test_run_logging.py::test_run_log_rejects_unknown_artifact_key \
  tests/test_run_logging.py::test_run_log_metadata_is_best_effort_json \
  tests/test_run_logging.py::test_run_log_records_best_effort_versions \
  -v
```

Expected: FAIL because `record_cli_args`, `record_artifact`, `record_config`,
and `record_metadata` do not exist yet.

- [ ] **Step 7: Implement path and metadata methods**

Add to `src/cli/run_logging.py`:

```python
from importlib.metadata import PackageNotFoundError, version
from subprocess import CalledProcessError, run

KNOWN_ARTIFACT_KEYS = {
    "benchmark_output_path",
    "baseline_output_path",
    "debug_trace_path",
    "terminal_log_path",
}


def _safe_json_value(value: JsonValue) -> JsonValue:
    try:
        json.dumps(value)
    except (TypeError, ValueError):
        return str(value)
    return value


def _display_path(path: str | Path | None) -> str | None:
    if path is None:
        return None
    candidate = Path(path)
    try:
        return candidate.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return candidate.as_posix()


def _git_commit() -> str | None:
    try:
        result = run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (CalledProcessError, OSError):
        return None
    return result.stdout.strip() or None


def _vllm_version() -> str | None:
    try:
        return version("vllm")
    except PackageNotFoundError:
        return None
```

Add the public methods:

```python
    def record_cli_args(self, args: Any) -> None:
        """Record known CLI path fields after argparse succeeds."""

        config_path = getattr(args, "config", None)
        if config_path is not None:
            self._row["paths"]["config_path"] = _display_path(config_path)

    def record_artifact(self, name: str, path: str | Path | None) -> None:
        """Record a known artifact pointer without copying artifact contents."""

        if name not in KNOWN_ARTIFACT_KEYS:
            raise ValueError(f"unknown artifact key: {name}")
        self._row["paths"][name] = _display_path(path)

    def record_metadata(self, **fields: JsonValue) -> None:
        """Record best-effort runtime metadata values."""

        self._row["runtime"].update({name: _safe_json_value(value) for name, value in fields.items()})

    def record_config(self, config: Any, config_path: str | Path) -> None:
        """Record config-derived runtime and model metadata best-effort."""

        self._row["paths"]["config_path"] = _display_path(config_path)
        runtime = getattr(config, "runtime", None)
        decoding = getattr(config, "decoding", None)
        self.record_metadata(
            execution_mode=getattr(runtime, "execution_mode", None),
            decoding_mode=getattr(decoding, "default", None),
        )
        for key in ("qwen_drafter", "gemma_e2b", "gemma_e4b_baseline"):
            model = getattr(config, key, None)
            value = getattr(model, "model_id_or_path", None)
            if value is not None:
                self._row["models"][key] = _safe_json_value(value)
```

Initialize `runtime` in `RunLogSession.__init__` with the version metadata:

```python
            "runtime": {"git_commit": _git_commit(), "vllm_version": _vllm_version()},
```

Use `importlib.metadata` only; do not import vLLM just to get its version.

- [ ] **Step 8: Run full logger tests and quality check for the new module**

Run:

```bash
PYTHONPATH=src .venv/bin/python -m pytest tests/test_run_logging.py -v
.venv/bin/python -m pyright
.venv/bin/python -m pylint src/cli/run_logging.py
```

Expected: tests pass, Pyright reports 0 errors, Pylint reports a passing score.

- [ ] **Step 9: Commit sanitizer and metadata support**

Run:

```bash
git diff -- src/htfsd.egg-info/PKG-INFO
git add src/cli/run_logging.py tests/test_run_logging.py
git commit -m "feat: add run log metadata and sanitization"
```

## Task 3: Integrate Run Logs Around `htfsd-generate`

**Files:**

- Modify: `tests/test_cli.py`
- Modify: `src/cli/generate.py`

- [ ] **Step 1: Write failing generate integration tests**

Add these imports to `tests/test_cli.py`:

```python
from pathlib import Path

import pytest
```

Add fake result/config helpers:

```python
from htfsd_types import GenerateResult, GenerationMetrics


def fake_metrics() -> GenerationMetrics:
    return GenerationMetrics(
        generated_tokens=1,
        cycles=1,
        drafted_candidate_tokens=1,
        accepted_tokens=1,
        fallback_tokens=0,
        malformed_dflash_count=0,
        dflash_parse_fail_count=0,
        dflash_schema_invalid_count=0,
        dflash_empty_draft_count=0,
        retokenized_empty_count=0,
        low_acceptance_rate=1.0,
        fallback_rate=0.0,
        total_ms=1.0,
        tokens_per_second=1000.0,
        latency_per_token_ms=1.0,
        execution_mode="concurrent",
        decoding_mode="greedy",
    )


class FakeGenerateEngine:
    def generate(self, prompt, **_kwargs):
        assert prompt == "private prompt"
        return GenerateResult(text="MODEL OUTPUT", token_ids=[1], metrics=fake_metrics())


CLI_CONFIG_YAML = """
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
"""
```

Add the integration tests:

```python
def latest_log(log_dir: Path) -> dict:
    log_file = next(log_dir.glob("*.json"))
    return json.loads(log_file.read_text(encoding="utf-8"))


def test_generate_main_records_run_log_without_model_output(tmp_path, monkeypatch, capsys):
    from cli import generate

    config_path = tmp_path / "local.yaml"
    config_path.write_text(CLI_CONFIG_YAML, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(generate, "_build_engine", lambda _config: FakeGenerateEngine())

    exit_code = generate.main(["--config", str(config_path), "--prompt", "private prompt"])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "MODEL OUTPUT" in captured.out
    row = latest_log(tmp_path / "logs" / "runs")
    raw_log = json.dumps(row, ensure_ascii=False)
    assert row["status"] == "ok"
    assert row["paths"]["config_path"] == "local.yaml"
    assert row["argv"]["prompt_chars"] == len("private prompt")
    assert "private prompt" not in raw_log
    assert "MODEL OUTPUT" not in raw_log


def test_generate_config_load_failure_still_records_run_log(tmp_path, monkeypatch):
    from cli import generate

    monkeypatch.chdir(tmp_path)
    with pytest.raises(FileNotFoundError):
        generate.main(["--config", "missing.yaml", "--prompt=private prompt"])

    row = latest_log(tmp_path / "logs" / "runs")
    assert row["status"] == "error"
    assert row["error"]["exception_type"] == "FileNotFoundError"
    assert row["paths"]["config_path"] == "missing.yaml"
```

- [ ] **Step 2: Run generate integration tests to verify RED**

Run:

```bash
PYTHONPATH=src .venv/bin/python -m pytest \
  tests/test_cli.py::test_generate_main_records_run_log_without_model_output \
  tests/test_cli.py::test_generate_config_load_failure_still_records_run_log \
  -v
```

Expected: FAIL because `generate.main` does not create `logs/runs/*.json` yet.

- [ ] **Step 3: Refactor generate CLI so logging wraps parse/config/runtime**

Modify `src/cli/generate.py`:

```python
import sys
```

and:

```python
from cli.run_logging import RunLogSession
```

Split the current load/run body so config loading happens in the logged path:

```python
def run_single_prompt(args: argparse.Namespace, *, config=None) -> int:
    """Run one prompt through the Low Tier generation path."""

    config = config or load_config(args.config)
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
```

Wrap `main`:

```python
def main(argv: list[str] | None = None) -> int:
    """Run the generate CLI."""

    command_argv = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    with RunLogSession("htfsd-generate", command_argv) as run_log:
        args = parser.parse_args(command_argv)
        run_log.record_cli_args(args)
        if args.debug_trace:
            run_log.record_artifact("debug_trace_path", args.debug_trace)
        config = load_config(args.config)
        run_log.record_config(config, config_path=args.config)
        run_log.record_metadata(decoding_mode=args.decoding or config.decoding.default)
        if args.prompt:
            return run_single_prompt(args, config=config)
        return run_prompt_loop(args)
```

Preserve `run_prompt_loop` behavior. It may call `run_single_prompt(args)` for
later prompts as it does today; the initial CLI invocation log covers the prompt
loop session and must not inject generated text into JSON.

- [ ] **Step 4: Run generate tests to verify GREEN**

Run:

```bash
PYTHONPATH=src .venv/bin/python -m pytest \
  tests/test_cli.py::test_generate_main_records_run_log_without_model_output \
  tests/test_cli.py::test_generate_config_load_failure_still_records_run_log \
  tests/test_cli.py::test_write_trace_jsonl \
  -v
```

Expected: PASS.

- [ ] **Step 5: Commit generate integration**

Run:

```bash
git diff -- src/htfsd.egg-info/PKG-INFO
git add src/cli/generate.py tests/test_cli.py
git commit -m "feat: log generate CLI runs"
```

## Task 4: Integrate Benchmark And Baseline CLI Commands

**Files:**

- Modify: `tests/test_cli.py`
- Modify: `src/cli/benchmark_low.py`
- Modify: `src/cli/baseline_e4b.py`

- [ ] **Step 1: Write failing benchmark/baseline integration tests**

Append to `tests/test_cli.py`:

```python
def test_benchmark_low_records_output_pointer(tmp_path, monkeypatch):
    from cli import benchmark_low

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(benchmark_low, "validate_benchmark_decoding", lambda _decoding: None)
    monkeypatch.setattr(benchmark_low, "load_config", lambda _path: object())
    monkeypatch.setattr(benchmark_low, "_build_engine", lambda _config: object())
    monkeypatch.setattr(benchmark_low, "run_low_tier_benchmark", lambda **_kwargs: None)

    output = tmp_path / "runs" / "low.jsonl"
    assert benchmark_low.main(
        ["--config", "configs/local.yaml", "--fixtures", "fixtures.jsonl", "--output", str(output)]
    ) == 0

    row = latest_log(tmp_path / "logs" / "runs")
    assert row["status"] == "ok"
    assert row["paths"]["benchmark_output_path"] == "runs/low.jsonl"


def test_baseline_records_output_pointer(tmp_path, monkeypatch):
    from cli import baseline_e4b

    class FakeHandle:
        def load(self):
            return type("FakeLlm", (), {"get_tokenizer": lambda self: object()})()

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(baseline_e4b, "load_config", lambda _path: type("Cfg", (), {"gemma_e4b_baseline": object()})())
    monkeypatch.setattr(baseline_e4b.VllmModelHandle, "from_config", lambda _config: FakeHandle())
    monkeypatch.setattr(baseline_e4b, "VllmGenerationAdapter", lambda _handle: object())
    monkeypatch.setattr(baseline_e4b, "run_e4b_baseline", lambda **_kwargs: None)

    output = tmp_path / "runs" / "baseline.jsonl"
    assert baseline_e4b.main(
        ["--config", "configs/local.yaml", "--fixtures", "fixtures.jsonl", "--output", str(output)]
    ) == 0

    row = latest_log(tmp_path / "logs" / "runs")
    assert row["status"] == "ok"
    assert row["paths"]["baseline_output_path"] == "runs/baseline.jsonl"
```

If Pylint dislikes inline fake classes, replace them with small module-level fake
classes in `tests/test_cli.py`; do not use a real vLLM handle.

- [ ] **Step 2: Run benchmark/baseline tests to verify RED**

Run:

```bash
PYTHONPATH=src .venv/bin/python -m pytest \
  tests/test_cli.py::test_benchmark_low_records_output_pointer \
  tests/test_cli.py::test_baseline_records_output_pointer \
  -v
```

Expected: FAIL because those CLIs do not create run logs yet.

- [ ] **Step 3: Wrap benchmark-low main**

Modify `src/cli/benchmark_low.py`:

```python
import sys

from cli.run_logging import RunLogSession
```

Replace `main` with:

```python
def main(argv: list[str] | None = None) -> int:
    """Run the Low Tier benchmark CLI."""

    command_argv = list(sys.argv[1:] if argv is None else argv)
    with RunLogSession("htfsd-benchmark-low", command_argv) as run_log:
        args = build_parser().parse_args(command_argv)
        run_log.record_cli_args(args)
        run_log.record_artifact("benchmark_output_path", args.output)
        run_log.record_metadata(decoding_mode=args.decoding, fixture_path=args.fixtures)
        validate_benchmark_decoding(args.decoding)
        config = load_config(args.config)
        run_log.record_config(config, config_path=args.config)
        engine = _build_engine(config)
        run_low_tier_benchmark(
            engine=engine,
            fixture_path=args.fixtures or config.benchmark.fixture_path,
            output_path=args.output,
            decoding=args.decoding,
        )
        return 0
```

- [ ] **Step 4: Wrap baseline-e4b main**

Modify `src/cli/baseline_e4b.py`:

```python
import sys

from cli.run_logging import RunLogSession
```

Replace `main` with:

```python
def main(argv: list[str] | None = None) -> int:
    """Run the Gemma E4B baseline CLI."""

    command_argv = list(sys.argv[1:] if argv is None else argv)
    with RunLogSession("htfsd-baseline-e4b", command_argv) as run_log:
        args = build_parser().parse_args(command_argv)
        run_log.record_cli_args(args)
        run_log.record_artifact("baseline_output_path", args.output)
        run_log.record_metadata(fixture_path=args.fixtures)
        config = load_config(args.config)
        run_log.record_config(config, config_path=args.config)
        handle = VllmModelHandle.from_config(config.gemma_e4b_baseline)
        llm = handle.load()
        run_e4b_baseline(
            generation_adapter=VllmGenerationAdapter(handle),
            tokenizer=llm.get_tokenizer(),
            fixture_path=args.fixtures or config.benchmark.fixture_path,
            output_path=args.output,
        )
        return 0
```

- [ ] **Step 5: Run CLI integration tests**

Run:

```bash
PYTHONPATH=src .venv/bin/python -m pytest tests/test_cli.py -v
```

Expected: existing CLI JSONL shape tests and new run logging integration tests
all pass without vLLM model loading.

- [ ] **Step 6: Commit benchmark/baseline integration**

Run:

```bash
git diff -- src/htfsd.egg-info/PKG-INFO
git add src/cli/benchmark_low.py src/cli/baseline_e4b.py tests/test_cli.py
git commit -m "feat: log benchmark CLI runs"
```

## Task 5: Add Log Hygiene And Minimal README Guidance

**Files:**

- Modify: `.gitignore`
- Modify minimally: `README.md`

- [ ] **Step 1: Inspect existing README diff before editing**

Run:

```bash
git diff -- README.md
```

Expected: the existing diff mentions editable installs and `.venv/bin/python -m`
gate commands. Keep those changes intact and add only run logging docs.

- [ ] **Step 2: Ignore generated run logs**

Add this near the other log-related ignore patterns in `.gitignore`:

```gitignore
# HTFSD generated CLI run logs
logs/
```

Keep existing `[Ll]og/`, `[Ll]ogs/`, and `*.log` patterns unchanged.

- [ ] **Step 3: Add the README run log note**

Add a short section after `## Usage` or before `## Benchmarking`:

```markdown
## Run Logs

Each HTFSD CLI invocation writes a structured JSON run log under
`logs/runs/*.json`. The run log stores command metadata, timing, artifact
pointers, runtime/config metadata when available, and traceback/error details
when a CLI run fails.

Raw `--prompt` text and generated model output are not stored in run logs by
default. Benchmark JSONL and `--debug-trace` JSONL stay as separate artifacts;
the run log only points to their paths.
```

Add `- [Run Logs](#run-logs)` to the README table of contents. Do not document a
terminal transcript flag because this plan does not implement one.

- [ ] **Step 4: Verify git ignores a sample generated log**

Run:

```bash
mkdir -p logs/runs
printf '{}\n' > logs/runs/ignored-check.json
git check-ignore -v logs/runs/ignored-check.json
```

Expected: output names the new `logs/` ignore rule.

- [ ] **Step 5: Commit hygiene/docs without package metadata**

Run:

```bash
git diff -- src/htfsd.egg-info/PKG-INFO
git add .gitignore README.md
git commit -m "docs: describe CLI run logs"
```

Only include README in this commit after checking that its pre-existing dirty
diff is intended to travel with this docs update. If the user wants the earlier
README note separated instead, stop and split the README work before committing.

## Task 6: Final Verification And Scope Audit

**Files:**

- Review only: `src/cli/run_logging.py`
- Review only: `src/cli/generate.py`
- Review only: `src/cli/benchmark_low.py`
- Review only: `src/cli/baseline_e4b.py`
- Review only: `tests/test_run_logging.py`
- Review only: `tests/test_cli.py`
- Review only: `.gitignore`
- Review only: `README.md`

- [ ] **Step 1: Run the required CPU/local test gate**

Run:

```bash
PYTHONPATH=src .venv/bin/python -m pytest -m "not gpu and not vllm" -v
```

Expected: all selected tests pass without GPU/model loading.

- [ ] **Step 2: Run type and lint gates**

Run:

```bash
.venv/bin/python -m pyright
.venv/bin/python -m pylint src
```

Expected: Pyright reports 0 errors and Pylint passes for `src`.

- [ ] **Step 3: Smoke the CLI entrypoint without model loading**

Run:

```bash
htfsd-generate --help
```

Expected: argparse help prints and exits 0. Under the chosen help policy, a
structured run log may be written with ok/0 status; it must not be an error log.

- [ ] **Step 4: Inspect run log privacy and artifact contract with repo search**

Run:

```bash
rg -n "LowTierEngine|parse_dflash|verify_greedy_prefix|benchmark_error_row|terminal-log|EAGLE|hidden-state" \
  src/cli/run_logging.py src/cli/generate.py src/cli/benchmark_low.py src/cli/baseline_e4b.py tests/test_run_logging.py tests/test_cli.py || true
```

Expected:

- `run_logging.py` does not import `LowTierEngine`, parser, verifier, or
  benchmark row writers.
- no terminal transcript flag appears in implementation.
- no High Tier/EAGLE/hidden-state feature code appears.

- [ ] **Step 5: Self-review git diff and generated metadata**

Run:

```bash
git status --short --untracked-files=all
git diff --stat
git diff -- src/cli/run_logging.py src/cli/generate.py src/cli/benchmark_low.py src/cli/baseline_e4b.py \
  tests/test_run_logging.py tests/test_cli.py .gitignore README.md
git diff -- src/htfsd.egg-info/PKG-INFO
```

Expected:

- code changes stay in the CLI run logging boundary and tests/docs/hygiene
- Low Tier/parser/verifier/benchmark row-shape files are unchanged
- generated `logs/` artifacts are ignored
- package metadata diff is either absent or explicitly excluded from commits
