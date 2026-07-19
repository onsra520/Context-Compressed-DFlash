from dataclasses import replace

import pytest

from ccdf.compression.safeguard import (
    safeguard_prompt,
    safeguard_prompt_batch,
    segment_prompt,
    validate_safeguard,
)
from ccdf.compression.fact_validation import extract_fact_inventory, validate_facts


def _compress(text: str) -> str:
    replacements = {
        "briefly": "",
        "carefully": "",
        "essential": "",
        "the": "",
    }
    words = text.split()
    return " ".join(word for word in words if word.lower().strip(",.") not in replacements)


def test_batch_safeguard_preserves_span_mapping_and_matches_scalar_result() -> None:
    prompt = "Briefly summarize the background. What is the final result?"
    scalar = safeguard_prompt(prompt, _compress)
    batch = safeguard_prompt_batch(prompt, lambda values: [_compress(value) for value in values])

    assert batch.reconstructed_prompt == scalar.reconstructed_prompt
    assert batch.compressed_spans == scalar.compressed_spans
    assert batch.validation == scalar.validation


def test_contraction_apostrophes_are_not_treated_as_quoted_literals() -> None:
    prompt = "They don't think it's necessary. What changed?"
    result = safeguard_prompt(prompt, _compress)

    assert result.validation.checks["preserve_literal"]
    assert result.validation.passed


def test_compression_preserves_punctuation_at_protected_word_boundary() -> None:
    prompt = "Background detail, then, provide the final result. What changed?"
    result = safeguard_prompt(prompt, lambda _text: "possibly useful")

    assert "then," in result.reconstructed_prompt
    assert result.validation.checks["preserve_relation"]
    assert result.validation.checks["preserve_time"]


def test_segmentation_is_contiguous_ordered_and_covers_original() -> None:
    prompt = (
        "A box has 18 red balls and 7 blue balls. Five red balls are removed. "
        "How many balls remain? Briefly show the essential calculation, then end with "
        "exactly `Final answer: <result>`."
    )
    spans = segment_prompt(prompt)

    assert "".join(span.text for span in spans) == prompt
    assert [(span.index, span.start, span.end) for span in spans] == [
        (index, span.start, span.end) for index, span in enumerate(spans)
    ]
    assert any(span.protected for span in spans)
    assert any(not span.protected for span in spans)


def test_numbers_operators_units_and_relations_are_preserved() -> None:
    prompt = (
        "A tank contains 240 liters. Thirty-five percent is used, then 60 liters are added. "
        "Compute 240 - 35% + 60. Briefly explain, then end with `Final answer: <result> liters`."
    )
    result = safeguard_prompt(prompt, _compress)

    assert result.validation.passed, result.validation.failure_reasons
    for value in ("240", "35%", "60", "-", "+", "liters", "used", "added", "then"):
        assert value.lower() in result.reconstructed_prompt.lower()


def test_negation_and_logic_are_preserved() -> None:
    prompt = (
        "If no students are absent, do not subtract anyone; otherwise remove only the absent count. "
        "How many remain? Briefly explain, then return exactly `Final answer: <count>`."
    )
    result = safeguard_prompt(prompt, _compress)

    assert result.validation.passed, result.validation.failure_reasons
    for value in ("If", "no", "not", "otherwise", "remove", "only", "remain"):
        assert value.lower() in result.reconstructed_prompt.lower()


def test_increase_decrease_add_remove_are_preserved() -> None:
    prompt = (
        "Increase the length by 3 m, decrease the width by 2 m, add 4 m, and remove 1 m. "
        "Find the final size. Briefly explain, then end with `Final answer: <size> m`."
    )
    result = safeguard_prompt(prompt, _compress)

    assert result.validation.passed, result.validation.failure_reasons
    for value in ("Increase", "decrease", "add", "remove", "3", "2", "4", "1", "m"):
        assert value.lower() in result.reconstructed_prompt.lower()


def test_time_duration_stop_and_order_are_preserved() -> None:
    prompt = (
        "Travel for 2 hours, stop for 30 minutes, then continue after the break. "
        "Find elapsed time. Carefully explain, then end with `Final answer: <hours> hours`."
    )
    result = safeguard_prompt(prompt, _compress)

    assert result.validation.passed, result.validation.failure_reasons
    for value in ("2 hours", "stop", "30 minutes", "then", "after", "elapsed time"):
        assert value.lower() in result.reconstructed_prompt.lower()


def test_output_format_and_required_literal_are_exact() -> None:
    literal = "`Final answer: total distance <value> km; elapsed time <value> hours`"
    prompt = f"Find total distance and elapsed time. Briefly calculate, then end with exactly {literal}."
    result = safeguard_prompt(prompt, _compress)

    assert result.validation.passed, result.validation.failure_reasons
    assert literal in result.reconstructed_prompt
    output_spans = [span for span in result.spans if "output_constraint" in span.reasons]
    assert output_spans
    assert all(span.protected for span in output_spans)


def test_imperative_instruction_is_exact_while_style_adverb_is_compressible() -> None:
    prompt = (
        "A store sells pens for $2. What is the price of 5 pens? "
        "Briefly show the essential calculation, then return exactly `Final answer: <price>`."
    )
    result = safeguard_prompt(prompt, lambda text: text.replace("Briefly", "").strip())

    assert result.validation.passed, result.validation.failure_reasons
    assert "show the essential calculation" in result.reconstructed_prompt
    assert "Briefly" not in result.reconstructed_prompt


def test_reconstruction_uses_original_span_order() -> None:
    prompt = "Compute 7 + 5. Briefly explain, then return exactly `Final answer: <result>`."
    result = safeguard_prompt(prompt, lambda text: text.replace("Briefly", "").strip())

    assert result.validation.passed, result.validation.failure_reasons
    cursor = 0
    for span in (span for span in result.spans if span.protected):
        position = result.reconstructed_prompt.find(span.text, cursor)
        assert position >= cursor
        cursor = position + len(span.text)


def test_validation_fails_when_protected_number_is_changed() -> None:
    prompt = "Compute 7 + 5. Briefly explain, then return exactly `Final answer: <result>`."
    result = safeguard_prompt(prompt, _compress)
    changed = result.reconstructed_prompt.replace("7", "8", 1)
    validation = validate_safeguard(prompt, changed, result.spans, result.compressed_spans)

    assert not validation.passed
    assert "protected_spans_exact_and_ordered" in validation.failure_reasons
    assert "preserve_number" in validation.failure_reasons


def test_validation_fails_when_protected_spans_are_reordered() -> None:
    prompt = "Compute 7 + 5. Briefly explain, then return exactly `Final answer: <result>`."
    result = safeguard_prompt(prompt, _compress)
    protected = [span for span in result.spans if span.protected]
    assert len(protected) >= 2
    reordered = result.reconstructed_prompt.replace(protected[0].text, "", 1) + protected[0].text
    validation = validate_safeguard(prompt, reordered, result.spans, result.compressed_spans)

    assert not validation.passed
    assert "protected_spans_exact_and_ordered" in validation.failure_reasons


def test_noop_compressor_is_safe_but_records_compression_diagnostic() -> None:
    prompt = "Compute 7 + 5. Briefly explain, then return exactly `Final answer: <result>`."
    result = safeguard_prompt(prompt, lambda text: text)

    assert result.validation.passed
    assert result.validation.failure_reasons == ()
    assert result.validation.diagnostic_failures == ("effective_compression",)


@pytest.mark.parametrize(
    ("text", "category", "expected"),
    [
        ("Greg found $20.", "currencies", "$20"),
        ("Greg found $20, then left.", "currencies", "$20"),
        ("The length is 3.5 m.", "numbers", "3.5"),
        ("There are 1,200 items.", "numbers", "1,200"),
        ("Use 20% now.", "percentages", "20%"),
    ],
)
def test_independent_number_extraction_excludes_sentence_punctuation(
    text: str, category: str, expected: str
) -> None:
    assert expected in extract_fact_inventory(text)[category]


@pytest.mark.parametrize(
    "phrase",
    [
        "a quarter of the pieces",
        "a third of the remaining pieces",
        "one half of each box",
        "two-thirds per group",
        "three-quarters of the items left",
        "decreased by 5",
        "stopped for 30 minutes",
    ],
)
def test_written_fraction_relation_and_duration_spans_are_preserved(phrase: str) -> None:
    prompt = f"Greg found $20. He used {phrase}. What is left? Return exactly `Final answer: <value>`."
    result = safeguard_prompt(prompt, lambda _text: "discarded")

    assert result.validation.passed, result.validation.failure_reasons
    assert phrase in result.reconstructed_prompt
    assert "$20." in result.reconstructed_prompt


def test_independent_fact_validator_fails_on_lost_currency_and_fraction_relation() -> None:
    original = "Greg found $20. He used a third of the remaining pieces."
    broken = "Greg found. He used pieces."
    validation = validate_facts(original, broken)

    assert not validation.passed
    assert "$20" in validation.missing["currencies"]
    assert "a third" in validation.missing["written_fractions"]
    assert "remaining" in validation.missing["relations"]
