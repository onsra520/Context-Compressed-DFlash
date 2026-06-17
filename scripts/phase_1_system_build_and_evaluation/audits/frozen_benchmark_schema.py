from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


FROZEN_CONDITIONS = {"Baseline-AR", "DFlash-R1", "LLMLingua-AR-R2", "CC-LLM-R2"}
WATCHLIST_CONDITIONS = {"CC-LLM-R3"}
AR_CONDITIONS = {"Baseline-AR", "LLMLingua-AR-R2"}
COMPRESSION_CONDITIONS = {"LLMLingua-AR-R2", "CC-LLM-R2", "CC-LLM-R3"}
DRAFT_CONDITIONS = {"DFlash-R1", "CC-LLM-R2", "CC-LLM-R3"}

COMMON_REQUIRED_FIELDS = [
    "timestamp",
    "condition",
    "prompt_id",
    "prompt_hash",
    "input_tokens",
    "output_tokens",
    "generation_time_s",
    "tok_per_sec",
    "acceptance_lengths",
    "tau_mean",
    "t_prefill_ms",
    "t_prefill_mode",
    "prefill_vram_allocated_gib",
    "prefill_vram_reserved_gib",
    "max_new_tokens",
    "block_size",
    "device",
    "target_path",
    "draft_path",
    "tokenizer_path",
    "backend_warning",
    "vram_allocated_gib",
    "vram_reserved_gib",
    "generated_text",
    "generated_token_count",
    "prompt_source",
    "domain",
    "expected_answer",
    "evidence",
    "approximate_context_words",
    "approximate_context_tokens",
    "t_compress_ms",
    "R_actual",
    "N_original",
    "N_compressed",
    "keep_rate",
    "compressor_model",
    "question_preserved",
    "generation_mode",
    "draft_used",
]

DATASET_ID_FIELDS = ["dataset_id", "fixture_id", "id"]
NULLABLE_FIELDS = {
    "prefill_vram_allocated_gib",
    "prefill_vram_reserved_gib",
    "draft_path",
    "block_size",
    "approximate_context_words",
    "approximate_context_tokens",
    "t_compress_ms",
    "R_actual",
    "N_original",
    "N_compressed",
    "keep_rate",
    "compressor_model",
    "question_preserved",
}


@dataclass
class AuditIssue:
    level: str
    message: str


@dataclass
class FrozenSchemaAudit:
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
    errors: list[str] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return rows, [f"artifact missing: {path}"]

    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"line {line_number}: invalid JSON ({exc})")
            continue
        if not isinstance(row, dict):
            errors.append(f"line {line_number}: row must be a JSON object")
            continue
        rows.append(row)
    return rows, errors


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _require_string(audit: FrozenSchemaAudit, row: dict[str, Any], row_index: int, field_name: str) -> None:
    value = row.get(field_name)
    if not isinstance(value, str) or not value.strip():
        audit.add("FAIL", f"row {row_index}: `{field_name}` must be a non-empty string")


def _require_number(
    audit: FrozenSchemaAudit,
    row: dict[str, Any],
    row_index: int,
    field_name: str,
    *,
    minimum: float | None = None,
    strict: bool = False,
    nullable: bool = False,
) -> None:
    value = row.get(field_name)
    if value is None and nullable:
        return
    if not _is_number(value):
        audit.add("FAIL", f"row {row_index}: `{field_name}` must be numeric" + (" or null" if nullable else ""))
        return
    if minimum is None:
        return
    if strict and value <= minimum:
        audit.add("FAIL", f"row {row_index}: `{field_name}` must be > {minimum:g}")
    elif not strict and value < minimum:
        audit.add("FAIL", f"row {row_index}: `{field_name}` must be >= {minimum:g}")


def _validate_common(audit: FrozenSchemaAudit, row: dict[str, Any], row_index: int) -> None:
    for field_name in COMMON_REQUIRED_FIELDS:
        if field_name not in row:
            audit.add("FAIL", f"row {row_index}: missing required field `{field_name}`")

    if not any(field_name in row for field_name in DATASET_ID_FIELDS):
        audit.add("FAIL", f"row {row_index}: missing dataset identifier field, expected one of {DATASET_ID_FIELDS}")

    for field_name in ["timestamp", "condition", "prompt_hash", "device", "target_path", "tokenizer_path", "backend_warning", "prompt_source", "domain", "expected_answer", "evidence", "generation_mode"]:
        if field_name in row:
            _require_string(audit, row, row_index, field_name)

    if "generated_text" in row:
        _require_string(audit, row, row_index, "generated_text")

    for field_name, minimum, strict in [
        ("prompt_id", 0, True),
        ("input_tokens", 0, True),
        ("output_tokens", 0, False),
        ("generation_time_s", 0, False),
        ("tok_per_sec", 0, False),
        ("tau_mean", 0, False),
        ("t_prefill_ms", 0, False),
        ("max_new_tokens", 128, False),
        ("vram_allocated_gib", 0, False),
        ("vram_reserved_gib", 0, False),
        ("generated_token_count", 0, False),
    ]:
        if field_name in row:
            _require_number(audit, row, row_index, field_name, minimum=minimum, strict=strict)

    for field_name in ["prefill_vram_allocated_gib", "prefill_vram_reserved_gib", "approximate_context_words", "approximate_context_tokens"]:
        if field_name in row:
            _require_number(audit, row, row_index, field_name, minimum=0, nullable=True)

    if "acceptance_lengths" in row and not isinstance(row["acceptance_lengths"], list):
        audit.add("FAIL", f"row {row_index}: `acceptance_lengths` must be a list")
    if "draft_used" in row and not isinstance(row.get("draft_used"), bool):
        audit.add("FAIL", f"row {row_index}: `draft_used` must be boolean")
    if "t_prefill_mode" in row and row.get("t_prefill_mode") not in {"cuda_synchronized", "cpu_timer", "not_measured"}:
        audit.add("FAIL", f"row {row_index}: `t_prefill_mode` has unsupported value `{row.get('t_prefill_mode')}`")


def _validate_no_missing_nullable_fields(audit: FrozenSchemaAudit, row: dict[str, Any], row_index: int) -> None:
    for field_name in NULLABLE_FIELDS:
        if field_name not in row:
            audit.add("FAIL", f"row {row_index}: nullable field `{field_name}` must be present")


def _validate_no_compression_row(audit: FrozenSchemaAudit, row: dict[str, Any], row_index: int) -> None:
    for field_name in ["t_compress_ms", "R_actual", "N_original", "N_compressed", "keep_rate", "compressor_model", "question_preserved"]:
        if field_name in row and row[field_name] is not None:
            audit.add("FAIL", f"row {row_index}: `{field_name}` must be null for no-compression condition")


def _validate_compression_row(audit: FrozenSchemaAudit, row: dict[str, Any], row_index: int) -> None:
    for field_name in ["t_compress_ms", "R_actual", "N_original", "N_compressed", "keep_rate"]:
        if field_name in row:
            _require_number(audit, row, row_index, field_name, minimum=0 if field_name != "R_actual" else 1)
    if _is_number(row.get("N_original")) and _is_number(row.get("N_compressed")):
        if row["N_compressed"] <= 0:
            audit.add("FAIL", f"row {row_index}: `N_compressed` must be > 0")
        if row["N_original"] < row["N_compressed"]:
            audit.add("FAIL", f"row {row_index}: `N_original` must be >= `N_compressed`")
    _require_string(audit, row, row_index, "compressor_model")
    if row.get("question_preserved") is not True:
        audit.add("FAIL", f"row {row_index}: `question_preserved` must be true for compression condition")


def _validate_condition(audit: FrozenSchemaAudit, row: dict[str, Any], row_index: int, condition: str) -> None:
    if condition in AR_CONDITIONS:
        if row.get("acceptance_lengths") != []:
            audit.add("FAIL", f"row {row_index}: AR condition must use `acceptance_lengths == []`")
        if row.get("tau_mean") != 0.0:
            audit.add("FAIL", f"row {row_index}: AR condition must use `tau_mean == 0.0`")
        if row.get("generation_mode") != "autoregressive":
            audit.add("FAIL", f"row {row_index}: AR condition must use `generation_mode == autoregressive`")
        if row.get("draft_used") is not False:
            audit.add("FAIL", f"row {row_index}: AR condition must use `draft_used == false`")
        if row.get("draft_path") is not None:
            audit.add("FAIL", f"row {row_index}: AR condition must use `draft_path == null`")
    else:
        if row.get("output_tokens", 0) > 0 and not row.get("acceptance_lengths"):
            audit.add("FAIL", f"row {row_index}: DFlash/CC row with output tokens must have non-empty `acceptance_lengths`")
        if row.get("draft_used") is not True:
            audit.add("FAIL", f"row {row_index}: DFlash/CC condition must use `draft_used == true`")
        _require_string(audit, row, row_index, "draft_path")

    if condition in COMPRESSION_CONDITIONS:
        _validate_compression_row(audit, row, row_index)
    else:
        _validate_no_compression_row(audit, row, row_index)


def audit_artifact(path: Path) -> FrozenSchemaAudit:
    audit = FrozenSchemaAudit(path=path)
    rows, errors = _load_rows(path)
    for error in errors:
        audit.add("FAIL", error)
    if errors:
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
    if condition not in FROZEN_CONDITIONS:
        level = "WARN" if condition in WATCHLIST_CONDITIONS else "FAIL"
        audit.add(level, f"condition `{condition}` is not in the frozen Task 44 matrix")

    for row_index, row in enumerate(rows, start=1):
        _validate_common(audit, row, row_index)
        _validate_no_missing_nullable_fields(audit, row, row_index)
        _validate_condition(audit, row, row_index, condition)

    return audit


def print_summary(audits: list[FrozenSchemaAudit]) -> None:
    for audit in audits:
        condition = audit.condition or "unknown"
        print(f"{audit.status} {audit.path} condition={condition} rows={audit.row_count} issues={len(audit.issues)}")
        for issue in audit.issues:
            print(f"  {issue.level}: {issue.message}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit benchmark JSONL artifacts against the frozen Task 44 schema")
    parser.add_argument("artifacts", nargs="+", help="Benchmark JSONL artifacts to audit")
    args = parser.parse_args()

    audits = [audit_artifact(Path(path)) for path in args.artifacts]
    print_summary(audits)
    if any(audit.status == "FAIL" for audit in audits):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
