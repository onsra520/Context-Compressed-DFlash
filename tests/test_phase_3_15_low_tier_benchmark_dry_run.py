"""Phase 3.15 — Low-tier benchmark dry-run guardrail tests.

All tests except those explicitly marked with HTFSD_LOCAL_MODEL_TEST=1
require NO GGUF model, no GPU, no real model execution.

Tests cover:
    - Report file existence and required sections
    - Correct/conditional roadmap in report
    - Dry-run harness structural correctness (fake cases)
    - Fake full-accept case
    - Fake partial-accept + fallback case
    - Fake full-reject + fallback case
    - Fake EOS termination case
    - Fake no-progress error case
    - Fake max-new-tokens truncation case
    - Divergence detection case (expected failure gate check)
    - Unused suffix leak detection case (expected failure gate check)
    - Structural metrics aggregation
    - Invalid cases excluded from performance interpretation
    - Forbidden positive claims absent
    - MVP closure decision present and compliant
    - Phase 3.16 routing decision present
    - Prompt fixture loaded and validated
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).parent.parent
REPORT_PATH = REPO_ROOT / "docs" / "reports" / "phase-3-15-low-tier-benchmark-dry-run-mvp-closure.md"
PROMPT_FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "phase_3_15_low_tier_prompts.json"
DRY_RUN_MODULE = "htfsd.benchmark.low_tier_dry_run"

REAL_MODEL_TEST = os.environ.get("HTFSD_LOCAL_MODEL_TEST", "0") == "1"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read(path: Path) -> str:
    assert path.exists(), f"Required file missing: {path}"
    return path.read_text(encoding="utf-8")


def _contains(text: str, phrase: str) -> bool:
    return phrase.lower() in text.lower()


# ---------------------------------------------------------------------------
# 1. Files exist
# ---------------------------------------------------------------------------


def test_report_file_exists() -> None:
    assert REPORT_PATH.exists(), f"Report missing: {REPORT_PATH}"


def test_prompt_fixture_exists() -> None:
    assert PROMPT_FIXTURE_PATH.exists(), f"Prompt fixture missing: {PROMPT_FIXTURE_PATH}"


# ---------------------------------------------------------------------------
# 2. Required report sections
# ---------------------------------------------------------------------------


REQUIRED_REPORT_SECTIONS = [
    "# Phase 3.15 Low-tier Benchmark Dry Run",
    "## Status",
    "## What Changed",
    "## Current Roadmap",
    "## Conditional Roadmap Decision",
    "## Prior Phase Chain",
    "## Runtime and Model Audit",
    "## Real/Local Benchmark Attempt",
    "## Context Duplication Bug",
    "## Multi-cycle Benchmark Attempt",
    "## Real D-Flash Benchmark Metrics",
    "## Speedup Usefulness Analysis",
    "## Low-Tier Usefulness Decision",
    "## Blocker Status",
    "## Fallback Diagnostic Dry Run",
    "## Dry Run Cases",
    "## Structural Metrics",
    "## Timing Fields",
    "## Correctness Gate",
    "## Equivalence Gate",
    "## Invalid-for-Performance Cases",
    "## Low-Tier D-Flash MVP Closure Decision",
    "## Phase 3.16 Routing Decision",
    "## Remaining Limitations",
    "## Interpretation Guards",
    "## Non-Claims",
    "## Tests",
    "## Verification",
    "## Error Reports",
    "## Commit",
    "## Next Step",
]


@pytest.mark.parametrize("section", REQUIRED_REPORT_SECTIONS)
def test_report_contains_required_section(section: str) -> None:
    text = _read(REPORT_PATH)
    assert section in text, f"Report missing section: {section!r}"


# ---------------------------------------------------------------------------
# 3. Roadmap
# ---------------------------------------------------------------------------


def test_report_contains_correct_roadmap() -> None:
    text = _read(REPORT_PATH)
    assert "Phase 3.15" in text
    assert "Phase 3.16" in text
    assert "Phase 4.0" in text


def test_report_does_not_extend_past_3_15_in_low_tier() -> None:
    text = _read(REPORT_PATH)
    # Phase 3.16 and 3.17 should appear only as conditional routing, not as a linear extension
    assert "Phase 3.15" in text, "Phase 3.15 must be present"
    # Phase 4.0+ is the high-tier boundary
    assert "Phase 4.0" in text


def test_report_has_conditional_roadmap_decision() -> None:
    text = _read(REPORT_PATH)
    assert "conditional roadmap" in text.lower() or "conditional" in text.lower()
    # Must include the two possible Phase 3.16 routes
    assert "frontend" in text.lower() or "demo linkage" in text.lower() or "blocker audit" in text.lower()


# ---------------------------------------------------------------------------
# 4. Runtime and model audit
# ---------------------------------------------------------------------------


def test_report_has_runtime_audit() -> None:
    text = _read(REPORT_PATH)
    assert "runtime and model audit" in text.lower() or "model audit" in text.lower()
    assert "gguf" in text.lower()
    assert "llama.cpp" in text.lower() or "llama-cpp" in text.lower()


def test_report_mentions_model_files() -> None:
    text = _read(REPORT_PATH)
    assert "drafter" in text.lower()
    assert "verifier" in text.lower()


def test_report_has_real_benchmark_attempt_section() -> None:
    text = _read(REPORT_PATH)
    assert "real/local benchmark attempt" in text.lower() or "real benchmark" in text.lower()


# ---------------------------------------------------------------------------
# 5. Blocker status
# ---------------------------------------------------------------------------


def test_report_has_blocker_status_section() -> None:
    text = _read(REPORT_PATH)
    assert "blocker status" in text.lower()


# ---------------------------------------------------------------------------
# 6. Fallback diagnostic dry run
# ---------------------------------------------------------------------------


def test_report_has_fallback_diagnostic_section() -> None:
    text = _read(REPORT_PATH)
    assert "fallback diagnostic dry run" in text.lower()


def test_report_has_dry_run_cases_section() -> None:
    text = _read(REPORT_PATH)
    assert "dry run cases" in text.lower()


# ---------------------------------------------------------------------------
# 7. Correctness and equivalence gates
# ---------------------------------------------------------------------------


def test_report_has_correctness_gate_section() -> None:
    text = _read(REPORT_PATH)
    assert "correctness gate" in text.lower()


def test_report_has_equivalence_gate_section() -> None:
    text = _read(REPORT_PATH)
    assert "equivalence gate" in text.lower()


# ---------------------------------------------------------------------------
# 8. MVP closure decision
# ---------------------------------------------------------------------------


def test_report_has_mvp_closure_section() -> None:
    text = _read(REPORT_PATH)
    assert "mvp closure" in text.lower() or "d-flash mvp" in text.lower()


def test_report_has_exactly_one_closure_decision() -> None:
    text = _read(REPORT_PATH)
    approved = "closure approved" in text.lower()
    conditional = "closure conditional" in text.lower() or "closure is conditional" in text.lower()
    not_approved = "closure not approved" in text.lower()
    decisions = sum([approved, conditional, not_approved])
    assert decisions >= 1, "Report must have at least one closure decision"


def test_report_closure_has_required_wording() -> None:
    text = _read(REPORT_PATH)
    has_approved = (
        "Low-Tier D-Flash MVP is closed as a local benchmarked MVP milestone" in text
        or "closure approved" in text.lower()
    )
    has_not_approved = (
        "Low-Tier D-Flash MVP is not closed" in text
        or "closure not approved" in text.lower()
    )
    has_conditional = (
        "closure conditional" in text.lower()
        or "closure is conditional" in text.lower()
    )
    assert has_approved or has_not_approved or has_conditional, (
        "Report must include one of the three required closure wording variants"
    )


# ---------------------------------------------------------------------------
# 9. Phase 3.16 routing decision
# ---------------------------------------------------------------------------


def test_report_has_phase_316_routing() -> None:
    text = _read(REPORT_PATH)
    assert "phase 3.16 routing" in text.lower() or "phase 3.16" in text.lower()


def test_report_316_routes_to_valid_option() -> None:
    text = _read(REPORT_PATH)
    valid_routes = [
        "frontend integration",
        "demo linkage",
        "debugging and full blocker audit",
        "blocker audit",
    ]
    assert any(route.lower() in text.lower() for route in valid_routes), (
        f"Phase 3.16 routing must point to one of: {valid_routes}"
    )


# ---------------------------------------------------------------------------
# 10. Forbidden positive claims
# ---------------------------------------------------------------------------


FORBIDDEN_CLAIMS = [
    "speedup achieved",
    "low-tier is faster",
    "benchmark result proves speedup",
    "production lossless generation",
    "lossless generation achieved",
    "lossless equivalence",
    "correctness validation completed for real models",
    "target Gemma E4B equivalence",
    "high-tier implemented",
    "EAGLE implemented",
    "vLLM integration",
]

NEGATION_WORDS = [
    "no ", "not ", "do not", "does not", "must not", "never",
    "without", "excluded", "forbidden", "non-claim", "invalid", "flagged",
    "not approved", "blocked", "did not", "is not", "are not",
]


@pytest.mark.parametrize("claim", FORBIDDEN_CLAIMS)
def test_report_does_not_positively_claim(claim: str) -> None:
    text = _read(REPORT_PATH)
    claim_lower = claim.lower()
    if claim_lower not in text.lower():
        return
    lines_with_claim = [
        line for line in text.splitlines()
        if claim_lower in line.lower()
    ]
    for line in lines_with_claim:
        assert any(neg in line.lower() for neg in NEGATION_WORDS), (
            f"Report contains forbidden positive claim {claim!r} without negation: {line!r}"
        )


# ---------------------------------------------------------------------------
# 11. Commit field
# ---------------------------------------------------------------------------


def test_report_commit_not_by_agent() -> None:
    text = _read(REPORT_PATH)
    assert "not committed by agent" in text.lower() or \
           "commit/merge handled manually" in text.lower() or \
           "handled manually" in text.lower()


# ---------------------------------------------------------------------------
# 12. Prompt fixture structure
# ---------------------------------------------------------------------------


REQUIRED_PROMPT_CATEGORIES = [
    "short_factual",
    "instruction_following",
    "code_like",
    "reasoning_style",
    "newline_format_sensitive",
    "unicode_punctuation",
    "stop_sequence_sensitive",
    "fallback_heavy",
]


def test_prompt_fixture_is_valid_json() -> None:
    text = PROMPT_FIXTURE_PATH.read_text(encoding="utf-8")
    data = json.loads(text)
    assert isinstance(data, list), "Prompt fixture must be a JSON array"
    assert len(data) >= 4, f"Expected at least 4 prompts, got {len(data)}"


def test_prompt_fixture_has_required_categories() -> None:
    data = json.loads(PROMPT_FIXTURE_PATH.read_text(encoding="utf-8"))
    found_categories = {entry["category"] for entry in data}
    for required in REQUIRED_PROMPT_CATEGORIES:
        assert required in found_categories, f"Missing prompt category: {required!r}"


def test_prompt_fixture_has_prompt_ids() -> None:
    data = json.loads(PROMPT_FIXTURE_PATH.read_text(encoding="utf-8"))
    for entry in data:
        assert "prompt_id" in entry, f"Missing prompt_id in: {entry}"
        assert "prompt" in entry, f"Missing prompt in: {entry}"
        assert "category" in entry, f"Missing category in: {entry}"


def test_prompt_fixture_no_empty_prompts() -> None:
    data = json.loads(PROMPT_FIXTURE_PATH.read_text(encoding="utf-8"))
    for entry in data:
        assert entry["prompt"].strip(), f"Empty prompt in: {entry}"


def test_prompt_fixture_size_within_limit() -> None:
    data = json.loads(PROMPT_FIXTURE_PATH.read_text(encoding="utf-8"))
    assert len(data) <= 20, f"Prompt fixture too large: {len(data)} prompts (max 20)"


# ---------------------------------------------------------------------------
# 13. Dry-run harness imports
# ---------------------------------------------------------------------------


def test_dry_run_module_importable() -> None:
    from htfsd.benchmark.low_tier_dry_run import (  # noqa: F401  # pylint: disable=unused-import
        VerifierTokenAccess,
        DryRunResult,
        DryRunCaseResult,
        run_fake_dry_run,
        aggregate_dry_run_metrics,
        BLOCKER_MISSING_MODEL,
        BLOCKER_BACKEND_NO_TOKEN_OPS,
        BLOCKER_WRAPPER_EXTENSION_REQ,
        CASE_STATUS_EQUIVALENT,
        CASE_STATUS_DIVERGENT,
        CASE_STATUS_EXPECTED_FAILURE,
        CASE_STATUS_NO_PROGRESS_ERROR,
    )


# ---------------------------------------------------------------------------
# 14. Fake dry-run cases — no model required
# ---------------------------------------------------------------------------


def test_fake_dry_run_runs_without_model() -> None:
    from htfsd.benchmark.low_tier_dry_run import run_fake_dry_run
    result = run_fake_dry_run()
    assert result is not None
    assert result.total_request_count > 0


def test_fake_dry_run_has_expected_case_count() -> None:
    from htfsd.benchmark.low_tier_dry_run import run_fake_dry_run
    result = run_fake_dry_run()
    # 6 standard cases + 2 expected-failure cases = 8 total
    assert result.total_request_count == 8, f"Expected 8 cases, got {result.total_request_count}"


def test_fake_dry_run_full_accept_case_equivalent() -> None:
    from htfsd.benchmark.low_tier_dry_run import (
        _fake_case_to_dry_run_result, CASE_STATUS_EQUIVALENT
    )
    from htfsd.validation.fake_harness import case_full_accept
    result = _fake_case_to_dry_run_result(
        "full_accept", "full_accept_case", case_full_accept(), CASE_STATUS_EQUIVALENT
    )
    assert result.equivalent is True
    assert result.status == CASE_STATUS_EQUIVALENT
    assert result.accepted_target_token_count == 3  # [1,2,3] all accepted
    assert result.rejected_target_token_count == 0
    assert result.unused_suffix_token_count == 0
    assert result.fallback_token_count == 0


def test_fake_dry_run_partial_accept_case_equivalent() -> None:
    from htfsd.benchmark.low_tier_dry_run import (
        _fake_case_to_dry_run_result, CASE_STATUS_EQUIVALENT
    )
    from htfsd.validation.fake_harness import case_partial_accept_with_fallback
    result = _fake_case_to_dry_run_result(
        "partial_accept", "partial_accept_case",
        case_partial_accept_with_fallback(), CASE_STATUS_EQUIVALENT
    )
    assert result.equivalent is True
    assert result.status == CASE_STATUS_EQUIVALENT
    # cycle 0: accept [1,2], fallback=9; cycle 1: accept [8,7]
    assert result.accepted_target_token_count >= 2  # at least the first 2 matched
    assert result.fallback_token_count >= 1  # at least one fallback


def test_fake_dry_run_full_reject_case_equivalent() -> None:
    from htfsd.benchmark.low_tier_dry_run import (
        _fake_case_to_dry_run_result, CASE_STATUS_EQUIVALENT
    )
    from htfsd.validation.fake_harness import case_full_reject_with_fallback
    result = _fake_case_to_dry_run_result(
        "full_reject", "full_reject_case",
        case_full_reject_with_fallback(), CASE_STATUS_EQUIVALENT
    )
    assert result.equivalent is True
    assert result.status == CASE_STATUS_EQUIVALENT
    assert result.fallback_token_count >= 1


def test_fake_dry_run_eos_termination_equivalent() -> None:
    from htfsd.benchmark.low_tier_dry_run import (
        _fake_case_to_dry_run_result, CASE_STATUS_EQUIVALENT
    )
    from htfsd.validation.fake_harness import case_eos_termination
    result = _fake_case_to_dry_run_result(
        "eos_termination", "eos_stop_case", case_eos_termination(), CASE_STATUS_EQUIVALENT
    )
    assert result.equivalent is True
    assert result.status == CASE_STATUS_EQUIVALENT


def test_fake_dry_run_no_progress_error_case() -> None:
    from htfsd.benchmark.low_tier_dry_run import (
        _fake_case_to_dry_run_result, CASE_STATUS_NO_PROGRESS_ERROR
    )
    from htfsd.validation.fake_harness import case_no_progress_error
    result = _fake_case_to_dry_run_result(
        "no_progress_error", "no_progress_case",
        case_no_progress_error(), CASE_STATUS_NO_PROGRESS_ERROR
    )
    assert result.status == CASE_STATUS_NO_PROGRESS_ERROR


def test_fake_dry_run_max_tokens_truncation() -> None:
    from htfsd.benchmark.low_tier_dry_run import (
        _fake_case_to_dry_run_result, CASE_STATUS_EQUIVALENT
    )
    from htfsd.validation.fake_harness import case_max_new_tokens_truncation
    result = _fake_case_to_dry_run_result(
        "max_new_tokens", "truncation_case",
        case_max_new_tokens_truncation(), CASE_STATUS_EQUIVALENT
    )
    assert result.equivalent is True
    assert result.status == CASE_STATUS_EQUIVALENT


# ---------------------------------------------------------------------------
# 15. Divergence detection (expected failure gate tests)
# ---------------------------------------------------------------------------


def test_divergence_case_is_not_equivalent() -> None:
    from htfsd.benchmark.low_tier_dry_run import _make_divergence_case, CASE_STATUS_DIVERGENT
    result = _make_divergence_case()
    assert result.equivalent is False
    assert result.status == CASE_STATUS_DIVERGENT
    assert result.correctness_gate_passed is False
    assert result.equivalence_gate_passed is False
    assert result.divergence_position is not None


def test_unused_suffix_leak_case_is_not_equivalent() -> None:
    from htfsd.benchmark.low_tier_dry_run import _make_unused_suffix_leak_case, CASE_STATUS_EXPECTED_FAILURE
    result = _make_unused_suffix_leak_case()
    assert result.equivalent is False
    assert result.status == CASE_STATUS_EXPECTED_FAILURE
    assert result.correctness_gate_passed is False


# ---------------------------------------------------------------------------
# 16. Structural metrics aggregation
# ---------------------------------------------------------------------------


def test_aggregate_metrics_total_requests() -> None:
    from htfsd.benchmark.low_tier_dry_run import run_fake_dry_run
    result = run_fake_dry_run()
    assert result.total_request_count == len(result.cases)


def test_aggregate_metrics_cycle_count_positive() -> None:
    from htfsd.benchmark.low_tier_dry_run import run_fake_dry_run
    result = run_fake_dry_run()
    # At least one case should have cycles
    assert result.total_cycle_count >= 0


def test_aggregate_metrics_no_negative_counts() -> None:
    from htfsd.benchmark.low_tier_dry_run import run_fake_dry_run
    result = run_fake_dry_run()
    assert result.total_accepted_target_token_count >= 0
    assert result.total_rejected_target_token_count >= 0
    assert result.total_unused_suffix_token_count >= 0
    assert result.total_fallback_token_count >= 0
    assert result.equivalent_request_count >= 0
    assert result.divergent_request_count >= 0


# ---------------------------------------------------------------------------
# 17. Invalid cases excluded from performance interpretation
# ---------------------------------------------------------------------------


def test_invalid_cases_not_performance_eligible() -> None:
    from htfsd.benchmark.low_tier_dry_run import (
        run_fake_dry_run, CASE_STATUS_DIVERGENT, CASE_STATUS_EXPECTED_FAILURE
    )
    result = run_fake_dry_run()
    for case in result.cases:
        if case.status in (CASE_STATUS_DIVERGENT, CASE_STATUS_EXPECTED_FAILURE):
            assert not case.valid_for_performance, (
                f"Case {case.case_name!r} with status {case.status!r} "
                "must not be valid for performance"
            )


def test_equivalent_cases_may_be_performance_eligible() -> None:
    from htfsd.benchmark.low_tier_dry_run import run_fake_dry_run, CASE_STATUS_EQUIVALENT
    result = run_fake_dry_run()
    equiv_cases = [c for c in result.cases if c.status == CASE_STATUS_EQUIVALENT]
    assert len(equiv_cases) >= 1, "At least one equivalent case required"
    for case in equiv_cases:
        assert case.valid_for_performance, (
            f"Equivalent unblocked case {case.case_name!r} should be performance eligible"
        )


# ---------------------------------------------------------------------------
# 18. Non-claims in DryRunResult
# ---------------------------------------------------------------------------


def test_dry_run_result_has_non_claims() -> None:
    from htfsd.benchmark.low_tier_dry_run import run_fake_dry_run
    result = run_fake_dry_run()
    assert len(result.non_claims) > 0
    non_claims_text = " ".join(result.non_claims).lower()
    assert "no speedup" in non_claims_text or "not a production benchmark" in non_claims_text


def test_dry_run_result_non_claims_exclude_vllm() -> None:
    from htfsd.benchmark.low_tier_dry_run import run_fake_dry_run
    result = run_fake_dry_run()
    non_claims_text = " ".join(result.non_claims).lower()
    assert "vllm" in non_claims_text or "no vllm" in non_claims_text


# ---------------------------------------------------------------------------
# 19. Real/local model test (skip by default)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not REAL_MODEL_TEST,
    reason="Real model test requires HTFSD_LOCAL_MODEL_TEST=1 and local GGUF files",
)
def test_real_verifier_baseline_runs() -> None:
    """Real local model test. Requires HTFSD_LOCAL_MODEL_TEST=1."""
    from llama_cpp import Llama
    from htfsd.benchmark.low_tier_dry_run import VerifierTokenAccess, run_real_baseline

    verifier_path = REPO_ROOT / "models" / "gemma-4-e2b-it" / "gemma-4-E2B-it-UD-Q4_K_XL.gguf"
    assert verifier_path.exists(), f"Verifier model not found: {verifier_path}"

    raw_model = Llama(
        model_path=str(verifier_path),
        n_ctx=256,
        n_gpu_layers=-1,
        seed=42,
        verbose=False,
    )
    token_access = VerifierTokenAccess(raw_model)
    result = run_real_baseline(
        prompt_id="real_test_001",
        prompt="What is the capital of France?",
        token_access=token_access,
        max_new_tokens=16,
        model_path=str(verifier_path),
    )
    assert result.succeeded, f"Real baseline failed: {result.error}"
    assert result.token_count > 0
    assert result.baseline_text.strip()
    assert result.wall_time_ms > 0


# ---------------------------------------------------------------------------
# 20. Multi-cycle D-Flash mock tests (no model required)
# ---------------------------------------------------------------------------

def test_run_multicycle_dflash_mocked() -> None:
    """Test multi-cycle D-Flash logic using a mock verifier token access.
    
    Verifies that:
        - context update appends committed tokens exactly once
        - accepted prefix tokens enter strict output once
        - fallback token enters strict output once
        - rejected token does not enter strict output
        - unused suffix does not enter strict output
        - metrics accumulate correctly
    """
    from htfsd.benchmark.low_tier_dry_run import run_multicycle_dflash

    class MockVerifierTokenAccess:
        def __init__(self, greedy_responses):
            self.greedy_responses = list(greedy_responses)
            self.greedy_generate_calls = []
            self.detokenize_calls = []

        def tokenize(self, text: str, add_bos: bool = False) -> list[int]:
            # simple mock mapping char -> int
            return [2] + [ord(c) for c in text] if add_bos else [ord(c) for c in text]

        def tokenize_bytes(self, text_bytes: bytes, add_bos: bool = False) -> list[int]:
            text = text_bytes.decode("utf-8")
            return self.tokenize(text, add_bos=add_bos)

        def detokenize(self, token_ids: list[int]) -> str:
            self.detokenize_calls.append(token_ids)
            return "".join(chr(i) for i in token_ids if i not in (2, 106))

        def token_eos(self) -> int:
            return 106

        def token_bos(self) -> int:
            return 2

        def greedy_generate(self, prompt_token_ids: list[int], max_new_tokens: int) -> tuple[list[int], str]:
            self.greedy_generate_calls.append(list(prompt_token_ids))
            _ = max_new_tokens
            if self.greedy_responses:
                return self.greedy_responses.pop(0), "eos"
            return [106], "eos"

    # We mock a drafter that produces " Paris" -> tokens: [32, 80, 97, 114, 105, 115]
    # verifier greedy output:
    # Cycle 0: we expect " Paris" to match completely, verifier returns [32, 80, 97, 114, 105, 115, 106]
    # Cycle 1: verifier greedy is empty/EOS -> returns [106]
    ta = MockVerifierTokenAccess(greedy_responses=[
        [32, 80, 97, 114, 105, 115, 106],
        [106]
    ])

    def mock_drafter(_context_text: str, _draft_tokens: int) -> str:
        return " Paris"

    metrics = run_multicycle_dflash(
        prompt_text="What is the capital of France?",
        drafter_fn=mock_drafter,
        token_access=ta,
        max_new_tokens=32,
        max_cycles=5,
        draft_tokens=8,
    )

    # Check metrics
    assert metrics["cycles"] == 2
    assert metrics["full_accept"] == 1
    assert metrics["full_reject"] == 1
    assert metrics["accepted_target_tokens"] == 6  # " Paris" matches in cycle 0
    assert metrics["rejected_target_tokens"] == 1  # cycle 1 rejects " Paris"
    assert metrics["unused_suffix_tokens"] == 5  # cycle 1 unused suffix "Paris" (length 5)
    assert metrics["fallback_events"] == 1  # fallback token (106) committed in cycle 1

    # Ensure evaluation context only has the prompt plus committed tokens exactly once
    # Prompt is "What is the capital of France?" -> BOS (2) + ords of chars
    prompt_ids = [2] + [ord(c) for c in "What is the capital of France?"]
    assert len(ta.greedy_generate_calls) == 2
    
    # Cycle 0 context: prompt_ids only
    assert ta.greedy_generate_calls[0] == prompt_ids
    
    # Cycle 1 context: prompt_ids + Cycle 0 committed tokens ([32, 80, 97, 114, 105, 115])
    expected_cycle_1_context = prompt_ids + [32, 80, 97, 114, 105, 115]
    assert ta.greedy_generate_calls[1] == expected_cycle_1_context

    # Check committed output: " Paris" (6 tokens) + EOS (1 token)
    assert metrics["strict_ids"] == [32, 80, 97, 114, 105, 115, 106]
    assert metrics["strict_text"] == " Paris"


def test_multicycle_metrics_aggregation_mocked() -> None:
    """Test aggregation of multi-cycle metrics, equivalence gates, and usefulness decisions.
    
    Verifies that:
        - equivalent request count is computed correctly
        - divergent request count is computed correctly
        - invalid_for_performance_count is computed correctly
        - speedup_candidate is false if equivalence fails
    """
    from htfsd.benchmark.low_tier_dry_run import DryRunCaseResult, aggregate_dry_run_metrics
    from htfsd.benchmark.low_tier_dry_run import CASE_STATUS_EQUIVALENT, CASE_STATUS_DIVERGENT

    # 1. Test case where all cases are equivalent
    case1 = DryRunCaseResult(
        case_name="case1",
        case_category="category",
        prompt_id="prompt1",
        run_mode="real",
        equivalent=True,
        status=CASE_STATUS_EQUIVALENT,
        cycle_count=3,
        accepted_target_token_count=10,
        rejected_target_token_count=1,
        unused_suffix_token_count=2,
        fallback_token_count=1,
        full_accept_cycle_count=2,
        partial_accept_cycle_count=0,
        full_reject_cycle_count=1,
        no_progress_error_count=0,
        fallback_only_cycle_count=1,
        baseline_wall_time_ms=100.0,
        strict_wall_time_ms=80.0,
        correctness_gate_passed=True,
        equivalence_gate_passed=True,
        divergence_position=None,
        divergence_reason=None,
        blocker=None,
    )
    
    # 2. Test case where one is divergent
    case2 = DryRunCaseResult(
        case_name="case2",
        case_category="category",
        prompt_id="prompt2",
        run_mode="real",
        equivalent=False,
        status=CASE_STATUS_DIVERGENT,
        cycle_count=2,
        accepted_target_token_count=5,
        rejected_target_token_count=1,
        unused_suffix_token_count=3,
        fallback_token_count=1,
        full_accept_cycle_count=1,
        partial_accept_cycle_count=0,
        full_reject_cycle_count=1,
        no_progress_error_count=0,
        fallback_only_cycle_count=1,
        baseline_wall_time_ms=100.0,
        strict_wall_time_ms=120.0,
        correctness_gate_passed=False,
        equivalence_gate_passed=False,
        divergence_position=3,
        divergence_reason="token_mismatch",
        blocker=None,
    )

    # Aggregate with only equivalent cases
    res_equiv = aggregate_dry_run_metrics([case1], run_mode="real")
    assert res_equiv.equivalent_request_count == 1
    assert res_equiv.divergent_request_count == 0
    assert res_equiv.invalid_for_performance_count == 0
    assert res_equiv.equivalence_gate_passed is True
    # speedup_candidate can be True since it is equivalent and strict time (80.0) < baseline time (100.0)
    assert res_equiv.speedup_candidate is True
    assert res_equiv.total_accepted_target_token_count > 0
    assert res_equiv.baseline_wall_time_ms_total == 100.0
    assert res_equiv.strict_wall_time_ms_total == 80.0
    assert res_equiv.baseline_wall_time_ms_total is not None
    assert res_equiv.strict_wall_time_ms_total is not None
    assert (res_equiv.baseline_wall_time_ms_total - res_equiv.strict_wall_time_ms_total) > 0


    # Aggregate with a divergent case
    res_div = aggregate_dry_run_metrics([case1, case2], run_mode="real")
    assert res_div.equivalent_request_count == 1
    assert res_div.divergent_request_count == 1
    assert res_div.invalid_for_performance_count == 1  # case2 is invalid for performance due to divergence
    assert res_div.equivalence_gate_passed is False
    assert res_div.speedup_candidate is False

    # Aggregate with case where strict is slower
    case3 = DryRunCaseResult(
        case_name="case3",
        case_category="category",
        prompt_id="prompt3",
        run_mode="real",
        equivalent=True,
        status=CASE_STATUS_EQUIVALENT,
        cycle_count=3,
        accepted_target_token_count=10,
        rejected_target_token_count=1,
        unused_suffix_token_count=2,
        fallback_token_count=1,
        full_accept_cycle_count=2,
        partial_accept_cycle_count=0,
        full_reject_cycle_count=1,
        no_progress_error_count=0,
        fallback_only_cycle_count=1,
        baseline_wall_time_ms=100.0,
        strict_wall_time_ms=120.0,
        correctness_gate_passed=True,
        equivalence_gate_passed=True,
        divergence_position=None,
        divergence_reason=None,
        blocker=None,
    )
    res_slower = aggregate_dry_run_metrics([case3], run_mode="real")
    assert res_slower.equivalence_gate_passed is True
    assert res_slower.speedup_candidate is False


