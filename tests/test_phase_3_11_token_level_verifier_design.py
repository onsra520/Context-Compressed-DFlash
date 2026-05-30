"""Phase 3.11 Token-Level Verifier Design — documentation presence and guardrail tests."""

from __future__ import annotations

from pathlib import Path


SPEC_PATH = Path("docs/specs/phase-3-11-token-level-verifier-design.md")
REPORT_PATH = Path("docs/reports/phase-3-11-token-level-verifier-design.md")


# ---------------------------------------------------------------------------
# Spec presence and required section tests
# ---------------------------------------------------------------------------


def test_phase_3_11_spec_exists_and_covers_required_sections() -> None:
    spec = SPEC_PATH.read_text(encoding="utf-8")

    for section in (
        "# Phase 3.11 Token-Level Verifier Design",
        "## Summary",
        "## Current Roadmap",
        "## Prior Specification",
        "## Scope",
        "## Non-Scope",
        "## Problem Statement",
        "## Tokenizer Mismatch",
        "## Design Principle",
        "## Candidate Source",
        "## Candidate Tokenization",
        "## Verifier Greedy Decision Source",
        "## Token Comparison Algorithm",
        "## Partial Match and First Rejection Position",
        "## Acceptance Semantics",
        "## Rejection Semantics",
        "## Fallback Semantics",
        "## Context Update Semantics",
        "## Trace Schema Requirements",
        "## Backend Capability Requirements",
        "## llama-cpp-python / GGUF Constraints",
        "## Deterministic Settings",
        "## Failure Modes",
        "## Metrics Naming Rules",
        "## Implementation Boundary for Phase 3.12",
        "## Risks and Open Questions",
        "## Interpretation Guards",
        "## Non-Claims",
        "## Conclusion",
        "## Next Step",
    ):
        assert section in spec, f"Missing required section: {section!r}"


def test_phase_3_11_spec_states_design_principle_correctly() -> None:
    spec = SPEC_PATH.read_text(encoding="utf-8")

    # Central design statement must be present
    assert "Gemma verifies candidate Gemma tokens derived from Qwen draft text" in spec

    # The incorrect wording must not appear as a positive claim
    # (It may appear as a negation — "Not: Gemma verifies Qwen tokens")
    # We check the correct phrasing is present; we don't assert the wrong one is absent
    # since the spec explicitly calls it out as the incorrect form.


def test_phase_3_11_spec_defines_tokenizer_mismatch() -> None:
    spec = SPEC_PATH.read_text(encoding="utf-8")

    assert "different tokenizers" in spec
    assert "candidate_verifier_token_ids" in spec
    assert "verifier_greedy_token_ids" in spec
    assert "draft_block_size" in spec
    # The spec must clarify that draft_block_size != Gemma target tokens
    assert (
        "NOT 8 Gemma target tokens" in spec
        or "not 8 gemma target tokens" in spec.lower()
        or "not a gemma-token block" in spec.lower()
        or "not gemma target tokens" in spec.lower()
        or "not correspond to 8 gemma" in spec.lower()
    )


def test_phase_3_11_spec_defines_candidate_tokenization() -> None:
    spec = SPEC_PATH.read_text(encoding="utf-8")

    # Combined context+candidate tokenization approach
    assert "tokens_context_plus_candidate" in spec or "context + candidate" in spec.lower() or "context text + candidate" in spec.lower()
    assert "candidate_verifier_token_ids" in spec
    assert "candidate_verifier_token_count" in spec


def test_phase_3_11_spec_defines_verifier_greedy_decision_source() -> None:
    spec = SPEC_PATH.read_text(encoding="utf-8")

    assert "verifier_greedy_token_ids" in spec
    assert "greedy" in spec
    # Must reference the preferred approach (logit/eval step) and fallback
    assert "logit" in spec.lower() or "get_logits" in spec
    assert "Approach A" in spec or "Approach B" in spec


def test_phase_3_11_spec_defines_comparison_algorithm() -> None:
    spec = SPEC_PATH.read_text(encoding="utf-8")

    assert "full_accept" in spec
    assert "partial_accept" in spec
    assert "full_reject" in spec
    assert "first_rejection_position" in spec
    assert "matched_verifier_token_count" in spec


def test_phase_3_11_spec_defines_partial_match_and_unused_suffix() -> None:
    spec = SPEC_PATH.read_text(encoding="utf-8")

    # Unused suffix is discarded, not rejected
    assert "unused" in spec.lower()
    assert "discarded" in spec.lower() or "discard" in spec.lower()
    # The spec must clarify that unused suffix != rejected
    assert "unused_suffix" in spec or "unused suffix" in spec.lower()


def test_phase_3_11_spec_defines_acceptance_rejection_fallback() -> None:
    spec = SPEC_PATH.read_text(encoding="utf-8")

    assert "## Acceptance Semantics" in spec
    assert "## Rejection Semantics" in spec
    assert "## Fallback Semantics" in spec
    assert "fallback_reason" in spec
    assert "rejection_reason" in spec


def test_phase_3_11_spec_defines_context_update_rule() -> None:
    spec = SPEC_PATH.read_text(encoding="utf-8")

    assert "## Context Update Semantics" in spec
    # Strict context update terms
    assert "accepted_prefix_text" in spec or "accepted prefix" in spec.lower()
    assert "fallback_token" in spec or "fallback token" in spec.lower()
    # Must not allow unverified drafter text
    assert "unverified drafter text" in spec


def test_phase_3_11_spec_defines_trace_schema() -> None:
    spec = SPEC_PATH.read_text(encoding="utf-8")

    assert "## Trace Schema Requirements" in spec
    for field in (
        "cycle_index",
        "candidate_text",
        "candidate_verifier_token_ids",
        "candidate_verifier_token_count",
        "verifier_greedy_token_ids",
        "verifier_greedy_token_count",
        "matched_verifier_token_count",
        "first_rejection_position",
        "verification_result",
        "rejection_reason",
        "fallback_reason",
        "accepted_target_token_count",
        "rejected_target_token_count",
        "unused_suffix_token_count",
        "context_update_source",
        "comparison_profile",
        "deterministic_settings",
        "backend_capability_status",
    ):
        assert field in spec, f"Missing trace schema field: {field!r}"


def test_phase_3_11_spec_defines_backend_capability_requirements() -> None:
    spec = SPEC_PATH.read_text(encoding="utf-8")

    assert "## Backend Capability Requirements" in spec
    assert "## llama-cpp-python / GGUF Constraints" in spec
    assert "unknown" in spec.lower()
    # Must not claim vLLM or hidden states are used
    assert "vLLM" not in spec or "Do not switch to vLLM" in spec
    assert "supports_hidden_states" in spec or "hidden states" in spec.lower()


def test_phase_3_11_spec_references_phase_310_prior_spec() -> None:
    spec = SPEC_PATH.read_text(encoding="utf-8")

    assert "Phase 3.10" in spec
    assert "13022de" in spec or "docs: define dflash correctness specification" in spec
    assert "docs/specs/phase-3-10-dflash-correctness-specification.md" in spec or "Phase 3.10" in spec


def test_phase_3_11_spec_defines_deterministic_settings() -> None:
    spec = SPEC_PATH.read_text(encoding="utf-8")

    assert "## Deterministic Settings" in spec
    assert "temperature" in spec
    assert "0.0" in spec
    assert "greedy" in spec
    assert "seed" in spec


def test_phase_3_11_spec_preserves_interpretation_guards() -> None:
    spec = SPEC_PATH.read_text(encoding="utf-8")

    assert "## Interpretation Guards" in spec
    # The spec uses backtick notation: "`bridge_valid_block_count` is a bridge-level structural diagnostic count only."
    assert "`bridge_valid_block_count` is a bridge-level structural diagnostic count only" in spec
    assert "`cycle_fallback_count` is a cycle-level fallback count only" in spec
    assert "It is not accepted block count." in spec
    assert "It is not correctness evidence." in spec
    assert "It is not performance evidence." in spec
    assert "It is not benchmark evidence." in spec
    assert "It is not a quality score." in spec


def test_phase_3_11_spec_preserves_non_claims() -> None:
    spec = SPEC_PATH.read_text(encoding="utf-8")

    assert "## Non-Claims" in spec
    assert "This is not a benchmark report." in spec
    assert "This is not D-Flash correctness validation." in spec
    assert "No speedup claim is made." in spec
    assert "No target-equivalence claim is made." in spec
    assert "No correctness claim is made." in spec
    assert "No lossless-generation claim is made." in spec
    assert "No draft-acceptance metric is reported." in spec
    assert "No high-tier implementation claim is made." in spec


def test_phase_3_11_spec_points_to_phase_312_next_step() -> None:
    spec = SPEC_PATH.read_text(encoding="utf-8")

    assert "## Next Step" in spec
    assert "Phase 3.12" in spec
    assert "Strict Acceptance" in spec or "Strict acceptance" in spec or "strict acceptance" in spec.lower()


def test_phase_3_11_spec_does_not_claim_implementation_complete() -> None:
    spec = SPEC_PATH.read_text(encoding="utf-8")

    # These phrases must not appear as POSITIVE claims.
    # They may appear inside non-claim sections or as negations (e.g., "No speedup claim is made.").
    # Check for positive claim forms only.
    for forbidden_positive_phrase in (
        "correctness validation completed",
        "benchmark completed",
        "benchmark score",
        "speedup achieved",
        "2x speedup",
        "4x speedup",
        "performance gain",
        "low-tier is faster",
        "high-tier implemented",
        "EAGLE implemented",
        "lossless equivalence",
        "lossless generation achieved",
        "target equivalence achieved",
        "statistically significant",
    ):
        assert forbidden_positive_phrase.lower() not in spec.lower(), (
            f"Forbidden positive claim found in Phase 3.11 spec: {forbidden_positive_phrase!r}"
        )

    # Verify the spec does NOT claim vLLM is being used/introduced
    # ("vLLM" may appear only in "Do not switch to vLLM" form)
    assert "vLLM integration" not in spec or "not introduce" in spec or "Do not switch" in spec


# ---------------------------------------------------------------------------
# Report presence and required section tests
# ---------------------------------------------------------------------------


def test_phase_3_11_report_exists_and_covers_required_sections() -> None:
    report = REPORT_PATH.read_text(encoding="utf-8")

    for section in (
        "# Phase 3.11 Token-Level Verifier Design",
        "## Status",
        "## What Changed",
        "## Current Roadmap",
        "## Prior Specification",
        "## Design Summary",
        "## Tokenizer Mismatch",
        "## Candidate Tokenization",
        "## Verifier Greedy Decision Source",
        "## Token Comparison Algorithm",
        "## Partial Match and First Rejection Position",
        "## Acceptance Semantics",
        "## Rejection Semantics",
        "## Fallback Semantics",
        "## Context Update Semantics",
        "## Trace Schema Requirements",
        "## Backend Capability Requirements",
        "## Deterministic Settings",
        "## Metrics Naming Rules",
        "## Verification",
        "## Remaining Limitations",
        "## Interpretation Guards",
        "## Non-Claims",
        "## Error Reports",
        "## Commit",
        "## Next Step",
    ):
        assert section in report, f"Missing required section in report: {section!r}"


def test_phase_3_11_report_preserves_non_claims() -> None:
    report = REPORT_PATH.read_text(encoding="utf-8")

    assert "This is not a benchmark report." in report
    assert "This is not D-Flash correctness validation." in report
    assert "No speedup claim is made." in report
    assert "No target-equivalence claim is made." in report
    assert "No correctness claim is made." in report
    assert "No high-tier implementation claim is made." in report


def test_phase_3_11_report_points_to_spec_and_next_step() -> None:
    report = REPORT_PATH.read_text(encoding="utf-8")

    assert "docs/specs/phase-3-11-token-level-verifier-design.md" in report
    assert "Phase 3.12" in report


def test_phase_3_11_report_does_not_claim_implementation_complete() -> None:
    report = REPORT_PATH.read_text(encoding="utf-8")

    for forbidden_positive_phrase in (
        "correctness validation completed",
        "benchmark completed",
        "speedup achieved",
        "2x speedup",
        "4x speedup",
        "high-tier implemented",
        "EAGLE implemented",
        "lossless generation achieved",
        "target equivalence achieved",
        "statistically significant",
    ):
        assert forbidden_positive_phrase.lower() not in report.lower(), (
            f"Forbidden positive claim found in Phase 3.11 report: {forbidden_positive_phrase!r}"
        )

    # vLLM may appear only in non-claim context ("No vLLM path is introduced")
    assert "vLLM integration" not in report or "not introduce" in report or "Do not switch" in report


# ---------------------------------------------------------------------------
# Cross-doc tests
# ---------------------------------------------------------------------------


def test_phase_3_11_docs_do_not_emit_reserved_runtime_fields() -> None:
    """Verify that reserved future fields are not claimed as Phase 3.11 runtime output."""
    combined = "\n".join([
        SPEC_PATH.read_text(encoding="utf-8"),
        REPORT_PATH.read_text(encoding="utf-8"),
    ])

    # These exact phrases must not appear — they would indicate Phase 3.11 incorrectly
    # claims to emit future runtime fields.
    for phrase in (
        "emit accepted_target_token_count",
        "emit rejected_target_token_count",
        "emit first_rejection_position",
        "emit matched_verifier_token_count",
    ):
        assert phrase not in combined, f"Forbidden emission phrase found: {phrase!r}"

    # The docs must not claim acceptance rate is being reported (as a positive claim)
    # "report acceptance rate" is forbidden; "No acceptance rate is measured" is fine.
    assert "report acceptance rate" not in combined.lower()


def test_phase_3_11_docs_use_canonical_role_names() -> None:
    """Verify canonical role-based naming is used in the spec."""
    spec = SPEC_PATH.read_text(encoding="utf-8")

    # Canonical names must be present
    assert "drafter" in spec
    assert "verifier" in spec

    # Model-specific names should not appear as new primary names
    # (They may appear in legacy context or naming deprecation notes)
    assert "candidate_verifier_token_ids" in spec
    assert "verifier_greedy_token_ids" in spec
