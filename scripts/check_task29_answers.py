from __future__ import annotations

import argparse
import json
import re
import string
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


TASK29_ARTIFACTS = [
    Path("results/task29_dflash_r1_longctx_n6.jsonl"),
    Path("results/task29_cc_llm_r2_longctx_n6.jsonl"),
    Path("results/task29_cc_llm_r3_longctx_n6.jsonl"),
    Path("results/task29_llmlingua_ar_r2_longctx_n6.jsonl"),
    Path("results/task29_llmlingua_ar_r3_longctx_n6.jsonl"),
]
FIXTURE_PATH = Path("tests/fixtures/long_context_smoke.jsonl")
FIXTURE_FIELDS = {
    "prompt_source",
    "fixture_id",
    "domain",
    "expected_answer",
    "evidence",
    "approximate_context_words",
}
GENERATED_TEXT_FIELDS = ("generated_text", "output_text", "decoded_text")


@dataclass
class CheckIssue:
    level: str
    message: str


@dataclass
class ArtifactCheck:
    path: Path
    condition: str | None = None
    rows: int = 0
    exact_matches: int = 0
    normalized_matches: int = 0
    generated_text_present: int = 0
    generated_text_missing: int = 0
    issues: list[CheckIssue] = field(default_factory=list)

    @property
    def status(self) -> str:
        levels = {issue.level for issue in self.issues}
        if "FAIL" in levels:
            return "FAIL"
        if "WARN" in levels:
            return "WARN"
        return "PASS"

    def add(self, level: str, message: str) -> None:
        self.issues.append(CheckIssue(level=level, message=message))


def normalize_text(text: str) -> str:
    punctuation = str.maketrans("", "", string.punctuation)
    normalized = text.lower().translate(punctuation)
    return re.sub(r"\s+", " ", normalized).strip()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def load_fixture_contexts(path: Path = FIXTURE_PATH) -> dict[str, str]:
    if not path.exists():
        return {}
    rows = load_jsonl(path)
    return {str(row["id"]): str(row["context"]) for row in rows}


def _generated_text(row: dict[str, Any]) -> str | None:
    for field_name in GENERATED_TEXT_FIELDS:
        value = row.get(field_name)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _validate_fixture_metadata(
    result: ArtifactCheck,
    row: dict[str, Any],
    row_index: int,
    fixture_contexts: dict[str, str],
) -> None:
    label = f"row {row_index}"
    missing = sorted(FIXTURE_FIELDS - set(row))
    for field_name in missing:
        result.add("FAIL", f"{label}: missing fixture metadata `{field_name}`")
    if missing:
        return

    if row["prompt_source"] != "fixture":
        result.add("FAIL", f"{label}: `prompt_source` must be `fixture`")
    for field_name in ["expected_answer", "evidence"]:
        if not isinstance(row[field_name], str) or not row[field_name].strip():
            result.add("FAIL", f"{label}: `{field_name}` must be a non-empty string")

    expected_answer = str(row.get("expected_answer", ""))
    evidence = str(row.get("evidence", ""))
    fixture_context = fixture_contexts.get(str(row.get("fixture_id")), "")
    if expected_answer and expected_answer not in evidence and expected_answer not in fixture_context:
        result.add("FAIL", f"{label}: expected answer is not present in evidence or fixture context")


def _validate_compression_contract(result: ArtifactCheck, row: dict[str, Any], row_index: int) -> None:
    if "question_preserved" in row and row["question_preserved"] is not True:
        result.add("FAIL", f"row {row_index}: `question_preserved` must be true when present")


def _validate_ar_contract(result: ArtifactCheck, row: dict[str, Any], row_index: int) -> None:
    condition = str(row.get("condition", ""))
    if not condition.startswith("LLMLingua-AR"):
        return
    if row.get("acceptance_lengths") != []:
        result.add("FAIL", f"row {row_index}: AR row must have `acceptance_lengths == []`")
    if row.get("tau_mean") != 0.0:
        result.add("FAIL", f"row {row_index}: AR row must have `tau_mean == 0.0`")
    if row.get("generation_mode") != "autoregressive":
        result.add("FAIL", f"row {row_index}: AR row must have `generation_mode == autoregressive`")
    if row.get("draft_used") is not False:
        result.add("FAIL", f"row {row_index}: AR row must have `draft_used == false`")


def _check_generated_answer(result: ArtifactCheck, row: dict[str, Any], row_index: int) -> None:
    expected_answer = str(row.get("expected_answer", ""))
    generated_text = _generated_text(row)
    if generated_text is None:
        result.generated_text_missing += 1
        result.add("WARN", f"row {row_index}: generated text field is missing; correctness not evaluated")
        return

    result.generated_text_present += 1
    if expected_answer in generated_text:
        result.exact_matches += 1
    if normalize_text(expected_answer) in normalize_text(generated_text):
        result.normalized_matches += 1


def check_artifact(path: Path, fixture_contexts: dict[str, str] | None = None) -> ArtifactCheck:
    result = ArtifactCheck(path=path)
    contexts = fixture_contexts if fixture_contexts is not None else load_fixture_contexts()
    try:
        rows = load_jsonl(path)
    except FileNotFoundError:
        result.add("FAIL", f"artifact missing: {path}")
        return result

    result.rows = len(rows)
    if not rows:
        result.add("FAIL", "artifact contains no rows")
        return result

    conditions = {row.get("condition") for row in rows}
    if len(conditions) == 1:
        condition = next(iter(conditions))
        result.condition = str(condition)
    else:
        result.add("FAIL", f"mixed or missing conditions: {sorted(conditions, key=str)}")

    for row_index, row in enumerate(rows, start=1):
        _validate_fixture_metadata(result, row, row_index, contexts)
        _validate_compression_contract(result, row, row_index)
        _validate_ar_contract(result, row, row_index)
        _check_generated_answer(result, row, row_index)

    return result


def print_summary(results: list[ArtifactCheck]) -> None:
    for result in results:
        condition = result.condition or "unknown"
        print(
            f"{result.status} {result.path} condition={condition} rows={result.rows} "
            f"generated_text_present={result.generated_text_present} "
            f"generated_text_missing={result.generated_text_missing} "
            f"exact_matches={result.exact_matches} normalized_matches={result.normalized_matches} "
            f"issues={len(result.issues)}"
        )
        for issue in result.issues:
            print(f"  {issue.level}: {issue.message}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Check Task 29 answer metadata and generated-text matches")
    parser.add_argument("artifacts", nargs="*", help="Task 29 JSONL artifacts to check")
    parser.add_argument("--fixture", default=str(FIXTURE_PATH), help="Fixture JSONL path")
    args = parser.parse_args()

    paths = [Path(path) for path in args.artifacts] if args.artifacts else TASK29_ARTIFACTS
    fixture_contexts = load_fixture_contexts(Path(args.fixture))
    results = [check_artifact(path, fixture_contexts) for path in paths]
    print_summary(results)
    if any(result.status == "FAIL" for result in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
