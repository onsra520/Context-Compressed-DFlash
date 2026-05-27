"""Shared prompt sets for controlled trace runs."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TracePrompt:
    """One controlled trace prompt."""

    prompt_id: str
    text: str
    prompt_type: str = "trace"
    expected_output_shape: str = "short text"
    risk_notes: str = ""


@dataclass(frozen=True)
class TracePromptSet:
    """Named prompt set for low-tier and baseline traces."""

    prompt_set_id: str
    prompts: tuple[TracePrompt, ...]


DEFAULT_TRACE_PROMPT_SET = TracePromptSet(
    prompt_set_id="phase-1-controlled-trace-v1",
    prompts=(
        TracePrompt("prompt-001", "Explain speculative decoding in one short sentence."),
        TracePrompt("prompt-002", "Write a five word greeting."),
        TracePrompt("prompt-003", "List two benefits of GPU inference."),
    ),
)

PHASE_2_CONTROLLED_ELIGIBILITY_PROMPT_SET = TracePromptSet(
    prompt_set_id="phase-2-controlled-eligibility-v1",
    prompts=(
        TracePrompt("elig-001", "Answer with only: ready", "fixed reply", "single token or short word", "Very constrained."),
        TracePrompt("elig-002", "Write three words about latency.", "short phrase", "three-word phrase", "May include punctuation."),
        TracePrompt("elig-003", "List two colors.", "short list", "two-item list or short phrase", "Low ambiguity."),
        TracePrompt("elig-004", "Define caching in one sentence.", "short definition", "one sentence", "Common concept."),
        TracePrompt(
            "elig-005",
            "Write exactly one short sentence about GPU inference.",
            "short sentence",
            "one short sentence",
            "May not obey exactly.",
        ),
        TracePrompt("elig-006", "Name two common operating systems.", "naming", "two names", "Factual and short."),
        TracePrompt("elig-007", 'Rewrite "fast model" as a short phrase.', "transformation", "short phrase", "Low ambiguity."),
        TracePrompt(
            "elig-008",
            "Complete this sentence: Machine learning is",
            "sentence completion",
            "short completion",
            "Raw continuation friendly.",
        ),
        TracePrompt("elig-009", "Give one benefit of batching.", "short answer", "short sentence or phrase", "Common systems topic."),
        TracePrompt("elig-010", "Reply with a five-word greeting.", "greeting", "five-word greeting", "Compact response."),
        TracePrompt(
            "elig-011",
            "Is CUDA related to CPU or GPU? Answer briefly.",
            "classification",
            "short answer",
            "Low ambiguity.",
        ),
        TracePrompt("elig-012", "Expand the acronym API in one short phrase.", "acronym", "short phrase", "Common acronym."),
        TracePrompt(
            "elig-013",
            "Name one difference between RAM and storage.",
            "contrast",
            "short sentence",
            "General technical prompt.",
        ),
        TracePrompt("elig-014", "Write two words that describe reliability.", "count", "two words", "Compact output."),
        TracePrompt(
            "elig-015",
            'Summarize "small draft model" in three words.',
            "simple summary",
            "three-word phrase",
            "Domain-adjacent but concise.",
        ),
        TracePrompt(
            "elig-016",
            "Finish the phrase: A verifier checks",
            "completion",
            "short completion",
            "Raw continuation friendly.",
        ),
    ),
)

PHASE_2_REFINED_ELIGIBILITY_PROMPT_SET = TracePromptSet(
    prompt_set_id="phase-2-controlled-eligibility-v2",
    prompts=(
        TracePrompt(
            "elig2-001",
            "A short readiness reply is",
            "continuation",
            "short phrase",
            'Replaces forced "Answer with only" shape.',
        ),
        TracePrompt(
            "elig2-002",
            "Latency in one short phrase is",
            "continuation",
            "short phrase",
            "Replaces exact three-word constraint.",
        ),
        TracePrompt(
            "elig2-003",
            "Two common colors are",
            "continuation",
            "short list-like completion",
            "Replaces bare list request.",
        ),
        TracePrompt(
            "elig2-004",
            "Caching means",
            "continuation",
            "short definition",
            "Keeps successful caching topic in continuation form.",
        ),
        TracePrompt(
            "elig2-005",
            "GPU inference is useful because",
            "continuation",
            "short explanatory completion",
            "Replaces exact sentence command.",
        ),
        TracePrompt(
            "elig2-006",
            "Two common operating systems are",
            "continuation",
            "two-name completion",
            "Replaces direct naming command.",
        ),
        TracePrompt(
            "elig2-007",
            "A fast model can be described as",
            "continuation",
            "short phrase",
            "Replaces rewrite command.",
        ),
        TracePrompt(
            "elig2-008",
            "Machine learning is",
            "continuation",
            "short definition or completion",
            "Keeps successful sentence stem.",
        ),
        TracePrompt(
            "elig2-009",
            "Batching helps because",
            "continuation",
            "short explanation",
            "Keeps successful batching topic in continuation form.",
        ),
        TracePrompt(
            "elig2-010",
            "A friendly greeting could be",
            "continuation",
            "short greeting",
            "Replaces exact five-word constraint.",
        ),
        TracePrompt(
            "elig2-011",
            "CUDA is related to",
            "continuation",
            "short technical completion",
            "Replaces direct question.",
        ),
        TracePrompt(
            "elig2-012",
            "API stands for",
            "continuation",
            "acronym expansion",
            "Replaces command-style acronym prompt.",
        ),
        TracePrompt(
            "elig2-013",
            "RAM differs from storage because",
            "continuation",
            "short contrast",
            "Keeps successful RAM/storage topic.",
        ),
        TracePrompt(
            "elig2-014",
            "Reliable systems are usually",
            "continuation",
            "short descriptive completion",
            "Replaces exact two-word constraint.",
        ),
        TracePrompt(
            "elig2-015",
            "A small draft model is",
            "continuation",
            "short description",
            "Replaces exact three-word summary.",
        ),
        TracePrompt(
            "elig2-016",
            "A verifier checks",
            "continuation",
            "short completion",
            "Keeps successful verifier stem.",
        ),
    ),
)

MANUAL_LOW_TIER_TEST_PROMPT_SET = TracePromptSet(
    prompt_set_id="manual-low-tier-test-v1",
    prompts=(
        TracePrompt(
            "manual-001",
            "What is AI?",
            "manual test",
            "short answer",
            "Manual low-tier prompt test.",
        ),
    ),
)

TRACE_PROMPT_SETS = {
    DEFAULT_TRACE_PROMPT_SET.prompt_set_id: DEFAULT_TRACE_PROMPT_SET,
    PHASE_2_CONTROLLED_ELIGIBILITY_PROMPT_SET.prompt_set_id: PHASE_2_CONTROLLED_ELIGIBILITY_PROMPT_SET,
    PHASE_2_REFINED_ELIGIBILITY_PROMPT_SET.prompt_set_id: PHASE_2_REFINED_ELIGIBILITY_PROMPT_SET,
    MANUAL_LOW_TIER_TEST_PROMPT_SET.prompt_set_id: MANUAL_LOW_TIER_TEST_PROMPT_SET,
}


def default_trace_prompts() -> tuple[TracePrompt, ...]:
    """Return the default controlled trace prompts."""

    return DEFAULT_TRACE_PROMPT_SET.prompts


def default_trace_prompt_texts() -> tuple[str, ...]:
    """Return only prompt text for compatibility with older callers."""

    return tuple(prompt.text for prompt in DEFAULT_TRACE_PROMPT_SET.prompts)


def get_trace_prompt_set(prompt_set_id: str) -> TracePromptSet:
    """Return a named prompt set or raise a clear error."""

    try:
        return TRACE_PROMPT_SETS[prompt_set_id]
    except KeyError as error:
        available = ", ".join(trace_prompt_set_ids())
        raise ValueError(f"Unknown prompt set '{prompt_set_id}'. Available prompt sets: {available}") from error


def trace_prompt_set_ids() -> tuple[str, ...]:
    """Return available prompt set identifiers in stable order."""

    return tuple(TRACE_PROMPT_SETS)
