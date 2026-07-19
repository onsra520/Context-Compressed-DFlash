import json

import pytest

from ccdf.cli import build_parser, main


def test_parser_keeps_run_defaults() -> None:
    args = build_parser().parse_args(["run", "--condition", "baseline", "--prompt", "hello"])

    assert args.config == "config.yml"
    assert args.target_profile == "primary"
    assert args.dataset == "general"
    assert args.max_new_tokens is None


def test_parser_rejects_unknown_condition() -> None:
    with pytest.raises(SystemExit) as error:
        build_parser().parse_args(["run", "--condition", "compressed", "--prompt", "hello"])

    assert error.value.code == 2


def test_main_validate_config_preserves_json_contract(capsys) -> None:
    assert main(["validate-config", "--config", "config.yml"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["pass"] is True
    assert payload["root"].endswith("CCDF-Rework")
    assert payload["warnings"] == ["D-Flash limit plus compressor reserve exceeds 8 GiB"]
