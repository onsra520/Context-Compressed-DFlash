from __future__ import annotations

from pathlib import Path

import pytest

from ccdf.compression.llmlingua import LLMLinguaCompressor
from ccdf.config.loader import resolve_compressor_model_source, resolve_llmlingua_config


def test_large_profile_resolves_local_compressor_path(tmp_path: Path):
    compressor_dir = tmp_path / "models" / "llmlingua-2-xlm-roberta-large-meetingbank"
    compressor_dir.mkdir(parents=True)
    cfg = {
        "model_name": "microsoft/llmlingua-2-xlm-roberta-large-meetingbank",
        "compressor_path": "models/llmlingua-2-xlm-roberta-large-meetingbank",
        "local_files_only": True,
    }

    resolved = resolve_compressor_model_source(cfg, repo_root=tmp_path)

    assert resolved["source_kind"] == "compressor_path"
    assert resolved["compressor_path"] == "models/llmlingua-2-xlm-roberta-large-meetingbank"
    assert resolved["resolved_compressor_path"] == str(compressor_dir.resolve())
    assert resolved["local_files_only"] is True


def test_light_profile_resolves_local_compressor_path(tmp_path: Path):
    compressor_dir = tmp_path / "models" / "llmlingua-2-bert-base-multilingual-cased-meetingbank"
    compressor_dir.mkdir(parents=True)
    cfg = {
        "model_name": "microsoft/llmlingua-2-bert-base-multilingual-cased-meetingbank",
        "compressor_path": "models/llmlingua-2-bert-base-multilingual-cased-meetingbank",
        "local_files_only": True,
    }

    resolved = resolve_compressor_model_source(cfg, repo_root=tmp_path)

    assert resolved["source_kind"] == "compressor_path"
    assert resolved["resolved_compressor_path"] == str(compressor_dir.resolve())


def test_compressor_path_takes_priority_over_model_name(tmp_path: Path):
    compressor_dir = tmp_path / "models" / "preferred-path"
    compressor_dir.mkdir(parents=True)
    cfg = {
        "model_name": "remote/model-id",
        "compressor_path": "models/preferred-path",
        "local_files_only": True,
    }

    resolved = resolve_compressor_model_source(cfg, repo_root=tmp_path)

    assert resolved["source"] == str(compressor_dir.resolve())
    assert resolved["source_kind"] == "compressor_path"
    assert resolved["model_name"] == "remote/model-id"


def test_missing_compressor_path_raises_clear_error(tmp_path: Path):
    cfg = {
        "model_name": "remote/model-id",
        "compressor_path": "models/missing-path",
        "local_files_only": True,
    }

    with pytest.raises(FileNotFoundError, match="Configured compressor_path does not exist"):
        resolve_compressor_model_source(cfg, repo_root=tmp_path)


def test_model_name_only_profile_remains_backward_compatible():
    cfg = {
        "model_name": "legacy/model-id",
        "device_map": "cpu",
    }

    resolved = resolve_compressor_model_source(cfg)

    assert resolved["source"] == "legacy/model-id"
    assert resolved["source_kind"] == "model_name"
    assert resolved["resolved_compressor_path"] is None


def test_from_config_uses_local_path_metadata(tmp_path: Path):
    compressor_dir = tmp_path / "models" / "llmlingua-2-xlm-roberta-large-meetingbank"
    compressor_dir.mkdir(parents=True)
    config = {
        "compression": {
            "large_llmlingua": {
                "model_name": "microsoft/llmlingua-2-xlm-roberta-large-meetingbank",
                "compressor_path": str(compressor_dir),
                "device_map": "cpu",
                "local_files_only": True,
            }
        }
    }

    cfg = resolve_llmlingua_config(config, profile="large")
    resolved = resolve_compressor_model_source(cfg, repo_root=tmp_path)

    compressor = LLMLinguaCompressor(
        model_name=cfg["model_name"],
        compressor_path=resolved["compressor_path"],
        resolved_compressor_path=resolved["resolved_compressor_path"],
        model_source=resolved["source"],
        source_kind=resolved["source_kind"],
        local_files_only=resolved["local_files_only"],
        device_map=cfg["device_map"],
        compressor_profile="large",
    )

    assert compressor.model_name == "microsoft/llmlingua-2-xlm-roberta-large-meetingbank"
    assert compressor.model_source == str(compressor_dir)
    assert compressor.source_kind == "compressor_path"
    assert compressor.local_files_only is True
