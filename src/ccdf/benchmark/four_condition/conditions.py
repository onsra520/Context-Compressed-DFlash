"""Canonical four-condition identities."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Condition:
    condition_id: str
    name: str
    runtime_condition: str
    prompt_kind: str


CONDITIONS = {
    "C1": Condition("C1", "Baseline-AR", "baseline", "original"),
    "C2": Condition("C2", "DFlash-R1", "dflash", "original"),
    "C3": Condition("C3", "LLMLingua-AR-R2", "baseline", "compressed"),
    "C4": Condition("C4", "CC-DFlash-R2", "dflash", "compressed"),
}
