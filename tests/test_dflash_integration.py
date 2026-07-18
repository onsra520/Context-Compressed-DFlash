import importlib
from pathlib import Path
import sys
import types

import torch

from ccdf.config import load_config


ROOT = Path(__file__).resolve().parents[1]


class FakeDynamicCache:
    def __init__(self):
        self.length = 0

    def get_seq_length(self):
        return self.length

    def crop(self, length):
        self.length = int(length)


# The runtime dependency is not installed in the artifact build container.
# Supply only the cache contract needed by this CPU integration test.
sys.modules.setdefault("transformers", types.SimpleNamespace(DynamicCache=FakeDynamicCache))

generate_module = importlib.import_module("ccdf.dflash.generate")
verifier_module = importlib.import_module("ccdf.dflash.verifier")
# Other tests can import the real Transformers package first, making the
# setdefault shim above ineffective. Keep this CPU test's explicit fake cache
# contract independent of module import order.
verifier_module.DynamicCache = FakeDynamicCache
policy_module = importlib.import_module("ccdf.dflash.policy")
schemas_module = importlib.import_module("ccdf.schemas")


class Output:
    def __init__(self, logits, hidden_states):
        self.logits = logits
        self.hidden_states = hidden_states


class Embed(torch.nn.Module):
    def __init__(self, vocab):
        super().__init__()
        self.vocab = vocab

    def forward(self, input_ids):
        return torch.nn.functional.one_hot(input_ids, self.vocab).float()


class Target(torch.nn.Module):
    def __init__(self, vocab=32):
        super().__init__()
        self.anchor = torch.nn.Parameter(torch.zeros(1))
        self.vocab = vocab
        self.model = types.SimpleNamespace(embed_tokens=Embed(vocab))
        self.lm_head = torch.nn.Identity()

    @property
    def device(self):
        return self.anchor.device

    def forward(self, input_ids, past_key_values, **kwargs):
        past_key_values.length += int(input_ids.shape[1])
        predicted = (input_ids + 1) % self.vocab
        logits = torch.nn.functional.one_hot(predicted, self.vocab).float()
        hidden = torch.nn.functional.one_hot(input_ids, self.vocab).float()
        return Output(logits, (hidden, hidden))


class Drafter(torch.nn.Module):
    def __init__(self, block_size, vocab=32):
        super().__init__()
        self.anchor = torch.nn.Parameter(torch.zeros(1))
        self.vocab = vocab
        self.block_size = block_size
        self.mask_token_id = 0
        self.target_layer_ids = [0]

    def forward(self, noise_embedding, position_ids, past_key_values, **kwargs):
        assert noise_embedding.dtype == self.anchor.dtype
        assert kwargs["target_hidden"].dtype == self.anchor.dtype
        seed = noise_embedding[:, 0].argmax(dim=-1)
        block = noise_embedding.shape[1]
        ids = torch.stack([(seed + index) % self.vocab for index in range(block)], dim=1)
        past_key_values.length = int(position_ids[0, -1].item()) + 1
        return torch.nn.functional.one_hot(ids, self.vocab).float()


class Tokenizer:
    def decode(self, token_ids, skip_special_tokens=True):
        return " ".join(str(value) for value in token_ids)


def test_dflash_loop_advances_by_verified_blocks(monkeypatch):
    profile = load_config(ROOT / "config.yml").resolve_active_protocol_profile()
    config = profile.config
    block_policy = dict(config.require("optimization.block_policy"))
    fixed_block = int(block_policy["fixed_block_size"])
    max_new_tokens = int(config.require("runtime.max_new_tokens"))
    memory_limit = float(profile.require("hard_gates.dflash_peak_reserved_vram_gib"))
    monkeypatch.setattr(generate_module, "synchronize", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        generate_module,
        "collect_memory",
        lambda limit_gib: schemas_module.MemoryStats(
            limit_bytes=int(memory_limit * 1024**3), gate_pass=True
        ),
    )
    monkeypatch.setattr(generate_module, "enforce_memory_gate", lambda stats, label: None)
    settings = schemas_module.GenerationSettings(
        max_new_tokens=max_new_tokens,
        temperature=float(config.require("runtime.temperature")),
        stop_token_ids=tuple(config.require("runtime.stop_token_ids")),
        dataset=str(profile.require("dataset")),
        block_size=fixed_block,
        output_contract_mode=str(config.require("optimization.output_contract_mode")),
    )
    policy = policy_module.BlockPolicy.from_config(block_policy)
    result = generate_module.generate_dflash(
        Target(),
        Drafter(int(config.require("models.dflash.drafter.checkpoint_block_size"))),
        Tokenizer(),
        torch.tensor([[1]], dtype=torch.long),
        settings,
        model_metadata={},
        block_policy=policy,
        memory_limit_gib=memory_limit,
        compact_structural_audit=bool(
            config.require("optimization.compact_structural_audit")
        ),
    )
    assert len(result.generated_token_ids) == max_new_tokens
    assert sum(result.dflash.acceptance_lengths) == max_new_tokens - 1
    assert result.dflash.effective_tau == (
        sum(result.dflash.acceptance_lengths) / result.dflash.target_verification_calls
    )
    assert all(size == fixed_block for size in result.dflash.block_sizes)
    assert all(item["structural_pass"] for item in result.dflash.structural_audit)
