from __future__ import annotations

import pathlib

import pytest
import torch

import ccdf.dflash as dflash
from ccdf.dflash.attention import Qwen3DFlashAttention, apply_rotary_pos_emb
from ccdf.dflash.generate import dflash_generate
from ccdf.dflash.loader import load_all, load_draft, load_target, load_tokenizer
from ccdf.dflash.model import DFlashDraftModel, Qwen3DFlashDecoderLayer
from ccdf.dflash.utils import build_target_layer_ids, extract_context_feature, sample


def test_dflash_split_modules_do_not_import_raw_references():
    bad = []
    for path in pathlib.Path("src/ccdf/dflash").glob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "model_raw" in text or "benchmark_raw" in text:
            bad.append(str(path))

    assert bad == []


def test_synthetic_probe_has_dry_run_and_no_raw_imports():
    text = pathlib.Path("scripts/synthetic_probe.py").read_text(encoding="utf-8")

    assert "--dry-run" in text
    assert "import model_raw" not in text
    assert "import benchmark_raw" not in text
    assert "from ccdf import model_raw" not in text
    assert "from ccdf.benchmark import benchmark_raw" not in text


def test_key_split_symbols_are_exported_from_real_modules():
    assert dflash.DFlashDraftModel is DFlashDraftModel
    assert dflash.Qwen3DFlashAttention is Qwen3DFlashAttention
    assert callable(dflash_generate)
    assert callable(apply_rotary_pos_emb)
    assert callable(load_target)
    assert callable(load_draft)
    assert callable(load_tokenizer)
    assert callable(load_all)
    assert Qwen3DFlashDecoderLayer.__name__ == "Qwen3DFlashDecoderLayer"


def test_build_target_layer_ids_matches_reference_spacing():
    assert build_target_layer_ids(12, 3) == [1, 5, 9]


def test_extract_context_feature_uses_layer_offset():
    hidden_states = [
        torch.tensor([[0.0, 0.0]]),
        torch.tensor([[1.0, 1.0]]),
        torch.tensor([[2.0, 2.0]]),
        torch.tensor([[3.0, 3.0]]),
    ]
    feature = extract_context_feature(hidden_states, [0, 1])
    assert torch.equal(feature, torch.tensor([[1.0, 1.0, 2.0, 2.0]]))


def test_extract_context_feature_matches_raw_error_for_missing_layer_ids():
    with pytest.raises(TypeError):
        extract_context_feature([torch.tensor([[0.0]])], None)


def test_sample_greedy_path_chooses_argmax():
    logits = torch.tensor([[[1.0, 5.0, 2.0]]])
    assert torch.equal(sample(logits, temperature=0.0), torch.tensor([[1]]))
