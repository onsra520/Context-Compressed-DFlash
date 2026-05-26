from __future__ import annotations

from pathlib import Path


SPEC_PATH = Path("docs/specs/phase-3-10-dflash-correctness-specification.md")
REPORT_PATH = Path("docs/reports/phase-3-10-dflash-correctness-specification.md")


def test_phase_3_10_spec_exists_and_covers_required_sections() -> None:
    spec = SPEC_PATH.read_text(encoding="utf-8")

    for section in (
        "# Phase 3.10 D-Flash Correctness Specification",
        "## Current Roadmap",
        "## Tokenizer Mismatch",
        "## Candidate Unit",
        "## Verification Unit",
        "## Deterministic Settings",
        "## Acceptance Semantics",
        "## Rejection Semantics",
        "## Fallback Semantics",
        "## Context Update Semantics",
        "## Baseline Equivalence Target",
        "## Correctness Trace Requirements",
        "## Metrics Naming Rules",
        "## Interpretation Guards",
        "## Non-Claims",
    ):
        assert section in spec


def test_phase_3_10_spec_defines_text_first_correctness_boundary() -> None:
    spec = SPEC_PATH.read_text(encoding="utf-8")

    assert "draft_text_chunk" in spec
    assert "normalized text prefix" in spec
    assert "Gemma E2B greedy baseline" in spec
    assert "Qwen-side draft max tokens" in spec
    assert "not a Gemma-token block" in spec
    assert "Phase 3.10 defines correctness semantics only." in spec
    assert "Phase 3.10 does not implement the verifier." in spec
    assert "Phase 3.10 does not validate correctness." in spec


def test_phase_3_10_spec_preserves_guards_and_non_claims() -> None:
    spec = SPEC_PATH.read_text(encoding="utf-8")

    assert "bridge_valid_block_count is structural bridge metadata only." in spec
    assert "cycle_fallback_count is fallback event metadata only." in spec
    assert "No target-equivalence claim is made." in spec
    assert "No draft-acceptance metric is reported." in spec
    assert "This is not D-Flash correctness validation." in spec


def test_phase_3_10_report_exists_and_points_to_spec() -> None:
    report = REPORT_PATH.read_text(encoding="utf-8")

    assert "# Phase 3.10 D-Flash Correctness Specification" in report
    assert "docs/specs/phase-3-10-dflash-correctness-specification.md" in report
    assert "Phase 3.11: Token-Level Verifier Design" in report


def test_phase_3_10_docs_do_not_emit_future_runtime_fields() -> None:
    combined = "\n".join(
        [
            SPEC_PATH.read_text(encoding="utf-8"),
            REPORT_PATH.read_text(encoding="utf-8"),
        ]
    )

    for phrase in (
        "emit accepted_target_token_count",
        "emit rejected_target_token_count",
        "emit first_rejection_position",
        "report " + "acceptance " + "rate",
        "claim target equivalence",
        "claim correctness",
    ):
        assert phrase not in combined
