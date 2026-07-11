from types import SimpleNamespace
import sys

import torch


class FakeDynamicCache:
    def __init__(self):
        self.length = 0

    def get_seq_length(self):
        return self.length

    def crop(self, length):
        self.length = int(length)


class FakeTarget:
    def __init__(self):
        self.calls = []
        self.device = torch.device("cpu")

    def __call__(self, input_ids, **kwargs):
        cache = kwargs["past_key_values"]
        cache.length += input_ids.shape[1]
        self.calls.append((input_ids.clone(), kwargs.copy()))
        vocab = 32
        logits = torch.zeros((1, input_ids.shape[1], vocab))
        # Prefill seed=7. Block posterior [11, 13, 17, 19].
        if input_ids.shape[1] == 3:
            logits[:, -1, 7] = 5
        else:
            for index, token in enumerate([11, 13, 17, 19][: input_ids.shape[1]]):
                logits[:, index, token] = 5
        hidden = (
            torch.zeros((1, input_ids.shape[1], 2)),
            torch.ones((1, input_ids.shape[1], 2)),
        )
        return SimpleNamespace(logits=logits, hidden_states=hidden)


def install_fake_transformers(monkeypatch):
    monkeypatch.setitem(sys.modules, "transformers", SimpleNamespace(DynamicCache=FakeDynamicCache))


def test_cached_baseline_position_progression(monkeypatch) -> None:
    install_fake_transformers(monkeypatch)
    from ccdf.inference.cached_target import CachedAutoregressiveState

    model = FakeTarget()
    state = CachedAutoregressiveState(model, torch.tensor([[1, 2, 3]]), 0.0)
    seed = state.prefill()
    assert seed == 7
    state.commit(seed)
    state.next_token(seed)
    _, second = model.calls[1]
    assert second["position_ids"].tolist() == [[3]]
    assert second["attention_mask"].shape[1] == 4


def test_one_forward_block_verification_and_crop(monkeypatch) -> None:
    install_fake_transformers(monkeypatch)
    from ccdf.dflash.verifier import TargetBlockVerifierState

    model = FakeTarget()
    state = TargetBlockVerifierState(model, torch.tensor([[1, 2, 3]]), 0.0, [0])
    seed, hidden = state.prefill()
    assert seed == 7
    assert hidden.shape[1] == 3
    block = torch.tensor([[7, 11, 99, 0]])
    result = state.verify(block_ids=block, start=3, proposal_count=2)
    assert result.accepted_count == 1
    assert result.correction_token_id == 13
    assert result.raw_emitted_tokens == [11, 13]
    assert state.target_block_verification_calls == 1
    assert state.total_target_forward_calls == 2
    assert state.cache_length == 5


class FakeEmbedding:
    def __call__(self, input_ids):
        return torch.zeros((input_ids.shape[0], input_ids.shape[1], 2))


class FakeLMHead:
    def __call__(self, hidden):
        logits = torch.zeros((1, hidden.shape[1], 32))
        for index, token in enumerate([11, 13, 29][: hidden.shape[1]]):
            logits[:, index, token] = 5
        return logits


class FakeGenerationTarget(FakeTarget):
    def __init__(self):
        super().__init__()
        self.model = SimpleNamespace(embed_tokens=FakeEmbedding())
        self.lm_head = FakeLMHead()

    def eval(self):
        return self


class FakeDrafter:
    block_size = 4
    mask_token_id = 31
    target_layer_ids = [0]

    def eval(self):
        return self

    def __call__(self, *, noise_embedding, past_key_values, **kwargs):
        # Three proposal positions for block_size=4.
        past_key_values.length = max(past_key_values.length, 7)
        return torch.zeros((1, noise_embedding.shape[1] - 1, 2))


class FakeOutputTokenizer:
    def decode(self, ids, skip_special_tokens=True):
        return " ".join(str(int(token)) for token in ids if int(token) != 17)


def test_production_dflash_uses_one_target_forward_for_a_block(monkeypatch) -> None:
    install_fake_transformers(monkeypatch)
    from ccdf.dflash.generate import generate_dflash
    from ccdf.inference.schemas import GenerationConfig

    target = FakeGenerationTarget()
    result = generate_dflash(
        target,
        FakeDrafter(),
        FakeOutputTokenizer(),
        torch.tensor([[1, 2, 3]]),
        GenerationConfig(
            max_new_tokens=8,
            stop_token_ids=(17,),
            dataset="qmsum",
            dflash_block_size=4,
        ),
    )

    assert result.generated_token_ids == [7, 11, 13, 17]
    assert result.eos_hit is True
    assert result.target_prefill_calls == 1
    assert result.target_block_verification_calls == 1
    assert result.total_target_forward_calls == 2
    assert result.draft_forward_calls == 1
    assert result.target_seed_tokens == 1
    assert result.emitted_acceptance_lengths == [3]
    assert result.accepted_draft_tokens == 2
    assert result.correction_tokens == 1
    assert result.output_token_count == result.target_seed_tokens + sum(
        result.emitted_acceptance_lengths
    )
    assert all(row["structural_pass"] for row in result.structural_audit)
