import pytest

from tokenization.gemma import GemmaTokenizer, RetokenizedDraft, reject_empty_draft


class FakeTokenizer:
    @property
    def eos_token_id(self) -> int | None:
        return 0

    def encode(self, text: str, add_special_tokens: bool = False) -> list[int]:
        if text == "":
            return []
        return [ord(char) for char in text]

    def decode(self, token_ids: list[int], skip_special_tokens: bool = True) -> str:
        return "".join(chr(token_id) for token_id in token_ids if token_id != self.eos_token_id)


def test_retokenize_non_empty_draft_text():
    tokenizer = GemmaTokenizer(FakeTokenizer())

    result = tokenizer.retokenize_draft("ab", max_tokens=8)

    assert result == RetokenizedDraft(token_ids=[97, 98], empty=False)


def test_retokenize_caps_candidate_tokens():
    tokenizer = GemmaTokenizer(FakeTokenizer())

    result = tokenizer.retokenize_draft("abcd", max_tokens=2)

    assert result.token_ids == [97, 98]


def test_empty_draft_rejected_before_verify():
    with pytest.raises(ValueError, match="empty draft_text"):
        reject_empty_draft("   ")


def test_decode_final_token_ids():
    tokenizer = GemmaTokenizer(FakeTokenizer())

    assert tokenizer.decode([97, 98, 0]) == "ab"
