from __future__ import annotations

from pathlib import Path

from scripts.analyze_manual_review import (
    compute_summary,
    parse_manual_review_report,
)


def test_parse_manual_review_report_extracts_rows(tmp_path: Path):
    report = tmp_path / "manual-review.md"
    report.write_text(
        """# Task 35

## Reviewed Rows

| Source artifact | Condition | Prompt id | Expected answer | Generated output summary | Original label | Manual label | Rationale |
| --- | --- | ---: | --- | --- | --- | --- | --- |
| `a.jsonl` | DFlash-R1 | 1 | 410 dollars | summary a | NO_CONTAINMENT | TRUE_FAIL | rationale a |
| `b.jsonl` | CC-LLM-R2 | 2 | 20 items | summary b | NO_CONTAINMENT | PARAPHRASE_OR_FORMAT_MISS | rationale b |
| `c.jsonl` | LLMLingua-AR-R3 | 3 | 5 years | summary c | NO_CONTAINMENT | UNCLEAR | rationale c |

## Summary
""",
        encoding="utf-8",
    )

    rows = parse_manual_review_report(report)

    assert len(rows) == 3
    assert rows[0]["condition"] == "DFlash-R1"
    assert rows[1]["manual_label"] == "PARAPHRASE_OR_FORMAT_MISS"
    assert rows[2]["prompt_id"] == "3"


def test_compute_summary_reports_counts_and_rates():
    rows = [
        {"condition": "DFlash-R1", "manual_label": "TRUE_FAIL"},
        {"condition": "CC-LLM-R2", "manual_label": "TRUE_FAIL"},
        {"condition": "CC-LLM-R2", "manual_label": "PARAPHRASE_OR_FORMAT_MISS"},
        {"condition": "LLMLingua-AR-R3", "manual_label": "UNCLEAR"},
    ]

    summary = compute_summary(rows)

    assert summary["reviewed_rows"] == 4
    assert summary["counts_by_manual_label"] == {
        "TRUE_FAIL": 2,
        "PARAPHRASE_OR_FORMAT_MISS": 1,
        "UNCLEAR": 1,
    }
    assert summary["counts_by_condition"] == {
        "CC-LLM-R2": 2,
        "DFlash-R1": 1,
        "LLMLingua-AR-R3": 1,
    }
    assert summary["true_fail_rate_in_reviewed_no_containment"] == 0.5
    assert summary["paraphrase_or_format_miss_rate"] == 0.25
    assert summary["unclear_rate"] == 0.25
