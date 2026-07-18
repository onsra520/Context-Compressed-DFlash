"""Four-condition protocol definitions and fixture construction."""

from __future__ import annotations

from typing import Any

from ..benchmark.metrics import sha256_text
from ..compression import ContextOnlyProtocol
from ..config import ResolvedProtocolProfile


PROTOCOL_VERSION = "ccdf.four-condition.config-profile.v1"
ARTIFACT_FILENAMES = {
    "fixtures": "mock_fixtures.json",
    "raw": "raw_runs.json",
    "summary": "summary.json",
    "report": "FINAL_REPORT.md",
    "gates": "gate_matrix.json",
    "protected_hashes": "protected_field_hashes.json",
    "parity": "pair_parity.json",
    "config_snapshot": "resolved_config_snapshot.json",
}


def build_fixtures(profile: ResolvedProtocolProfile) -> list[dict[str, Any]]:
    contract = profile.require("prompt_contract")
    fixtures = []
    for index, values in enumerate(profile.require("fixtures"), start=1):
        turns = int(values["turns"])
        distractors = [
            str(contract["distractor_template"]).format(
                turn=turn,
                candidate=turn % 7,
                fixture_index=index,
                turn_padded=f"{turn:03d}",
                distractor_quantity=1000 + index * 100 + turn,
            )
            for turn in range(1, turns + 1)
        ]
        expected_fields = {
            "owner": str(values["owner"]),
            "approval_code": str(values["approval_code"]),
            "quantity": str(values["quantity"]),
        }
        evidence = str(contract["evidence_template"]).format(**expected_fields)
        position = float(values["evidence_position_fraction"])
        insertion = round(len(distractors) * position)
        context = " ".join(distractors[:insertion] + [evidence] + distractors[insertion:])
        protocol = ContextOnlyProtocol(
            context=context,
            question=str(contract["question"]),
            output_instruction=str(contract["output_instruction"]),
        )
        fixtures.append({
            "prompt_id": f"mock_{index:02d}",
            "context_turns": turns,
            "evidence_position_fraction": position,
            "expected_fields": expected_fields,
            "context": context,
            "question": protocol.question,
            "output_instruction": protocol.output_instruction,
            "protocol": protocol,
        })
    return fixtures


def json_fixture(item: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in item.items() if key != "protocol"}


def input_quality_record(
    item: dict[str, Any], compressed_context: str, original_prompt: str, compressed_prompt: str
) -> dict[str, Any]:
    evidence = list(item["expected_fields"].values())
    original_protected = original_prompt.split("\n\nQuestion:\n", 1)[1].encode("utf-8")
    compressed_protected = compressed_prompt.split("\n\nQuestion:\n", 1)[1].encode("utf-8")
    protected_byte_exact = original_protected == compressed_protected
    evidence_once_input = all(item["context"].count(fragment) == 1 for fragment in evidence)
    evidence_retained = all(fragment in compressed_context for fragment in evidence)
    return {
        "protected_fields_byte_exact": protected_byte_exact,
        "question_sha256": sha256_text(item["question"]),
        "instruction_sha256": sha256_text(item["output_instruction"]),
        "required_evidence": evidence,
        "required_evidence_occurs_once_in_original_context": evidence_once_input,
        "required_evidence_retained_in_compressed_context": evidence_retained,
        "pass": protected_byte_exact and evidence_once_input and evidence_retained,
    }
