from __future__ import annotations

import inspect

import importlib.util

import pytest
import torch

from ccdf.dflash.attention import validate_attention_contract
from ccdf.dflash.loader import audit_model_contract, load_drafter_config
from ccdf.dflash.model import EXPECTED_CONTRACT
from ccdf.dflash.utils import acceptance_prefix_length, build_target_layer_ids, metric_counters, sample
from ccdf.inference.model_registry import DRAFTER_PATH, TARGET_PATH
from ccdf.inference.target_loader import load_target_config, load_target_tokenizer
from ccdf.config import resolve_config
from ccdf.paths import find_shared_root, find_worktree_root

WORKTREE_ROOT = find_worktree_root()
SHARED_ROOT = find_shared_root(WORKTREE_ROOT)
RUNTIME_AVAILABLE = importlib.util.find_spec("transformers") is not None
TARGET_LOCAL = SHARED_ROOT / "models/target/unsloth--Qwen3-4B-bnb-4bit"
DRAFTER_LOCAL = SHARED_ROOT / "models/drafter/z-lab--Qwen3-4B-DFlash-b16"
requires_models = pytest.mark.skipif(
    not RUNTIME_AVAILABLE or not TARGET_LOCAL.is_dir() or not DRAFTER_LOCAL.is_dir(),
    reason="local model contract test requires Transformers and both checkpoints",
)


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


@requires_models
def test_local_configs_are_compatible() -> None:
    target_config = load_target_config(TARGET_LOCAL)
    drafter_config = load_drafter_config(DRAFTER_LOCAL)
    audit = audit_model_contract(target_config, drafter_config)
    assert audit["pass"] is True
    assert validate_attention_contract(drafter_config)["is_full_attention_only"] is True


@requires_models
def test_target_tokenizer_local_only() -> None:
    tokenizer = load_target_tokenizer(TARGET_LOCAL)
    assert tokenizer.eos_token_id == 151645


def test_runtime_modules_do_not_import_archives() -> None:
    import ccdf.dflash.generate as generate
    import ccdf.inference.baseline_ar as baseline

    assert ".archives" not in inspect.getsource(generate)
    assert ".archives" not in inspect.getsource(baseline)


def test_generation_result_has_benchmark_timing_fields() -> None:
    from ccdf.inference.schemas import GenerationResult

    fields = set(GenerationResult.__dataclass_fields__)
    assert {"target_prefill_ms", "decode_total_ms", "request_e2e_ms"}.issubset(fields)
