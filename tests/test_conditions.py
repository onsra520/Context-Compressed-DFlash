from __future__ import annotations

from ccdf.benchmark.conditions import CONDITIONS, MVP_CONDITIONS


def _condition(name: str) -> dict:
    matches = [condition for condition in MVP_CONDITIONS if condition["name"] == name]
    assert len(matches) == 1
    return matches[0]


def test_baseline_ar_is_first_class_mvp_condition():
    baseline = _condition("Baseline-AR")

    assert baseline["compression"] == "none"
    assert baseline["keep_rate"] == 1.0
    assert baseline["generation_mode"] == "autoregressive"
    assert baseline["uses_dflash"] is False
    assert baseline["uses_draft"] is False
    assert baseline["uses_compression"] is False


def test_existing_mvp_conditions_keep_expected_roles():
    dflash = _condition("DFlash-R1")
    ar_r2 = _condition("LLMLingua-AR-R2")
    cc_r2 = _condition("CC-LLM-R2")

    assert dflash["uses_dflash"] is True
    assert dflash["uses_draft"] is True
    assert dflash["uses_compression"] is False
    assert ar_r2["generation_mode"] == "autoregressive"
    assert ar_r2["uses_draft"] is False
    assert ar_r2["uses_compression"] is True
    assert cc_r2["uses_dflash"] is True
    assert cc_r2["uses_draft"] is True
    assert cc_r2["uses_compression"] is True


def test_conditions_alias_preserves_runner_compatibility():
    assert CONDITIONS is MVP_CONDITIONS
    assert "Baseline-AR" in [condition["name"] for condition in CONDITIONS]
