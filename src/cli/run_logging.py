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
        except OSError as error:
            print(f"warning: failed to write HTFSD run log: {error}", file=sys.stderr)
