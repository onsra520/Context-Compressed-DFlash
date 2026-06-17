from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


EXPECTED_COLUMNS = [
    "Source artifact",
    "Condition",
    "Prompt id",
    "Expected answer",
    "Generated output summary",
    "Original label",
    "Manual label",
    "Rationale",
]
ALLOWED_LABELS = {"TRUE_FAIL", "PARAPHRASE_OR_FORMAT_MISS", "UNCLEAR"}


def _split_markdown_row(line: str) -> list[str]:
    stripped = line.strip()
    if not (stripped.startswith("|") and stripped.endswith("|")):
        raise ValueError(f"Expected markdown table row, got: {line!r}")
    return [cell.strip() for cell in stripped[1:-1].split("|")]


def parse_manual_review_report(path: Path) -> list[dict[str, str]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    start = None
    for index, line in enumerate(lines):
        if line.strip() == "## Reviewed Rows":
            start = index
            break
    if start is None:
        raise ValueError("Could not find '## Reviewed Rows' section")

    table_lines: list[str] = []
    saw_table = False
    for line in lines[start + 1 :]:
        if line.strip().startswith("|"):
            table_lines.append(line)
            saw_table = True
            continue
        if saw_table:
            break
    if len(table_lines) < 3:
        raise ValueError("Reviewed Rows table is missing or incomplete")

    header = _split_markdown_row(table_lines[0])
    if header != EXPECTED_COLUMNS:
        raise ValueError(f"Unexpected Reviewed Rows columns: {header!r}")

    rows: list[dict[str, str]] = []
    for row_line in table_lines[2:]:
        cells = _split_markdown_row(row_line)
        if len(cells) != len(EXPECTED_COLUMNS):
            raise ValueError(f"Row has {len(cells)} cells, expected {len(EXPECTED_COLUMNS)}: {row_line!r}")
        row = {
            "source_artifact": cells[0].strip("`"),
            "condition": cells[1],
            "prompt_id": cells[2],
            "expected_answer": cells[3],
            "generated_output_summary": cells[4],
            "original_label": cells[5],
            "manual_label": cells[6],
            "rationale": cells[7],
        }
        if row["manual_label"] not in ALLOWED_LABELS:
            raise ValueError(f"Unexpected manual label {row['manual_label']!r} in row: {row_line!r}")
        rows.append(row)
    return rows


def compute_summary(rows: list[dict[str, str]]) -> dict[str, object]:
    reviewed_rows = len(rows)
    label_counts = Counter(row["manual_label"] for row in rows)
    condition_counts = Counter(row["condition"] for row in rows)

    def rate(label: str) -> float:
        return label_counts.get(label, 0) / reviewed_rows if reviewed_rows else 0.0

    return {
        "reviewed_rows": reviewed_rows,
        "counts_by_manual_label": {
            "TRUE_FAIL": label_counts.get("TRUE_FAIL", 0),
            "PARAPHRASE_OR_FORMAT_MISS": label_counts.get("PARAPHRASE_OR_FORMAT_MISS", 0),
            "UNCLEAR": label_counts.get("UNCLEAR", 0),
        },
        "counts_by_condition": dict(sorted(condition_counts.items())),
        "true_fail_rate_in_reviewed_no_containment": rate("TRUE_FAIL"),
        "paraphrase_or_format_miss_rate": rate("PARAPHRASE_OR_FORMAT_MISS"),
        "unclear_rate": rate("UNCLEAR"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze Task 35 manual review markdown report")
    parser.add_argument("--input", required=True, help="Path to the Task 35 manual review report")
    args = parser.parse_args()

    rows = parse_manual_review_report(Path(args.input))
    summary = compute_summary(rows)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
