"""Markdown runtime error reports for CLI commands."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from pprint import pformat
from typing import Any, Sequence

SENSITIVE_FLAGS = ("--prompt", "--token", "--api-key", "--password", "--hf-token")


def write_runtime_error_report(
    *,
    summary: str,
    command: Sequence[str],
    environment: dict[str, Any],
    model_context: dict[str, Any],
    error_message: str,
    traceback_text: str,
    suspected_cause: str,
    proposed_fix: str,
    verification_steps: Sequence[str],
    status: str = "Open",
    log_dir: str | Path = Path("logs/errors"),
) -> Path:
    """Write an agent-readable markdown error report."""

    sensitive_values = _sensitive_values_from_command(command)
    report_dir = Path(log_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    report_path = report_dir / f"{timestamp}-runtime-error.md"
    command_text = redact_text(" ".join(command), sensitive_values=sensitive_values)
    steps = "\n".join(f"- `{redact_text(step, sensitive_values=sensitive_values)}`" for step in verification_steps)

    report_path.write_text(
        "\n".join(
            [
                "# Runtime Error Report",
                "",
                "## Summary",
                redact_text(summary, sensitive_values=sensitive_values),
                "",
                "## Command",
                f"`{command_text}`",
                "",
                "## Environment",
                "```text",
                redact_text(pformat(environment), sensitive_values=sensitive_values),
                "```",
                "",
                "## Model Context",
                "```text",
                redact_text(pformat(model_context), sensitive_values=sensitive_values),
                "```",
                "",
                "## Error Message",
                redact_text(error_message, sensitive_values=sensitive_values),
                "",
                "## Traceback",
                "```text",
                redact_text(traceback_text, sensitive_values=sensitive_values),
                "```",
                "",
                "## Suspected Cause",
                redact_text(suspected_cause, sensitive_values=sensitive_values),
                "",
                "## Proposed Fix",
                redact_text(proposed_fix, sensitive_values=sensitive_values),
                "",
                "## Verification Steps",
                steps,
                "",
                "## Status",
                status,
                "",
            ]
        ),
        encoding="utf-8",
    )
    return report_path


def redact_text(text: str, *, sensitive_values: Sequence[str]) -> str:
    """Redact sensitive values from report text."""

    redacted = text
    for value in sorted({item for item in sensitive_values if item}, key=len, reverse=True):
        redacted = redacted.replace(value, "<redacted>")
    return redacted


def _sensitive_values_from_command(command: Sequence[str]) -> list[str]:
    values: list[str] = []
    index = 0
    while index < len(command):
        item = command[index]
        flag, equals, value = item.partition("=")
        if equals and flag in SENSITIVE_FLAGS:
            values.append(value)
        elif item in SENSITIVE_FLAGS and index + 1 < len(command):
            values.append(command[index + 1])
            index += 1
        index += 1
    return values
