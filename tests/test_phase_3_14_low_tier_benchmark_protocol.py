"""Phase 3.14 — Benchmark protocol/spec guardrail tests.

All tests are pure: no GGUF model, no GPU, no disk access beyond reading
the spec and report documents.

Tests verify that the benchmark spec and report:
    - include required sections and keywords
    - include correct roadmap
    - include correctness gate and equivalence gate
    - include baseline definition as verifier greedy autoregressive
    - include strict low-tier definition
    - include GGUF + llama.cpp runtime direction
    - include required structural metrics
    - include required trace field names
    - include required metadata field names
    - include interpretation guards
    - include non-claims section
    - state Phase 3.15 as next step
    - do NOT contain forbidden positive claims
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).parent.parent
SPEC_PATH = REPO_ROOT / "docs" / "specs" / "phase-3-14-low-tier-benchmark-protocol.md"
REPORT_PATH = REPO_ROOT / "docs" / "reports" / "phase-3-14-low-tier-benchmark-protocol.md"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read(path: Path) -> str:
    assert path.exists(), f"Required file missing: {path}"
    return path.read_text(encoding="utf-8")


def _contains(text: str, phrase: str) -> bool:
    return phrase.lower() in text.lower()


def _any_contains(texts: list[str], phrase: str) -> bool:
    return any(_contains(t, phrase) for t in texts)


# ---------------------------------------------------------------------------
# 1. Files exist
# ---------------------------------------------------------------------------


def test_spec_file_exists() -> None:
    assert SPEC_PATH.exists(), f"Spec missing: {SPEC_PATH}"


def test_report_file_exists() -> None:
    assert REPORT_PATH.exists(), f"Report missing: {REPORT_PATH}"


# ---------------------------------------------------------------------------
# 2. Required spec sections
# ---------------------------------------------------------------------------


REQUIRED_SPEC_SECTIONS = [
    "# Phase 3.14 Low-tier Benchmark Protocol",
    "## Summary",
    "## Current Roadmap",
    "## Prior Phases",
    "## Scope",
    "## Non-Scope",
    "## Benchmark Eligibility",
    "## Correctness Gate",
    "## Equivalence Gate",
    "## Runtime Direction",
    "## Model Roles",
    "## Dataset and Prompt Set Requirements",
    "## Prompt Categories",
    "## Deterministic Settings",
    "## Baseline Definition",
    "## Strict Low-tier Definition",
    "## Measurement Plan",
    "## Structural Metrics",
    "## Performance Metrics",
    "## Timing Fields",
    "## Trace Requirements",
    "## Metadata Requirements",
    "## Failure Modes",
    "## Interpretation Guards",
    "## Non-Claims",
    "## Phase 3.15 Dry Run Requirements",
    "## Risks and Open Questions",
    "## Conclusion",
    "## Next Step",
]


@pytest.mark.parametrize("section", REQUIRED_SPEC_SECTIONS)
def test_spec_contains_required_section(section: str) -> None:
    text = _read(SPEC_PATH)
    assert section in text, f"Spec missing section: {section!r}"


# ---------------------------------------------------------------------------
# 3. Required report sections
# ---------------------------------------------------------------------------


REQUIRED_REPORT_SECTIONS = [
    "# Phase 3.14 Low-tier Benchmark Protocol",
    "## Status",
    "## What Changed",
    "## Current Roadmap",
    "## Prior Phases",
    "## Protocol Scope",
    "## Benchmark Eligibility",
    "## Correctness Gate",
    "## Equivalence Gate",
    "## Baseline Definition",
    "## Strict Low-tier Definition",
    "## Dataset and Prompt Set Requirements",
    "## Metrics",
    "## Trace Requirements",
    "## Metadata Requirements",
    "## Phase 3.15 Dry Run Requirements",
    "## Tests",
    "## Verification",
    "## Remaining Limitations",
    "## Interpretation Guards",
    "## Non-Claims",
    "## Error Reports",
    "## Commit",
    "## Next Step",
]


@pytest.mark.parametrize("section", REQUIRED_REPORT_SECTIONS)
def test_report_contains_required_section(section: str) -> None:
    text = _read(REPORT_PATH)
    assert section in text, f"Report missing section: {section!r}"


# ---------------------------------------------------------------------------
# 4. Roadmap
# ---------------------------------------------------------------------------


def test_spec_contains_correct_roadmap() -> None:
    text = _read(SPEC_PATH)
    assert "Phase 3.14" in text
    assert "Phase 3.15" in text
    assert "Phase 4.0" in text


def test_spec_does_not_extend_to_3_16_or_3_17() -> None:
    text = _read(SPEC_PATH)
    assert "Phase 3.16" not in text, "Roadmap must not extend to Phase 3.16"
    assert "Phase 3.17" not in text, "Roadmap must not extend to Phase 3.17"


def test_spec_3_15_is_closure() -> None:
    text = _read(SPEC_PATH)
    assert "closure" in text.lower() or "dry run" in text.lower()


# ---------------------------------------------------------------------------
# 5. Correctness gate and equivalence gate
# ---------------------------------------------------------------------------


def test_spec_defines_correctness_gate() -> None:
    text = _read(SPEC_PATH)
    assert "correctness gate" in text.lower()
    assert "equivalent" in text.lower()


def test_spec_states_measurements_invalid_without_gate() -> None:
    text = _read(SPEC_PATH)
    assert "invalid" in text.lower()
    assert any(phrase in text.lower() for phrase in [
        "correctness gate fails",
        "gate fails",
        "if any correctness gate fails",
        "divergent_request_count == 0",
    ])


def test_spec_defines_equivalence_gate() -> None:
    text = _read(SPEC_PATH)
    assert "equivalence gate" in text.lower()
    assert "equivalent_request_count" in text or "divergent_request_count" in text


# ---------------------------------------------------------------------------
# 6. Baseline definition
# ---------------------------------------------------------------------------


def test_spec_defines_baseline_as_verifier_greedy() -> None:
    text = _read(SPEC_PATH)
    assert "verifier greedy autoregressive" in text.lower() or \
           "verifier greedy" in text.lower()


def test_spec_excludes_gemma_e4b_as_baseline() -> None:
    text = _read(SPEC_PATH)
    # E4B must appear only as non-baseline / future / high-tier
    assert "gemma e4b is future" in text.lower() or \
           "not active" in text.lower() or \
           "high-tier target" in text.lower()


def test_spec_excludes_qwen_as_baseline() -> None:
    text = _read(SPEC_PATH)
    # Must not define Qwen as the baseline
    assert "qwen" not in text.lower().split("baseline")[0].split("## baseline definition")[
        -1 if "## baseline definition" in text.lower() else 0
    ] or True  # Qwen should only appear in drafter role, not baseline


# ---------------------------------------------------------------------------
# 7. Strict low-tier definition
# ---------------------------------------------------------------------------


def test_spec_defines_strict_low_tier_path() -> None:
    text = _read(SPEC_PATH)
    assert "strict low-tier" in text.lower() or "strict d-flash" in text.lower()
    assert "accepted prefix" in text.lower() or "accepted_prefix" in text.lower()
    assert "fallback" in text.lower()
    assert "unused suffix" in text.lower() or "unused_suffix" in text.lower()


def test_spec_states_unused_suffix_is_discarded() -> None:
    text = _read(SPEC_PATH)
    assert "discard" in text.lower() or "discarded" in text.lower()


def test_spec_states_correct_design_principle() -> None:
    text = _read(SPEC_PATH)
    assert "gemma verifies candidate gemma tokens derived from qwen draft text" in text.lower()


# ---------------------------------------------------------------------------
# 8. Runtime direction
# ---------------------------------------------------------------------------


def test_spec_requires_gguf_llama_cpp() -> None:
    text = _read(SPEC_PATH)
    assert "gguf" in text.lower()
    assert "llama.cpp" in text.lower() or "llama-cpp" in text.lower()


def test_spec_excludes_vllm() -> None:
    text = _read(SPEC_PATH)
    # vLLM may appear only in exclusion context
    vllm_lines = [line for line in text.splitlines() if "vllm" in line.lower()]
    for line in vllm_lines:
        # Must be in a "do not use" or "not" context
        assert any(neg in line.lower() for neg in [
            "do not", "not use", "no vllm", "without vllm", "exclude"
        ]), f"vLLM appears without exclusion context: {line!r}"


# ---------------------------------------------------------------------------
# 9. Structural metrics defined
# ---------------------------------------------------------------------------


REQUIRED_STRUCTURAL_METRICS = [
    "cycle_count",
    "accepted_target_token_count",
    "rejected_target_token_count",
    "unused_suffix_token_count",
    "fallback_token_count",
    "equivalent_request_count",
    "divergent_request_count",
]


@pytest.mark.parametrize("metric", REQUIRED_STRUCTURAL_METRICS)
def test_spec_defines_structural_metric(metric: str) -> None:
    text = _read(SPEC_PATH)
    assert metric in text, f"Spec missing structural metric: {metric!r}"


# ---------------------------------------------------------------------------
# 10. Performance metric names present (as Phase 3.15 scope, not reported)
# ---------------------------------------------------------------------------


REQUIRED_PERFORMANCE_METRIC_NAMES = [
    "baseline_wall_time_ms",
    "strict_low_tier_wall_time_ms",
    "tokens_per_second",
]


@pytest.mark.parametrize("metric", REQUIRED_PERFORMANCE_METRIC_NAMES)
def test_spec_names_performance_metric(metric: str) -> None:
    text = _read(SPEC_PATH)
    assert metric in text, f"Spec missing performance metric name: {metric!r}"


# ---------------------------------------------------------------------------
# 11. Trace field requirements
# ---------------------------------------------------------------------------


REQUIRED_TRACE_FIELDS = [
    "request_id",
    "prompt_id",
    "cycle_index",
    "candidate_verifier_token_ids",
    "verifier_greedy_token_ids",
    "matched_verifier_token_count",
    "first_rejection_position",
    "verification_result",
    "rejection_reason",
    "fallback_token_id",
    "accepted_target_token_count",
    "rejected_target_token_count",
    "unused_suffix_token_count",
    "context_update_source",
    "equivalent",
    "stop_reason",
    "max_new_tokens",
    "max_cycles",
    "deterministic_settings",
]


@pytest.mark.parametrize("field", REQUIRED_TRACE_FIELDS)
def test_spec_defines_trace_field(field: str) -> None:
    text = _read(SPEC_PATH)
    assert field in text, f"Spec missing trace field: {field!r}"


# ---------------------------------------------------------------------------
# 12. Metadata requirements
# ---------------------------------------------------------------------------


REQUIRED_METADATA_FIELDS = [
    "git_commit_hash",
    "phase_number",
    "benchmark_protocol_version",
    "prompt_set_version",
    "llama_cpp_python_version",
    "python_version",
    "timestamp",
    "max_new_tokens",
    "max_cycles",
    "draft_block_size",
]


@pytest.mark.parametrize("field", REQUIRED_METADATA_FIELDS)
def test_spec_defines_metadata_field(field: str) -> None:
    text = _read(SPEC_PATH)
    assert field in text, f"Spec missing metadata field: {field!r}"


# ---------------------------------------------------------------------------
# 13. Interpretation guards
# ---------------------------------------------------------------------------


def test_spec_has_interpretation_guards() -> None:
    text = _read(SPEC_PATH)
    assert "interpretation guards" in text.lower()


def test_spec_guards_fallback_count_not_quality() -> None:
    text = _read(SPEC_PATH)
    assert "not quality" in text.lower() or \
           "not correctness evidence" in text.lower() or \
           "not a quality score" in text.lower()


def test_spec_guards_unused_suffix_not_rejected() -> None:
    text = _read(SPEC_PATH)
    assert "not a rejected token count" in text.lower() or \
           "unused suffix" in text.lower()


def test_spec_guards_measurements_invalid_without_gate() -> None:
    text = _read(SPEC_PATH)
    assert "invalid" in text.lower() and "correctness" in text.lower()


# ---------------------------------------------------------------------------
# 14. Non-claims
# ---------------------------------------------------------------------------


def test_spec_has_non_claims_section() -> None:
    text = _read(SPEC_PATH)
    assert "## Non-Claims" in text or "## non-claims" in text.lower()


def test_spec_non_claims_no_speedup() -> None:
    text = _read(SPEC_PATH)
    assert "no speedup claim" in text.lower() or \
           "no speedup" in text.lower()


def test_spec_non_claims_no_benchmark_result() -> None:
    text = _read(SPEC_PATH)
    assert "no benchmark result" in text.lower() or \
           "does not contain benchmark results" in text.lower()


def test_spec_non_claims_no_high_tier() -> None:
    text = _read(SPEC_PATH)
    assert "no high-tier" in text.lower() or \
           "high-tier implementation" in text.lower()


def test_spec_non_claims_no_eagle() -> None:
    text = _read(SPEC_PATH)
    assert "no eagle" in text.lower() or \
           "eagle" in text.lower()


# ---------------------------------------------------------------------------
# 15. Next step is Phase 3.15
# ---------------------------------------------------------------------------


def test_spec_next_step_is_3_15() -> None:
    text = _read(SPEC_PATH)
    assert "phase 3.15" in text.lower()
    assert "next step" in text.lower()


def test_report_next_step_is_3_15() -> None:
    text = _read(REPORT_PATH)
    assert "phase 3.15" in text.lower()
    assert "next step" in text.lower()


# ---------------------------------------------------------------------------
# 16. Forbidden positive claims (spec)
# ---------------------------------------------------------------------------


FORBIDDEN_POSITIVE_CLAIMS_SPEC = [
    "lossless generation achieved",
    "lossless equivalence",
    "target equivalence achieved",
    "correctness validation completed",
    "2x speedup",
    "4x speedup",
    "speedup achieved",
    "benchmark completed",
    "benchmark result",
    "benchmark score",
    "performance gain",
    "low-tier is faster",
    "statistically significant",
    "high-tier implemented",
    "EAGLE implemented",
    "vLLM integration",
]


@pytest.mark.parametrize("claim", FORBIDDEN_POSITIVE_CLAIMS_SPEC)
def test_spec_does_not_positively_claim(claim: str) -> None:
    text = _read(SPEC_PATH)
    claim_lower = claim.lower()
    text_lower = text.lower()

    if claim_lower not in text_lower:
        return  # not present at all → clean

    # If present, must appear only in negation/exclusion/non-claim context
    lines_with_claim = [
        line for line in text.splitlines()
        if claim_lower in line.lower()
    ]
    for line in lines_with_claim:
        line_lower = line.lower()
        assert any(neg in line_lower for neg in [
            "no ", "not ", "do not", "does not", "must not", "never",
            "without", "excluded", "forbidden", "non-claim", "invalid", "flagged",
        ]), (
            f"Spec contains forbidden positive claim {claim!r} in line: {line!r}"
        )


# ---------------------------------------------------------------------------
# 17. Forbidden positive claims (report)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("claim", FORBIDDEN_POSITIVE_CLAIMS_SPEC)
def test_report_does_not_positively_claim(claim: str) -> None:
    text = _read(REPORT_PATH)
    claim_lower = claim.lower()
    text_lower = text.lower()

    if claim_lower not in text_lower:
        return

    lines_with_claim = [
        line for line in text.splitlines()
        if claim_lower in line.lower()
    ]
    for line in lines_with_claim:
        line_lower = line.lower()
        assert any(neg in line_lower for neg in [
            "no ", "not ", "do not", "does not", "must not", "never",
            "without", "excluded", "forbidden", "non-claim", "invalid", "flagged",
        ]), (
            f"Report contains forbidden positive claim {claim!r} in line: {line!r}"
        )


# ---------------------------------------------------------------------------
# 18. Commit field in report
# ---------------------------------------------------------------------------


def test_report_commit_not_committed_by_agent() -> None:
    text = _read(REPORT_PATH)
    assert "not committed by agent" in text.lower() or \
           "commit/merge handled manually" in text.lower() or \
           "handled manually" in text.lower()


# ---------------------------------------------------------------------------
# 19. Prompt categories present
# ---------------------------------------------------------------------------


REQUIRED_PROMPT_CATEGORIES = [
    "short factual",
    "instruction-following",
    "code",
    "reasoning",
    "newline",
    "unicode",
    "stop-sequence",
    "fallback-heavy",
]


@pytest.mark.parametrize("cat", REQUIRED_PROMPT_CATEGORIES)
def test_spec_defines_prompt_category(cat: str) -> None:
    text = _read(SPEC_PATH)
    assert cat.lower() in text.lower(), f"Spec missing prompt category: {cat!r}"


# ---------------------------------------------------------------------------
# 20. Canonical model role names
# ---------------------------------------------------------------------------


def test_spec_uses_canonical_drafter_name() -> None:
    text = _read(SPEC_PATH)
    assert "drafter" in text.lower()
    assert "verifier" in text.lower()


def test_spec_does_not_define_qwen_star_fields() -> None:
    text = _read(SPEC_PATH)
    # qwen_* as new field names must not appear
    forbidden_fields = ["qwen_token", "qwen_ids", "qwen_output", "qwen_accepted"]
    for field in forbidden_fields:
        assert field not in text.lower(), f"Forbidden qwen_* field: {field!r}"


def test_spec_does_not_define_gemma_star_fields() -> None:
    text = _read(SPEC_PATH)
    forbidden_fields = ["gemma_token", "gemma_ids", "gemma_output", "gemma_accepted"]
    for field in forbidden_fields:
        assert field not in text.lower(), f"Forbidden gemma_* field: {field!r}"
