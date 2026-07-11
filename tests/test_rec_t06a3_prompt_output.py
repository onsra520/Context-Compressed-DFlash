import torch

from ccdf.evaluation.gsm8k import evaluate
from ccdf.inference.output_contract import (
    OutputContractState,
    analyze_output_health,
    first_final_answer,
)
from ccdf.prompts.contracts import audit_encoded_prompt
from ccdf.prompts.encoder import encode_prompt
from ccdf.prompts.renderer import render_prompt
from ccdf.prompts.schemas import PromptParts


class FakeTokenizer:
    def __init__(self):
        self.fragments = {}
        self.last_kwargs = None

    def apply_chat_template(self, messages, **kwargs):
        self.last_kwargs = kwargs
        # Stable synthetic IDs; content identity is tested separately.
        return torch.tensor([[10, 11, 12]])

    def decode(self, ids, skip_special_tokens=True):
        return "".join(self.fragments.get(int(token), "") for token in ids)


def test_gsm8k_is_not_rendered_as_meeting() -> None:
    parts = PromptParts(
        context="",
        question="2+2?",
        instruction='End with "Final answer: <number>".',
    )
    text = render_prompt(parts, "gsm8k")
    assert "Problem:" in text
    assert "Meeting transcript:" not in text


def test_chat_template_and_thinking_contract() -> None:
    tokenizer = FakeTokenizer()
    policy = 'End with "Final answer: <number>".'
    parts = PromptParts(context="", question="2+2?", instruction=policy, system="system")
    encoded = encode_prompt(
        tokenizer,
        parts=parts,
        dataset="gsm8k",
        enable_thinking=False,
        device="cpu",
    )
    audit = audit_encoded_prompt(encoded, policy)
    assert tokenizer.last_kwargs["enable_thinking"] is False
    assert tokenizer.last_kwargs["add_generation_prompt"] is True
    assert audit["pass"] is True
    assert audit["policy_occurrence"] == 1


def test_gsm8k_contract_waits_for_stable_answer_boundary() -> None:
    tokenizer = FakeTokenizer()
    tokenizer.fragments = {
        1: "Reasoning.\nFinal answer: ",
        2: "1",
        3: "8",
        4: ".",
    }
    state = OutputContractState(
        tokenizer=tokenizer,
        dataset="gsm8k",
        stop_token_ids=(99,),
        max_new_tokens=32,
        policy_text="policy",
        settings={},
    )
    assert state.observe([1, 2]).should_stop is False
    # Candidate changes from 1 to 18, so no premature stop.
    assert state.observe([1, 2, 3]).should_stop is False
    decision = state.observe([1, 2, 3, 4])
    assert decision.should_stop is True
    assert decision.stop_reason == "output_contract"
    assert decision.validated_answer == "18"


def test_gsm8k_accepts_final_answer_after_completed_sentence_boundary() -> None:
    text = "The arithmetic is complete. Final answer: 315"
    assert first_final_answer(text) == "315"


def test_gsm8k_rejects_final_answer_words_inside_ordinary_prose() -> None:
    text = "we still need to determine the final answer: 315 before responding"
    assert first_final_answer(text) is None


def test_gsm8k_inline_completed_answer_keeps_wrong_numeric_label() -> None:
    quality = evaluate("The arithmetic is complete. Final answer: 315", "45")
    assert quality["prediction"] == "315"
    assert quality["label"] == "wrong_numeric"


def test_repetition_health() -> None:
    text = " ".join(["alpha beta gamma delta"] * 30)
    health = analyze_output_health(
        text,
        policy_text="unused",
        repetition_min_tokens=20,
        repeated_ngram_size=4,
        repeated_ngram_ratio=0.4,
        instruction_echo_limit=0,
    )
    assert health.repetition_detected is True
