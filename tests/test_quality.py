import pytest

from ccdf.validation.quality import evaluate_complete_answer


def evaluate(prompt_index: int, text: str, *, stop_reason: str = "eos", output_tokens: int = 32):
    return evaluate_complete_answer(
        prompt_index=prompt_index,
        text=text,
        stop_reason=stop_reason,
        output_tokens=output_tokens,
        max_new_tokens=256,
    )


@pytest.mark.parametrize(
    ("prompt_index", "text"),
    [
        (0, "7 + 5 = 12\nFinal answer: 12"),
        (1, "Reasoning.\nFinal answer: Any number multiplied by zero equals zero."),
        (2, "18 + 7 - 5 = 20\nFinal answer: 20 balls."),
        (3, "Cost is 27.\nFinal answer: $27."),
        (4, "Work.\nFinal answer: total distance 300 km; elapsed time 5.5 hours; average speed about 54.55 km/h."),
        (5, "Work.\nFinal answer: new area 105 square meters; decrease of 3 square meters."),
        (6, "Work.\nFinal answer: 216 liters."),
        (7, "Work.\nFinal answer: attendance 52 students; ratio 7:6."),
        (8, "Work.\nFinal answer: $73.44."),
        (9, "Work.\nFinal answer: total distance 48 km; total time 3.5 hours; average speed about 13.71 km/h."),
    ],
)
def test_quality_accepts_all_locked_answers(prompt_index, text):
    result = evaluate(prompt_index, text)
    assert result.answer_correctness_pass is True
    assert result.completeness_pass is True
    assert result.final_answer_line_format_pass is True
    assert result.fixture_format_compliance_pass is True
    assert result.quality_pass is True


@pytest.mark.parametrize(
    ("prompt_index", "answer"),
    [
        (0, "112"),
        (2, "120 balls"),
        (4, "1300 km; 15.5 hours; 154.55 km/h"),
        (8, "$173.44"),
        (9, "148 km; 13.5 hours; 113.71 km/h"),
    ],
)
def test_numeric_boundaries_reject_substring_matches(prompt_index, answer):
    result = evaluate(prompt_index, f"Final answer: {answer}")
    assert result.answer_correctness_pass is False
    assert result.quality_pass is False


@pytest.mark.parametrize(
    ("prompt_index", "answer"),
    [
        (2, "20"),
        (3, "27 dollars"),
        (4, "300 km, 5.5 hours, 54.55 km/h"),
        (5, "105 m², -3 m²"),
        (6, "216 gallons"),
        (6, "216 ml"),
        (7, "52:7:6"),
        (7, "52 students; 7:6"),
        (8, "73.44 dollars"),
        (9, "48 3.5 13.71"),
        (9, "48 km, 3.5 hours, 13.71 km/h"),
    ],
)
def test_fixture_format_rejects_missing_units_currency_or_labels(prompt_index, answer):
    result = evaluate(prompt_index, f"Final answer: {answer}")
    assert result.fixture_format_compliance_pass is False
    assert result.quality_pass is False


def test_only_last_final_answer_content_is_scored():
    result = evaluate(0, "The intermediate calculation says 12.\nFinal answer: 13")
    assert result.extracted_answer == "13"
    assert result.answer_correctness_pass is False
    assert result.quality_pass is False


def test_duplicate_final_answer_lines_fail_exact_line_format():
    result = evaluate(0, "Final answer: 11\nFinal answer: 12")
    assert result.answer_correctness_pass is True
    assert result.final_answer_line_format_pass is False
    assert result.quality_pass is False


def test_lowercase_final_line_keeps_completeness_separate_from_exact_format():
    result = evaluate(0, "final answer: 12")
    assert result.answer_correctness_pass is True
    assert result.completeness_pass is True
    assert result.final_answer_line_format_pass is False
    assert result.quality_pass is False


def test_correct_answer_at_cap_still_fails_completion_gate():
    result = evaluate(0, "Final answer: 12", stop_reason="max_new_tokens", output_tokens=256)
    assert result.answer_correctness_pass is True
    assert result.completeness_pass is False
    assert result.quality_pass is False


def test_missing_final_line_fails_all_quality_gates():
    result = evaluate(0, "The calculation gives 12.")
    assert result.answer_correctness_pass is False
    assert result.completeness_pass is False
    assert result.final_answer_line_format_pass is False
    assert result.fixture_format_compliance_pass is False
    assert result.quality_pass is False
