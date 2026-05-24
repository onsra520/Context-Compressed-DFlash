from htfsd.text_bridge.normalization import normalize_qwen_draft


def test_plain_draft_text_is_valid():
    result = normalize_qwen_draft("The answer is concise.")

    assert result.bridge_status == "valid"
    assert result.normalized_text == "The answer is concise."
    assert result.rejection_reason is None


def test_complete_think_section_is_removed():
    result = normalize_qwen_draft("<think>private reasoning</think>\nFinal answer.")

    assert result.bridge_status == "valid"
    assert result.normalized_text == "Final answer."
    assert result.rejection_reason is None


def test_unclosed_think_section_is_rejected():
    result = normalize_qwen_draft("<think>private reasoning\nFinal answer.")

    assert result.bridge_status == "rejected"
    assert result.normalized_text == ""
    assert result.rejection_reason == "contains_unclosed_think"


def test_empty_after_normalization_is_rejected():
    result = normalize_qwen_draft("<think>private reasoning</think>\n   ")

    assert result.bridge_status == "rejected"
    assert result.normalized_text == ""
    assert result.rejection_reason == "empty_after_normalization"


def test_blank_input_is_rejected():
    result = normalize_qwen_draft("   ")

    assert result.bridge_status == "rejected"
    assert result.normalized_text == ""
    assert result.rejection_reason == "empty_after_normalization"


def test_empty_input_is_rejected():
    result = normalize_qwen_draft("")

    assert result.bridge_status == "rejected"
    assert result.normalized_text == ""
    assert result.rejection_reason == "empty_after_normalization"
