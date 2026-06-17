from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


ARTIFACTS = [
    Path("results/_archives/early_smokes/dflash_r1_n20.jsonl"),
    Path("results/_archives/early_smokes/cc_llm_r2_smoke.jsonl"),
    Path("results/_archives/early_smokes/cc_llm_r3_smoke.jsonl"),
    Path("results/_archives/early_smokes/llmlingua_ar_r2_smoke.jsonl"),
    Path("results/_archives/early_smokes/llmlingua_ar_r3_smoke.jsonl"),
]

COMMON_REQUIRED_FIELDS = [
    "prompt_id",
    "input_tokens",
    "output_tokens",
    "generation_time_s",
    "tok_per_sec",
    "acceptance_lengths",
    "tau_mean",
    "vram_allocated_gib",
    "vram_reserved_gib",
]

COMPRESSION_REQUIRED_FIELDS = [
    "t_compress_ms",
    "R_actual",
    "N_original",
    "N_compressed",
    "keep_rate",
    "compressor_model",
    "question_preserved",
]


@dataclass
class AuditIssue:
    level: str
    message: str


@dataclass
class ArtifactAudit:
    path: Path
    condition: str | None = None
    row_count: int = 0
    issues: list[AuditIssue] = field(default_factory=list)

    @property
    def status(self) -> str:
        levels = {issue.level for issue in self.issues}
        if "FAIL" in levels:
            return "FAIL"
        if "WARN" in levels:
            return "WARN"
        return "PASS"

    def add(self, level: str, message: str) -> None:
        self.issues.append(AuditIssue(level=level, message=message))


def _load_rows(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    failures: list[str] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return [], [f"artifact missing: {path}"]

    for lineno, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            failures.append(f"line {lineno}: invalid JSON ({exc})")
            continue
        if not isinstance(row, dict):
            failures.append(f"line {lineno}: row is not a JSON object")
            continue
        rows.append(row)
    return rows, failures


def _validate_common_fields(audit: ArtifactAudit, row: dict[str, Any], row_index: int) -> None:
    label = f"row {row_index}"
    for field_name in COMMON_REQUIRED_FIELDS:
        if field_name not in row:
            audit.add("FAIL", f"{label}: missing required field `{field_name}`")

    if "acceptance_lengths" in row and not isinstance(row["acceptance_lengths"], list):
        audit.add("FAIL", f"{label}: `acceptance_lengths` must be a list")

    for field_name, minimum, strict in [
        ("input_tokens", 0, True),
        ("output_tokens", 0, False),
        ("generation_time_s", 0, False),
        ("tok_per_sec", 0, False),
        ("tau_mean", 0, False),
    ]:
        value = row.get(field_name)
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            if value is not None:
                audit.add("FAIL", f"{label}: `{field_name}` must be numeric")
            continue
        if strict and value <= minimum:
            audit.add("FAIL", f"{label}: `{field_name}` must be > {minimum}")
        if not strict and value < minimum:
            audit.add("FAIL", f"{label}: `{field_name}` must be >= {minimum}")


def _validate_compression_fields(audit: ArtifactAudit, row: dict[str, Any], row_index: int) -> None:
    label = f"row {row_index}"
    for field_name in COMPRESSION_REQUIRED_FIELDS:
        if field_name not in row:
            audit.add("FAIL", f"{label}: missing compression field `{field_name}`")

    r_actual = row.get("R_actual")
    n_original = row.get("N_original")
    n_compressed = row.get("N_compressed")
    question_preserved = row.get("question_preserved")

    if isinstance(r_actual, (int, float)) and not isinstance(r_actual, bool) and r_actual < 1:
        audit.add("FAIL", f"{label}: `R_actual` must be >= 1")
    if (
        isinstance(n_original, (int, float))
        and isinstance(n_compressed, (int, float))
        and not isinstance(n_original, bool)
        and not isinstance(n_compressed, bool)
    ):
        if n_compressed <= 0:
            audit.add("FAIL", f"{label}: `N_compressed` must be > 0")
        if n_original < n_compressed:
            audit.add("FAIL", f"{label}: `N_original` must be >= `N_compressed`")
    if question_preserved is not True:
        audit.add("FAIL", f"{label}: `question_preserved` must be true")


def _validate_dflash_row(audit: ArtifactAudit, row: dict[str, Any], row_index: int) -> None:
    if row.get("output_tokens", 0) > 0 and not row.get("acceptance_lengths"):
        audit.add("FAIL", f"row {row_index}: DFlash row with output tokens must have non-empty `acceptance_lengths`")


def _validate_cc_llm_row(audit: ArtifactAudit, row: dict[str, Any], row_index: int) -> None:
    _validate_compression_fields(audit, row, row_index)
    if row.get("output_tokens", 0) > 0 and not row.get("acceptance_lengths"):
        audit.add("WARN", f"row {row_index}: CC-LLM row has output tokens but empty `acceptance_lengths`")


def _validate_llmlingua_ar_row(audit: ArtifactAudit, row: dict[str, Any], row_index: int) -> None:
    _validate_compression_fields(audit, row, row_index)
    if row.get("acceptance_lengths") != []:
        audit.add("FAIL", f"row {row_index}: LLMLingua-AR rows must use `acceptance_lengths == []`")
    if row.get("tau_mean") != 0.0:
        audit.add("FAIL", f"row {row_index}: LLMLingua-AR rows must use `tau_mean == 0.0`")
    if "generation_mode" in row and row.get("generation_mode") != "autoregressive":
        audit.add("FAIL", f"row {row_index}: `generation_mode` must be `autoregressive` when present")
    if "draft_used" in row and row.get("draft_used") is not False:
        audit.add("FAIL", f"row {row_index}: `draft_used` must be false when present")


def audit_artifact(path: Path) -> ArtifactAudit:
    audit = ArtifactAudit(path=path)
    rows, failures = _load_rows(path)
    for failure in failures:
        audit.add("FAIL", failure)
    if failures:
        return audit
    if not rows:
        audit.add("FAIL", "artifact contains no JSON rows")
        return audit

    audit.row_count = len(rows)
    conditions = {row.get("condition") for row in rows}
    if len(conditions) != 1:
        audit.add("FAIL", f"mixed or missing conditions: {sorted(conditions, key=str)}")
        return audit

    condition = next(iter(conditions))
    if not isinstance(condition, str):
        audit.add("FAIL", "condition must be a string")
        return audit
    audit.condition = condition

    for row_index, row in enumerate(rows, start=1):
        _validate_common_fields(audit, row, row_index)
        if condition == "DFlash-R1":
            _validate_dflash_row(audit, row, row_index)
        elif condition in {"CC-LLM-R2", "CC-LLM-R3"}:
            _validate_cc_llm_row(audit, row, row_index)
        elif condition in {"LLMLingua-AR-R2", "LLMLingua-AR-R3"}:
            _validate_llmlingua_ar_row(audit, row, row_index)
        else:
            audit.add("WARN", f"row {row_index}: unknown condition `{condition}`")

    return audit


def print_summary(audits: list[ArtifactAudit]) -> None:
    for audit in audits:
        condition = audit.condition or "unknown"
        print(f"{audit.status} {audit.path} condition={condition} rows={audit.row_count} issues={len(audit.issues)}")
        for issue in audit.issues:
            print(f"  {issue.level}: {issue.message}")


def resolve_artifact_paths(paths: list[str] | None = None) -> list[Path]:
    if paths:
        return [Path(path) for path in paths]
    return ARTIFACTS


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit smoke JSONL artifact contracts")
    parser.add_argument(
        "artifacts",
        nargs="*",
        help="Optional artifact paths to audit. Defaults to the Task 23 smoke artifact set.",
    )
    args = parser.parse_args()

    audits = [audit_artifact(path) for path in resolve_artifact_paths(args.artifacts)]
    print_summary(audits)
    if any(audit.status == "FAIL" for audit in audits):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
