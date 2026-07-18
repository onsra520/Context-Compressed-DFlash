"""Per-request quality, parity, and hashing metrics."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def token_ids_sha256(token_ids: list[int]) -> str:
    payload = json.dumps(token_ids, separators=(",", ":")).encode("ascii")
    return sha256_bytes(payload)


def output_quality_record(
    text: str,
    expected_fields: Mapping[str, str],
    *,
    strict_pattern: str,
    tolerant_pattern: str,
) -> dict[str, Any]:
    strict_match = re.fullmatch(strict_pattern, text)
    tolerant_match = re.search(tolerant_pattern, text)
    parsed_fields = tolerant_match.groupdict() if tolerant_match else None
    field_matches = (
        {field: parsed_fields[field] == expected for field, expected in expected_fields.items()}
        if parsed_fields is not None
        else {field: False for field in expected_fields}
    )
    return {
        "format_compliant": strict_match is not None,
        "strict_format_pattern": strict_pattern,
        "tolerant_field_pattern": tolerant_pattern,
        "parsed_fields": parsed_fields,
        "expected_fields": dict(expected_fields),
        "field_matches": field_matches,
        "exact_field_match": parsed_fields is not None and all(field_matches.values()),
    }


def pair_record(left: dict[str, Any], right: dict[str, Any], *, name: str) -> dict[str, Any]:
    if not left["success"] or not right["success"]:
        return {"pair": name, "pass": False, "reason": "condition_failed"}
    left_result = left["result"]
    right_result = right["result"]
    left_input = left_result["protocol_metrics"]["chat_template_input"]
    right_input = right_result["protocol_metrics"]["chat_template_input"]
    chat_token_ids_equal = left_input["token_ids"] == right_input["token_ids"]
    chat_token_sha256_equal = left_input["token_ids_sha256"] == right_input["token_ids_sha256"]
    generated_token_parity = left_result["generated_token_ids"] == right_result["generated_token_ids"]
    return {
        "pair": name,
        "raw_rendered_prompt_sha256_equal": (
            left_result["protocol_metrics"]["raw_rendered_prompt_sha256"]
            == right_result["protocol_metrics"]["raw_rendered_prompt_sha256"]
        ),
        "chat_template_input_token_count": left_input["token_count"],
        "chat_template_input_token_ids_sha256": left_input["token_ids_sha256"],
        "chat_template_input_token_ids_equal": chat_token_ids_equal,
        "chat_template_input_token_sha256_equal": chat_token_sha256_equal,
        "generated_token_parity": generated_token_parity,
        "left_output_tokens": left_result["output_tokens"],
        "right_output_tokens": right_result["output_tokens"],
        "pass": chat_token_ids_equal and chat_token_sha256_equal and generated_token_parity,
    }
