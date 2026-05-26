"""Timing-readiness schema for low-tier diagnostic benchmark preparation."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

from htfsd.metrics.generation_settings import GenerationSettings
from htfsd.metrics.prompt_sets import PHASE_2_REFINED_ELIGIBILITY_PROMPT_SET


MVP_NAME = "Low-Tier Diagnostic MVP v0.1"
DEFAULT_RUN_KIND = "benchmark_readiness_scaffold"
DEFAULT_RUNTIME_BACKEND = "llama.cpp"
DEFAULT_CONFIG_PATH = "configs/local.example.yaml"

TIMING_CATEGORIES: tuple[str, ...] = (
    "valid_draft_continuation",
    "fallback_after_rejection",
    "fallback_only",
    "unknown_contribution",
    "eligible_valid_draft_record",
    "excluded_fallback_derived_record",
    "excluded_empty_baseline_record",
    "excluded_unknown_contribution_record",
)

BLOCK_CYCLE_TIMING_CATEGORIES: tuple[str, ...] = (
    "bridge_valid_block",
    "bridge_rejected_block",
    "cycle_fallback",
    "cycle_no_fallback",
)

BLOCK_CYCLE_INTERPRETATION_GUARDS: tuple[str, ...] = (
    "bridge_valid_block_count is a bridge-level structural diagnostic count only.",
    "It is not accepted block count.",
    "It is not accepted token count.",
    "It is not acceptance-rate evidence.",
    "It is not target-equivalence evidence.",
    "cycle_fallback_count is a cycle-level fallback count only.",
    "It is not correctness evidence.",
    "It is not performance evidence.",
    "It is not benchmark evidence.",
    "It is not a quality score.",
)

NON_CLAIMS: tuple[str, ...] = (
    "This is not a benchmark report.",
    "This is not a performance comparison.",
    "No speedup claim is made.",
    "No performance-improvement claim is made.",
    "No output parity claim is made.",
    "No target-equivalence claim is made.",
    "No correctness claim is made.",
    "No lossless-generation claim is made.",
    "No draft-acceptance metric is reported.",
    "No high-tier implementation claim is made.",
)


@dataclass(frozen=True)
class TimingBoundary:
    """Named timing boundaries for readiness artifacts."""

    environment_check_time_seconds: float | None = None
    model_discovery_time_seconds: float | None = None
    model_load_time_seconds: float | None = None
    prompt_preparation_time_seconds: float | None = None
    drafter_generation_time_seconds: float | None = None
    bridge_normalization_time_seconds: float | None = None
    verifier_continuation_time_seconds: float | None = None
    baseline_generation_time_seconds: float | None = None
    selection_or_diagnostic_time_seconds: float | None = None
    generation_time_seconds: float | None = None
    diagnostic_overhead_seconds: float | None = None
    total_wall_time_seconds: float | None = None

    def to_dict(self) -> dict[str, float | None]:
        """Return JSON-friendly timing data."""

        return asdict(self)


@dataclass(frozen=True)
class TimingCategorySummary:
    """Fallback-aware timing category summary."""

    category: str
    record_count: int = 0
    prompt_ids: list[str] = field(default_factory=list)
    generation_time_seconds_summary: dict[str, float | int | None] = field(default_factory=dict)
    tokens_per_second_descriptive_summary: dict[str, float | int | None] = field(default_factory=dict)
    fallback_count_total: int = 0
    draft_valid_count_total: int = 0
    draft_rejected_count_total: int = 0
    selection_category_count: int = 0
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-friendly category data."""

        return asdict(self)


@dataclass(frozen=True)
class TimingRepetitionSummary:
    """One dry-run repetition summary."""

    repetition_id: str
    trace_kind: str
    cycle_trace_path: str | None
    started_at_utc: str
    ended_at_utc: str
    total_wall_time_seconds: float | None
    generation_time_seconds: float | None
    diagnostic_overhead_seconds: float | None
    trace_records: int
    total_cycles: int
    bridge_valid_block_count: int
    bridge_rejected_block_count: int
    cycle_fallback_count: int

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-friendly repetition data."""

        return asdict(self)


@dataclass(frozen=True)
class TimingSummary:
    """Trace-level timing-readiness summary."""

    run_id: str
    run_kind: str
    boundaries: TimingBoundary
    category_summaries: list[TimingCategorySummary]
    tokens_per_second_descriptive: float | None = None
    latency_seconds_descriptive: float | None = None
    total_prompt_tokens: int | None = None
    total_completion_tokens: int | None = None
    trace_kind: str | None = None
    dry_run: bool = False
    repetitions_requested: int | None = None
    prompt_set_id: str | None = None
    prompt_count: int | None = None
    prompt_mode: str | None = None
    draft_block_size: int | None = None
    max_cycles: int | None = None
    capture_raw_output: bool | None = None
    cycle_trace_artifact_paths: list[str] = field(default_factory=list)
    repetition_summaries: list[TimingRepetitionSummary] = field(default_factory=list)
    interpretation_guards: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-friendly summary data."""

        return {
            "run_id": self.run_id,
            "run_kind": self.run_kind,
            "boundaries": self.boundaries.to_dict(),
            "category_summaries": [summary.to_dict() for summary in self.category_summaries],
            "tokens_per_second_descriptive": self.tokens_per_second_descriptive,
            "latency_seconds_descriptive": self.latency_seconds_descriptive,
            "total_prompt_tokens": self.total_prompt_tokens,
            "total_completion_tokens": self.total_completion_tokens,
            "trace_kind": self.trace_kind,
            "dry_run": self.dry_run,
            "repetitions_requested": self.repetitions_requested,
            "prompt_set_id": self.prompt_set_id,
            "prompt_count": self.prompt_count,
            "prompt_mode": self.prompt_mode,
            "draft_block_size": self.draft_block_size,
            "max_cycles": self.max_cycles,
            "capture_raw_output": self.capture_raw_output,
            "cycle_trace_artifact_paths": self.cycle_trace_artifact_paths,
            "repetition_summaries": [summary.to_dict() for summary in self.repetition_summaries],
            "interpretation_guards": self.interpretation_guards,
        }


@dataclass(frozen=True)
class RunManifest:
    """Run manifest for benchmark-readiness artifacts."""

    run_id: str
    created_at_utc: str
    run_kind: str
    mvp_name: str
    prompt_set_id: str
    prompt_count: int
    prompt_mode: str
    capture_raw_output: bool
    generation_settings: dict[str, Any]
    config_path: str
    git_commit: str
    runtime_backend: str
    environment_snapshot: dict[str, Any]
    artifact_paths: dict[str, str]
    non_claims: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-friendly manifest data."""

        return asdict(self)


def default_generation_settings_metadata() -> dict[str, Any]:
    """Return deterministic trace-safe settings for readiness manifests."""

    return GenerationSettings(
        max_tokens=64,
        temperature=0.0,
        seed=42,
        stop=None,
        prompt_mode="raw",
        capture_raw_output=False,
    ).to_metadata()


def create_run_manifest(
    *,
    run_id: str,
    artifact_paths: dict[str, str],
    environment_snapshot: dict[str, Any],
    run_kind: str = DEFAULT_RUN_KIND,
    config_path: str = DEFAULT_CONFIG_PATH,
    runtime_backend: str = DEFAULT_RUNTIME_BACKEND,
    created_at_utc: str | None = None,
) -> RunManifest:
    """Create a default benchmark-readiness run manifest."""

    prompt_set = PHASE_2_REFINED_ELIGIBILITY_PROMPT_SET
    return RunManifest(
        run_id=run_id,
        created_at_utc=created_at_utc or datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        run_kind=run_kind,
        mvp_name=MVP_NAME,
        prompt_set_id=prompt_set.prompt_set_id,
        prompt_count=len(prompt_set.prompts),
        prompt_mode="raw",
        capture_raw_output=False,
        generation_settings=default_generation_settings_metadata(),
        config_path=config_path,
        git_commit=str(environment_snapshot.get("git_commit") or "unknown"),
        runtime_backend=runtime_backend,
        environment_snapshot=environment_snapshot,
        artifact_paths=artifact_paths,
        non_claims=list(NON_CLAIMS),
    )
