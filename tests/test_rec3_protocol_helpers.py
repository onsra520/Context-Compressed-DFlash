import copy
from pathlib import Path

import pytest

from ccdf.config import Config, load_config
from ccdf.errors import ConfigurationError
from ccdf.benchmark.metrics import output_quality_record


ROOT = Path(__file__).resolve().parents[1]


def _profile():
    return load_config(ROOT / "config.yml").resolve_active_protocol_profile()


def _quality(text: str, expected: dict[str, str]):
    contract = _profile().require("prompt_contract")
    return output_quality_record(
        text,
        expected,
        strict_pattern=str(contract["strict_output_pattern"]),
        tolerant_pattern=str(contract["tolerant_field_pattern"]),
    )


def test_tolerant_parser_keeps_fields_when_strict_format_rejects_punctuation():
    fixture = _profile().require("fixtures")[0]
    expected = {
        "owner": str(fixture["owner"]),
        "approval_code": str(fixture["approval_code"]),
        "quantity": str(fixture["quantity"]),
    }
    text = (
        f"Owner: {expected['owner']}; Approval code: {expected['approval_code']}; "
        f"Quantity: {expected['quantity']}."
    )

    result = _quality(text, expected)

    assert result["format_compliant"] is False
    assert result["parsed_fields"] == expected
    assert result["exact_field_match"] is True


def test_tolerant_parser_still_rejects_wrong_field_value_for_quality():
    fixture = _profile().require("fixtures")[0]
    expected = {
        "owner": str(fixture["owner"]),
        "approval_code": str(fixture["approval_code"]),
        "quantity": str(fixture["quantity"]),
    }
    wrong_owner = f"{expected['owner']}-wrong"
    text = (
        f"Owner: {wrong_owner}; Approval code: {expected['approval_code']}; "
        f"Quantity: {expected['quantity']}"
    )

    result = _quality(text, expected)

    assert result["format_compliant"] is True
    assert result["parsed_fields"]["owner"] == wrong_owner
    assert result["field_matches"]["owner"] is False
    assert result["exact_field_match"] is False


def test_active_profile_resolves_without_mutating_canonical_config():
    canonical = load_config(ROOT / "config.yml")
    active = canonical.resolve_active_protocol_profile()

    assert active.name == canonical.require("protocol_profiles.active")
    assert canonical.require("optimization.block_policy.fixed_block_size") == canonical.require(
        "models.dflash.drafter.checkpoint_block_size"
    )
    assert active.config.require("optimization.block_policy.fixed_block_size") in canonical.require(
        "optimization.block_policy.allowed_block_sizes"
    )
    assert active.config.data is not canonical.data


def test_missing_profile_setting_fails_fast():
    canonical = load_config(ROOT / "config.yml")
    data = copy.deepcopy(canonical.data)
    active_name = data["protocol_profiles"]["active"]
    del data["protocol_profiles"]["profiles"][active_name]["hard_gates"][
        "dflash_peak_reserved_vram_gib"
    ]
    invalid = Config(path=canonical.path, root=canonical.root, data=data)

    with pytest.raises(ConfigurationError, match="dflash_peak_reserved_vram_gib"):
        invalid.validate()


def test_unknown_profile_override_fails_fast():
    canonical = load_config(ROOT / "config.yml")
    data = copy.deepcopy(canonical.data)
    active_name = data["protocol_profiles"]["active"]
    data["protocol_profiles"]["profiles"][active_name]["config_overrides"]["runtime"][
        "misspelled_setting"
    ] = True
    invalid = Config(path=canonical.path, root=canonical.root, data=data)

    with pytest.raises(ConfigurationError, match="unknown config key"):
        invalid.validate()
