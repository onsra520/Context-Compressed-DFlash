from __future__ import annotations

import inspect

import torch

from ccdf.dflash.attention import validate_attention_contract
from ccdf.dflash.loader import audit_model_contract, load_drafter_config
from ccdf.dflash.model import EXPECTED_CONTRACT
from ccdf.dflash.utils import acceptance_prefix_length, build_target_layer_ids, metric_counters, sample
from ccdf.inference.model_registry import DRAFTER_PATH, TARGET_PATH
from ccdf.inference.target_loader import load_target_config, load_target_tokenizer


def test_target_layer_ids_match_locked_drafter() -> None:
    assert build_target_layer_ids(36, 5) == [1, 9, 17, 25, 33]
    assert EXPECTED_CONTRACT.block_size == 16


def test_greedy_sampler() -> None:
    logits = torch.tensor([[[0.1, 4.0, 0.2]]])
    assert sample(logits, temperature=0.0).item() == 1


def test_acceptance_prefix_cases() -> None:
    assert acceptance_prefix_length([1, 2, 3], [9, 2, 3]) == 0
    assert acceptance_prefix_length([1, 2, 3], [1, 2, 3]) == 3
    assert acceptance_prefix_length([1, 2, 3], [1, 9, 3]) == 1


def test_metric_counters() -> None:
    counters = metric_counters([1, 4, 2], draft_tokens_proposed=8)
    assert counters["verification_calls"] == 3
    assert counters["accepted_draft_tokens"] == 4
    assert counters["rollback_tokens"] == 4


def test_local_configs_are_compatible() -> None:
    target_config = load_target_config(TARGET_PATH)
    drafter_config = load_drafter_config(DRAFTER_PATH)
    audit = audit_model_contract(target_config, drafter_config)
    assert audit["pass"] is True
    assert validate_attention_contract(drafter_config)["is_full_attention_only"] is True


def test_target_tokenizer_local_only() -> None:
    tokenizer = load_target_tokenizer(TARGET_PATH)
    assert tokenizer.eos_token_id == 151645


def test_runtime_modules_do_not_import_archives() -> None:
    import ccdf.dflash.generate as generate
    import ccdf.inference.baseline_ar as baseline

    assert ".archives" not in inspect.getsource(generate)
    assert ".archives" not in inspect.getsource(baseline)
