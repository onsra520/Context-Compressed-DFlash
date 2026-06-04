from __future__ import annotations

import json
from pathlib import Path


FIXTURE_PATH = Path("tests/fixtures/long_context_smoke.jsonl")
REQUIRED_FIELDS = {
    "id",
    "domain",
    "context",
    "question",
    "expected_answer",
    "evidence",
    "noise_type",
    "approximate_context_words",
}


def test_long_context_fixture_contract():
    rows = [
        json.loads(line)
        for line in FIXTURE_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert 5 <= len(rows) <= 10

    for row in rows:
        assert REQUIRED_FIELDS.issubset(row)
        assert isinstance(row["context"], str) and row["context"].strip()
        assert isinstance(row["question"], str) and row["question"].strip()
        assert isinstance(row["expected_answer"], str) and row["expected_answer"].strip()
        assert isinstance(row["evidence"], str) and row["evidence"].strip()
        assert isinstance(row["approximate_context_words"], int)
        assert row["approximate_context_words"] >= 120

        answer = row["expected_answer"]
        assert answer in row["context"] or answer in row["evidence"]
