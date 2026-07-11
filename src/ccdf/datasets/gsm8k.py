"""GSM8K processing for Rec-T02A."""

from __future__ import annotations

import re
from typing import Any

from ccdf.datasets.hashing import hash_json, hash_text
from ccdf.datasets.schemas import validate_fixture

FINAL_ANSWER_RE = re.compile(r"####\s*([-+]?\$?[\d,]+(?:\.\d+)?)")


def extract_final_answer(answer: str) -> str:
    match = FINAL_ANSWER_RE.search(answer)
    if not match:
        raise ValueError("GSM8K answer missing #### final marker")
    return match.group(1).replace("$", "").replace(",", "")


def build_fixture(raw: dict[str, Any], index: int, source_lock: dict[str, Any]) -> dict[str, Any]:
    question = raw["question"]
    reference = extract_final_answer(raw["answer"])
    content = {
        "dataset": "gsm8k",
        "split": "test",
        "upstream_row_index": index,
        "question": question,
        "reference_answer": reference,
    }
    content_hash = hash_json(content)
    fixture_id = f"gsm8k_test_{index:06d}_{content_hash[:8]}"
    instruction = "End with exactly one line: Final answer: <number>"
    prompt = (
        "Short-context numeric QA. Solve the math word problem.\n\n"
        f"Question: {question}\n\n{instruction}"
    )
    row = {
        "fixture_id": fixture_id,
        "dataset": "gsm8k",
        "split": "test",
        "content_hash": content_hash,
        "source_row_hash": hash_json(raw),
        "question": question,
        "reference_answer": reference,
        "prompt_parts": {
            "context": "Short-context numeric QA.",
            "question": question,
            "instruction": instruction,
            "system": None,
        },
        "prompt": prompt,
        "lineage": {
            "source_identity": source_lock["identity"],
            "source_revision": source_lock["resolved_revision"],
            "source_raw_sha256": source_lock["raw_sha256"],
            "upstream_row_index": index,
        },
        "evaluation": {
            "policy": "numeric_final_answer_exact_match",
            "answer_extraction": "GSM8K #### marker",
        },
    }
    validate_fixture(row)
    return row


def build_fixtures(rows: list[dict[str, Any]], source_lock: dict[str, Any]) -> list[dict[str, Any]]:
    fixtures = [build_fixture(row, index, source_lock) for index, row in enumerate(rows)]
    ids = [fixture["fixture_id"] for fixture in fixtures]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate GSM8K fixture id")
    return fixtures


def changed_content_id(raw: dict[str, Any], index: int, source_lock: dict[str, Any]) -> str:
    return build_fixture(raw, index, source_lock)["fixture_id"]


def fixture_text_hash(fixture: dict[str, Any]) -> str:
    return hash_text(fixture["prompt"] + "\n" + fixture["reference_answer"])
