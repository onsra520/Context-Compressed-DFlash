from __future__ import annotations

import argparse
import json
import statistics
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.create_dataset import BuildOptions, build_rows, write_jsonl


DEFAULT_INPUT = Path("data/eval/gsm8k_100.jsonl")
DEFAULT_OUTPUT = Path("results/task42_dataset_audit_summary.json")

REQUIRED_FIELDS = {
    "id",
    "source",
    "source_mode",
    "domain",
    "question",
    "answer",
    "ground_truth_answer",
    "expected_answer",
    "context",
    "prompt",
    "evidence",
    "approximate_context_words",
    "original_dataset_reference",
    "augmentation_metadata",
    "token_length_metadata",
}

RUNNER_FIELDS = {
    "id",
    "domain",
    "context",
    "question",
    "expected_answer",
    "evidence",
    "approximate_context_words",
}


@dataclass
class Issue:
    level: str
    message: str


@dataclass
class AuditResult:
    input_path: Path
    rows: list[dict[str, Any]] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)
    reproducibility: dict[str, Any] = field(default_factory=dict)

    @property
    def status(self) -> str:
        levels = {issue.level for issue in self.issues}
        if "FAIL" in levels:
            return "FAIL"
        if "WARN" in levels:
            return "WARN"
        return "PASS"

    def add(self, level: str, message: str) -> None:
        self.issues.append(Issue(level, message))


def load_jsonl(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return rows, [f"missing dataset: {path}"]

    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"line {line_number}: invalid JSON ({exc})")
            continue
        if not isinstance(row, dict):
            errors.append(f"line {line_number}: row is not a JSON object")
            continue
        rows.append(row)
    return rows, errors


def _normalize_for_leakage(text: str) -> str:
    import re
    return " ".join(re.findall(r"[a-z0-9]+", text.casefold()))


def contains_answer(text: str, answer: str) -> bool:
    import re
    normalized_answer = _normalize_for_leakage(answer)
    if not normalized_answer:
        return False
    normalized_text = _normalize_for_leakage(text)
    return re.search(rf"(?<![a-z0-9]){re.escape(normalized_answer)}(?![a-z0-9])", normalized_text) is not None


def _distribution(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"min": None, "max": None, "mean": None, "median": None}
    return {
        "min": min(values),
        "max": max(values),
        "mean": statistics.mean(values),
        "median": statistics.median(values),
    }


def _validate_row(audit: AuditResult, row: dict[str, Any], index: int) -> None:
    label = f"row {index}"
    missing = REQUIRED_FIELDS - set(row)
    if missing:
        audit.add("FAIL", f"{label}: missing required fields {sorted(missing)}")
    missing_runner = RUNNER_FIELDS - set(row)
    if missing_runner:
        audit.add("FAIL", f"{label}: missing runner-compatible fields {sorted(missing_runner)}")

    for field_name in ["id", "question", "context", "prompt", "expected_answer", "ground_truth_answer"]:
        value = row.get(field_name)
        if not isinstance(value, str) or not value.strip():
            audit.add("FAIL", f"{label}: `{field_name}` must be a non-empty string")

    if row.get("expected_answer") != row.get("ground_truth_answer"):
        audit.add("FAIL", f"{label}: expected_answer and ground_truth_answer differ")

    question = str(row.get("question", ""))
    prompt = str(row.get("prompt", ""))
    context = str(row.get("context", ""))
    answer = str(row.get("ground_truth_answer", row.get("expected_answer", "")))

    if question and prompt and question not in prompt:
        audit.add("FAIL", f"{label}: question is not preserved in prompt")
    if answer and context and contains_answer(context, answer):
        audit.add("FAIL", f"{label}: final answer leaked into context")
    if answer and prompt and contains_answer(prompt, answer):
        audit.add("FAIL", f"{label}: final answer leaked into prompt")

    approximate_context_words = row.get("approximate_context_words")
    if not isinstance(approximate_context_words, (int, float)) or isinstance(approximate_context_words, bool):
        audit.add("FAIL", f"{label}: approximate_context_words must be numeric")
    elif approximate_context_words <= 0:
        audit.add("FAIL", f"{label}: approximate_context_words must be positive")

    approximate_context_tokens = row.get("approximate_context_tokens")
    if approximate_context_tokens is not None:
        if not isinstance(approximate_context_tokens, (int, float)) or isinstance(approximate_context_tokens, bool):
            audit.add("FAIL", f"{label}: approximate_context_tokens must be numeric when present")
        elif approximate_context_tokens <= 0:
            audit.add("FAIL", f"{label}: approximate_context_tokens must be positive when present")

    for field_name in ["original_dataset_reference", "augmentation_metadata", "token_length_metadata"]:
        if not isinstance(row.get(field_name), dict) or not row.get(field_name):
            audit.add("FAIL", f"{label}: `{field_name}` must be a non-empty object")


def audit_rows(path: Path) -> AuditResult:
    audit = AuditResult(input_path=path)
    rows, errors = load_jsonl(path)
    for error in errors:
        audit.add("FAIL", error)
    audit.rows = rows

    if errors:
        return audit
    if not rows:
        audit.add("FAIL", "dataset contains no rows")
        return audit

    ids = [row.get("id") for row in rows]
    if any(not isinstance(row_id, str) or not row_id.strip() for row_id in ids):
        audit.add("FAIL", "all rows must have stable non-empty string ids")
    duplicate_ids = sorted({row_id for row_id in ids if ids.count(row_id) > 1})
    if duplicate_ids:
        audit.add("FAIL", f"duplicate row ids: {duplicate_ids}")

    for index, row in enumerate(rows, start=1):
        _validate_row(audit, row, index)

    return audit


def reproducibility_check() -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmpdir:
        first = Path(tmpdir) / "first.jsonl"
        second = Path(tmpdir) / "second.jsonl"
        options = BuildOptions(
            output=first,
            max_samples=5,
            seed=41,
            split="test",
            source_mode="sample",
        )
        rows_first = build_rows(options)
        write_jsonl(rows_first, first)
        rows_second = build_rows(BuildOptions(**{**options.__dict__, "output": second}))
        write_jsonl(rows_second, second)
        first_bytes = first.read_bytes()
        second_bytes = second.read_bytes()
        return {
            "mode": "sample",
            "seed": 41,
            "row_level_equal": rows_first == rows_second,
            "byte_level_equal": first_bytes == second_bytes,
            "rows": len(rows_first),
        }


def summarize(audit: AuditResult) -> dict[str, Any]:
    rows = audit.rows
    context_words = [
        float(row["approximate_context_words"])
        for row in rows
        if isinstance(row.get("approximate_context_words"), (int, float)) and not isinstance(row.get("approximate_context_words"), bool)
    ]
    context_tokens = [
        float(row["approximate_context_tokens"])
        for row in rows
        if isinstance(row.get("approximate_context_tokens"), (int, float)) and not isinstance(row.get("approximate_context_tokens"), bool)
    ]
    source_modes = sorted({str(row.get("source_mode")) for row in rows if row.get("source_mode") is not None})
    sources = sorted({str(row.get("source")) for row in rows if row.get("source") is not None})

    full_benchmark_ready = audit.status == "PASS" and source_modes == ["hf"]
    sample_artifact_ready = audit.status == "PASS" and source_modes == ["sample"]

    return {
        "status": audit.status,
        "input_path": str(audit.input_path),
        "row_count": len(rows),
        "sources": sources,
        "source_modes": source_modes,
        "duplicate_id_count": len(rows) - len({row.get("id") for row in rows}),
        "context_words": _distribution(context_words),
        "context_tokens": _distribution(context_tokens),
        "reproducibility": audit.reproducibility,
        "readiness": {
            "builder_ready": audit.status == "PASS" and audit.reproducibility.get("byte_level_equal") is True,
            "sample_artifact_ready": sample_artifact_ready,
            "full_benchmark_dataset_ready": full_benchmark_ready,
            "full_benchmark_dataset_reason": (
                "source_mode is sample; full source-mode data has not been generated or audited"
                if source_modes == ["sample"]
                else "full source-mode audit passed"
                if full_benchmark_ready
                else "audit did not pass"
            ),
        },
        "issues": [{"level": issue.level, "message": issue.message} for issue in audit.issues],
    }


def write_summary(summary: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def print_summary(summary: dict[str, Any]) -> None:
    readiness = summary["readiness"]
    print(
        f"{summary['status']} {summary['input_path']} rows={summary['row_count']} "
        f"source_modes={','.join(summary['source_modes'])} issues={len(summary['issues'])}"
    )
    print(
        "readiness:"
        f" builder_ready={readiness['builder_ready']}"
        f" sample_artifact_ready={readiness['sample_artifact_ready']}"
        f" full_benchmark_dataset_ready={readiness['full_benchmark_dataset_ready']}"
    )
    print(f"context_words={summary['context_words']}")
    print(f"context_tokens={summary['context_tokens']}")
    for issue in summary["issues"]:
        print(f"  {issue['level']}: {issue['message']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit dataset JSONL")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--strict", action="store_true", help="Exit non-zero on WARN as well as FAIL")
    args = parser.parse_args()

    audit = audit_rows(args.input)
    audit.reproducibility = reproducibility_check()
    summary = summarize(audit)
    write_summary(summary, args.output)
    print_summary(summary)
    print(f"wrote {args.output}")

    if summary["status"] == "FAIL" or (args.strict and summary["status"] != "PASS"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
