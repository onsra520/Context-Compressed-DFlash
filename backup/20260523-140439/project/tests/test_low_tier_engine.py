from importlib import import_module

from low_tier.engine import LowTierEngine
from tokenization.gemma import RetokenizedDraft

_types = import_module("htfsd_types")
TokenResult = _types.TokenResult
VerificationResult = _types.VerificationResult


class FakeTokenizer:
    @property
    def eos_token_id(self) -> int | None:
        return 0

    def encode_prompt(self, prompt: str) -> list[int]:
        return [ord(char) for char in prompt]

    def retokenize_draft(self, draft_text: str, *, max_tokens: int) -> RetokenizedDraft:
        token_ids = [ord(char) for char in draft_text][:max_tokens]
        return RetokenizedDraft(token_ids=token_ids, empty=len(token_ids) == 0)

    def decode(self, token_ids: list[int]) -> str:
        return "".join(chr(token_id) for token_id in token_ids if token_id != 0)


class SequenceDrafter:
    def __init__(self, outputs):
        self.outputs = list(outputs)

    def draft(self, context_text: str, *, max_tokens: int) -> str:
        if self.outputs:
            return self.outputs.pop(0)
        return '{"draft_text":"x"}'


class FakeVerifier:
    def __init__(self, verification_results, fallback_tokens):
        self.verification_results = list(verification_results)
        self.fallback_tokens = list(fallback_tokens)

    def verify_greedy_prefix(
        self,
        context_token_ids: list[int],
        candidate_token_ids: list[int],
    ) -> VerificationResult:
        return self.verification_results.pop(0)

    def greedy_next_token(self, context_token_ids: list[int]) -> TokenResult:
        token_id = self.fallback_tokens.pop(0)
        return TokenResult(token_id=token_id, text=chr(token_id), is_eos=token_id == 0)


def test_engine_accepts_full_match_without_fallback():
    engine = LowTierEngine(
        drafter=SequenceDrafter(['{"draft_text":"ab"}']),
        verifier=FakeVerifier(
            [VerificationResult([97, 98], None, None, True)],
            fallback_tokens=[],
        ),
        tokenizer=FakeTokenizer(),
        execution_mode="concurrent",
        default_draft_max_tokens=8,
        hard_draft_max_tokens=16,
    )

    result = engine.generate("P", max_new_tokens=2, decoding="greedy")

    assert result.text == "Pab"
    assert result.token_ids[-2:] == [97, 98]
    assert result.metrics.accepted_tokens == 2
    assert result.metrics.fallback_tokens == 0
    assert result.trace[0].candidate_exhausted is True


def test_engine_fallbacks_on_immediate_reject_and_continues():
    engine = LowTierEngine(
        drafter=SequenceDrafter(['{"draft_text":"z"}', '{"draft_text":"b"}']),
        verifier=FakeVerifier(
            [
                VerificationResult([], 122, 0, False),
                VerificationResult([98], None, None, True),
            ],
            fallback_tokens=[97],
        ),
        tokenizer=FakeTokenizer(),
        execution_mode="concurrent",
        default_draft_max_tokens=8,
        hard_draft_max_tokens=16,
    )

    result = engine.generate("P", max_new_tokens=2, decoding="greedy")

    assert result.text == "Pab"
    assert result.metrics.fallback_tokens == 1
    assert result.metrics.accepted_tokens == 1
    assert result.trace[0].reject_position == 0
    assert result.trace[0].fallback_used is True


def test_engine_appends_partial_accept_then_fallback_on_reject():
    engine = LowTierEngine(
        drafter=SequenceDrafter(['{"draft_text":"az"}']),
        verifier=FakeVerifier(
            [VerificationResult([97], 122, 1, False)],
            fallback_tokens=[98],
        ),
        tokenizer=FakeTokenizer(),
        execution_mode="concurrent",
        default_draft_max_tokens=8,
        hard_draft_max_tokens=16,
    )

    result = engine.generate("P", max_new_tokens=2, decoding="greedy")

    assert result.text == "Pab"
    assert result.metrics.accepted_tokens == 1
    assert result.metrics.fallback_tokens == 1
    assert result.trace[0].reject_position == 1
    assert result.trace[0].candidate_exhausted is False
    assert result.trace[0].fallback_used is True


def test_engine_stops_on_eos_in_accepted_prefix():
    engine = LowTierEngine(
        drafter=SequenceDrafter(['{"draft_text":"a\\u0000x"}']),
        verifier=FakeVerifier(
            [VerificationResult([97, 0, 120], None, None, True)],
            fallback_tokens=[],
        ),
        tokenizer=FakeTokenizer(),
        execution_mode="concurrent",
        default_draft_max_tokens=8,
        hard_draft_max_tokens=16,
    )

    result = engine.generate("P", max_new_tokens=5, decoding="greedy", stop_on_eos=True)

    assert result.token_ids[-1] == 0
    assert result.token_ids == [80, 97, 0]
    assert result.metrics.accepted_tokens == 2
    assert result.metrics.fallback_tokens == 0
    assert result.metrics.cycles == 1
    assert result.trace[0].accepted_tokens == 2
    assert result.trace[0].fallback_used is False


def test_engine_fallbacks_on_malformed_dflash():
    engine = LowTierEngine(
        drafter=SequenceDrafter(["not json"]),
        verifier=FakeVerifier([], fallback_tokens=[97]),
        tokenizer=FakeTokenizer(),
        execution_mode="concurrent",
        default_draft_max_tokens=8,
        hard_draft_max_tokens=16,
    )

    result = engine.generate("P", max_new_tokens=1, decoding="greedy")

    assert result.text == "Pa"
    assert result.metrics.malformed_dflash_count == 1
    assert result.metrics.dflash_parse_fail_count == 1
    assert result.metrics.fallback_tokens == 1


def test_engine_stops_on_eos_fallback():
    engine = LowTierEngine(
        drafter=SequenceDrafter(["not json"]),
        verifier=FakeVerifier([], fallback_tokens=[0]),
        tokenizer=FakeTokenizer(),
        execution_mode="concurrent",
        default_draft_max_tokens=8,
        hard_draft_max_tokens=16,
    )

    result = engine.generate("P", max_new_tokens=5, decoding="greedy", stop_on_eos=True)

    assert result.token_ids[-1] == 0
    assert result.metrics.generated_tokens == 1
