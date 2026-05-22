"""Structured run logging for HTFSD console commands."""

from __future__ import annotations

import json
import subprocess
import sys
import traceback
from datetime import datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from time import perf_counter
from types import TracebackType
from typing import Any, Sequence
from uuid import uuid4

JsonValue = Any
SENSITIVE_VALUE_FLAGS = {"--prompt", "--hf-token", "--token", "--api-key", "--password"}
KNOWN_ARTIFACT_KEYS = {
    "benchmark_output_path",
    "baseline_output_path",
    "debug_trace_path",
    "terminal_log_path",
}


def _is_prompt_flag(flag: str) -> bool:
    return len(flag) > len("--") and "--prompt".startswith(flag)


def _is_sensitive_value_flag(flag: str) -> bool:
    return flag in SENSITIVE_VALUE_FLAGS or _is_prompt_flag(flag)


def sanitize_argv(argv: Sequence[str]) -> dict[str, JsonValue]:
    """Redact CLI values that should not be written to the run log."""

    sanitized: list[str] = []
    prompt_present = False
    prompt_chars: int | None = None
    index = 0
    while index < len(argv):
        item = argv[index]
        flag, equals, value = item.partition("=")
        if equals and _is_sensitive_value_flag(flag):
            sanitized.append(f"{flag}=<redacted>")
            if _is_prompt_flag(flag):
                prompt_present = True
                prompt_chars = len(value)
            index += 1
            continue
        if _is_sensitive_value_flag(item):
            sanitized.append(item)
            next_index = index + 1
            if next_index < len(argv):
                sanitized.append("<redacted>")
                if _is_prompt_flag(item):
                    prompt_present = True
                    prompt_chars = len(argv[next_index])
                index += 2
                continue
        else:
            sanitized.append(item)
        index += 1
    return {
        "sanitized": sanitized,
        "prompt_present": prompt_present,
        "prompt_chars": prompt_chars,
        "prompt_sha256": None,
    }


def _safe_json_value(value: JsonValue) -> JsonValue:
    """Return a JSON value or None when metadata cannot be serialized."""

    try:
        json.dumps(value)
    except (TypeError, ValueError):
        return None
    return value


def _display_path(path: str | Path) -> str:
    """Return a path relative to the current directory when possible."""

    display_path = Path(path)
    if not display_path.is_absolute():
        return str(display_path)
    try:
        return str(display_path.relative_to(Path.cwd()))
    except ValueError:
        return str(display_path)


def _git_commit() -> str | None:
    """Return the current Git commit when the source tree is available."""

    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            check=False,
            text=True,
            timeout=1,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def _vllm_version() -> str | None:
    """Return the installed vLLM distribution version without importing it."""

    try:
        return version("vllm")
    except PackageNotFoundError:
        return None


class RunLogSession:  # pylint: disable=too-many-instance-attributes
    """Collect one structured JSON run log for a CLI invocation."""

    def __init__(
        self,
        command_name: str,
        argv: Sequence[str],
        log_dir: Path = Path("logs/runs"),
    ) -> None:
        self.command_name = command_name
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
            "argv": sanitize_argv(argv),
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
        self.record_metadata(git_commit=_git_commit(), vllm_version=_vllm_version())

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

    def record_cli_args(self, args: Any) -> None:
        """Record paths that become available after argparse succeeds."""

        config_path = getattr(args, "config", None)
        if config_path is not None:
            self._row["paths"]["config_path"] = _display_path(config_path)

    def record_artifact(self, name: str, path: str | Path) -> None:
        """Record a known artifact path created or requested by the command."""

        if name not in KNOWN_ARTIFACT_KEYS:
            raise ValueError(f"unknown artifact key: {name}")
        self._row["paths"][name] = _display_path(path)

    def record_metadata(self, **fields: JsonValue) -> None:
        """Record JSON-compatible runtime metadata without raising on bad fields."""

        runtime = self._row["runtime"]
        runtime.update({name: _safe_json_value(value) for name, value in fields.items()})

    def record_config(self, config: Any, config_path: str | Path) -> None:
        """Record the config metadata used to construct this run."""

        try:
            self._row["paths"]["config_path"] = _display_path(config_path)
        except TypeError:
            pass

        runtime = getattr(config, "runtime", None)
        decoding = getattr(config, "decoding", None)
        self.record_metadata(
            execution_mode=getattr(runtime, "execution_mode", None),
            decoding_mode=getattr(decoding, "default", None),
        )
        models = self._row["models"]
        for name in ("qwen_drafter", "gemma_e2b", "gemma_e4b_baseline"):
            model_id = getattr(getattr(config, name, None), "model_id_or_path", None)
            models[name] = _safe_json_value(model_id)

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

    def _finish(self) -> None:
        ended_at = datetime.now().astimezone()
        self._row["end_time"] = ended_at.isoformat()
        self._row["duration_ms"] = (perf_counter() - self.started_perf) * 1000.0
        try:
            self.log_dir.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self._row, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        except Exception as error:  # pylint: disable=broad-exception-caught
            print(f"warning: failed to write HTFSD run log: {error}", file=sys.stderr)
