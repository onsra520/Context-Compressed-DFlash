from dflash.parser import parse_dflash
from dflash.prompts import build_dflash_prompt


def test_parse_valid_minimal_envelope():
    result = parse_dflash('{"draft_text":"hello world"}')

    assert result.parse_ok is True
    assert result.draft_text == "hello world"
    assert result.confidence is None
    assert result.max_tokens is None


def test_parse_valid_optional_fields():
    result = parse_dflash('{"draft_text":"abc","confidence":0.5,"max_tokens":6}')

    assert result.parse_ok is True
    assert result.confidence == 0.5
    assert result.max_tokens == 6


def test_parse_malformed_json_rejects_without_repair():
    result = parse_dflash('draft_text: "abc"')

    assert result.parse_ok is False
    assert result.error_reason == "parse_fail"
    assert result.draft_text is None


def test_parse_empty_draft_rejects():
    result = parse_dflash('{"draft_text":"   "}')

    assert result.parse_ok is False
    assert result.error_reason == "empty_draft"


def test_parse_crlf_normalization():
    result = parse_dflash('{"draft_text":"a\\r\\nb"}')

    assert result.parse_ok is True
    assert result.draft_text == "a\nb"


def test_parse_invalid_confidence_rejects():
    result = parse_dflash('{"draft_text":"abc","confidence":2}')

    assert result.parse_ok is False
    assert result.error_reason == "schema_invalid"


def test_prompt_requests_json_only():
    prompt = build_dflash_prompt("Say hello", max_tokens=8)

    assert "JSON" in prompt
    assert "draft_text" in prompt
    assert "```" not in prompt
