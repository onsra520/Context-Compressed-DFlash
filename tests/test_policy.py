from pathlib import Path

from ccdf.config import load_config
from ccdf.dflash.policy import BlockPolicy


ROOT = Path(__file__).resolve().parents[1]


def policy(mode="adaptive"):
    config = load_config(ROOT / "config.yml")
    values = dict(config.require("optimization.block_policy"))
    values["mode"] = mode
    return BlockPolicy.from_config(values)


def test_fixed_policy():
    config = load_config(ROOT / "config.yml")
    item = policy("fixed")
    item.observe(1)
    assert item.next_block_size() == config.require(
        "optimization.block_policy.fixed_block_size"
    )


def test_adaptive_policy_low_mid_high():
    config = load_config(ROOT / "config.yml")
    values = config.require("optimization.block_policy")
    low = policy()
    low.observe(float(values["low_tau_threshold"]) - 1)
    assert low.next_block_size() == values["low_tau_block_size"]
    mid = policy()
    mid.observe(float(values["low_tau_threshold"]))
    assert mid.next_block_size() == values["mid_tau_block_size"]
    high = policy()
    high.observe(float(values["high_tau_threshold"]))
    assert high.next_block_size() == values["high_tau_block_size"]
