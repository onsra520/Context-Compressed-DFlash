from __future__ import annotations

from pathlib import Path

import pytest

from ccdf.config.loader import resolve_compressor_model_source, resolve_llmlingua_config
from scripts.run_mvp import _prepare_cc_prompt


LARGE_MODEL_NAME = "microsoft/llmlingua-2-xlm-roberta-large-meetingbank"
LIGHT_MODEL_NAME = "microsoft/llmlingua-2-bert-base-multilingual-cased-meetingbank"
LARGE_COMPRESSOR_PATH = "models/llmlingua-2-xlm-roberta-large-meetingbank"
LIGHT_COMPRESSOR_PATH = "models/llmlingua-2-bert-base-multilingual-cased-meetingbank"


def _task93_config(repo_root: Path) -> dict:
    (repo_root / LARGE_COMPRESSOR_PATH).mkdir(parents=True)
    (repo_root / LIGHT_COMPRESSOR_PATH).mkdir(parents=True)
    return {
        "compression": {
            "large_llmlingua": {
                "model_name": LARGE_MODEL_NAME,
                "compressor_path": LARGE_COMPRESSOR_PATH,
                "device_map": "cpu",
                "local_files_only": True,
                "use_llmlingua2": True,
                "default_keep_rate": 0.5,
            },
            "light_llmlingua": {
                "model_name": LIGHT_MODEL_NAME,
                "compressor_path": LIGHT_COMPRESSOR_PATH,
                "device_map": "cpu",
                "local_files_only": True,
                "use_llmlingua2": True,
                "default_keep_rate": 0.5,
            },
        }
    }


@pytest.mark.parametrize(
    ("alias", "expected_model_name"),
    [
        ("large", LARGE_MODEL_NAME),
        ("large_llmlingua", LARGE_MODEL_NAME),
        ("light", LIGHT_MODEL_NAME),
        ("light_llmlingua", LIGHT_MODEL_NAME),
    ],
)
def test_compressor_profile_aliases_resolve(alias: str, expected_model_name: str, tmp_path: Path):
    config = _task93_config(tmp_path)

    profile = resolve_llmlingua_config(config, profile=alias)

    assert profile["model_name"] == expected_model_name


@pytest.mark.parametrize(
    ("alias", "expected_path"),
    [
        ("large", LARGE_COMPRESSOR_PATH),
        ("light", LIGHT_COMPRESSOR_PATH),
    ],
)
def test_profile_aliases_resolve_to_local_compressor_paths(alias: str, expected_path: str, tmp_path: Path):
    config = _task93_config(tmp_path)
    profile = resolve_llmlingua_config(config, profile=alias)

    source = resolve_compressor_model_source(profile, repo_root=tmp_path)

    assert source["compressor_path"] == expected_path
    assert source["resolved_compressor_path"] == str((tmp_path / expected_path).resolve())
    assert source["source_kind"] == "compressor_path"
    assert source["local_files_only"] is True


def test_prepare_cc_prompt_includes_task93_compressor_metadata():
    class FakeCompressor:
        model_name = LIGHT_MODEL_NAME
        compressor_path = LIGHT_COMPRESSOR_PATH
        resolved_compressor_path = f"/repo/{LIGHT_COMPRESSOR_PATH}"
        model_source = f"/repo/{LIGHT_COMPRESSOR_PATH}"
        source_kind = "compressor_path"
        local_files_only = True
        compressor_profile = "light"

        def compress(self, *, context: str, question: str, keep_rate: float):
            return (
                f"compressed context\n\n{question}",
                {
                    "t_compress_ms": 12.5,
                    "R_actual": 2.0,
                    "N_original": 100,
                    "N_compressed": 50,
                    "keep_rate": keep_rate,
                },
            )

    _prompt, metadata = _prepare_cc_prompt(
        question="What is 2 + 2?",
        context="Numbers matter here.",
        compressor=FakeCompressor(),
        keep_rate=0.5,
    )

    assert metadata["compressor_profile"] == "light"
    assert metadata["compressor_path"] == LIGHT_COMPRESSOR_PATH
    assert metadata["resolved_compressor_path"] == f"/repo/{LIGHT_COMPRESSOR_PATH}"
    assert metadata["compressor_model_name"] == LIGHT_MODEL_NAME
    assert metadata["local_files_only"] is True
