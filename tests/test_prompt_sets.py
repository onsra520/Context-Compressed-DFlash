from htfsd.metrics.prompt_sets import (
    DEFAULT_TRACE_PROMPT_SET,
    get_trace_prompt_set,
    trace_prompt_set_ids,
)


def test_prompt_registry_contains_default_trace_set():
    prompt_set = get_trace_prompt_set("phase-1-controlled-trace-v1")

    assert prompt_set is DEFAULT_TRACE_PROMPT_SET
    assert prompt_set.prompt_set_id == "phase-1-controlled-trace-v1"
    assert [prompt.prompt_id for prompt in prompt_set.prompts] == ["prompt-001", "prompt-002", "prompt-003"]


def test_prompt_registry_contains_phase_2_controlled_eligibility_set():
    prompt_set = get_trace_prompt_set("phase-2-controlled-eligibility-v1")

    assert prompt_set.prompt_set_id == "phase-2-controlled-eligibility-v1"
    assert len(prompt_set.prompts) == 16
    assert [prompt.prompt_id for prompt in prompt_set.prompts] == [f"elig-{index:03d}" for index in range(1, 17)]
    assert prompt_set.prompts[0].text == "Answer with only: ready"
    assert prompt_set.prompts[-1].text == "Finish the phrase: A verifier checks"


def test_prompt_registry_contains_phase_2_refined_eligibility_set():
    prompt_set = get_trace_prompt_set("phase-2-controlled-eligibility-v2")

    assert prompt_set.prompt_set_id == "phase-2-controlled-eligibility-v2"
    assert len(prompt_set.prompts) == 16
    assert [prompt.prompt_id for prompt in prompt_set.prompts] == [f"elig2-{index:03d}" for index in range(1, 17)]
    assert [prompt.text for prompt in prompt_set.prompts] == [
        "A short readiness reply is",
        "Latency in one short phrase is",
        "Two common colors are",
        "Caching means",
        "GPU inference is useful because",
        "Two common operating systems are",
        "A fast model can be described as",
        "Machine learning is",
        "Batching helps because",
        "A friendly greeting could be",
        "CUDA is related to",
        "API stands for",
        "RAM differs from storage because",
        "Reliable systems are usually",
        "A small draft model is",
        "A verifier checks",
    ]


def test_prompt_registry_reports_available_ids():
    assert trace_prompt_set_ids() == (
        "phase-1-controlled-trace-v1",
        "phase-2-controlled-eligibility-v1",
        "phase-2-controlled-eligibility-v2",
    )


def test_unknown_prompt_set_raises_clear_error():
    try:
        get_trace_prompt_set("missing-set")
    except ValueError as error:
        message = str(error)
        assert "Unknown prompt set" in message
        assert "missing-set" in message
        assert "phase-2-controlled-eligibility-v1" in message
    else:
        raise AssertionError("expected unknown prompt set to fail")
