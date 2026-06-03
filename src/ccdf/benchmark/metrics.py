from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Sequence

# STATUS: current EM and tau are skeleton-level metrics.
# STATUS: GSM8K EM must later use final-answer extraction.
# STATUS: tau must later come from real DFlash acceptance_lengths.


def _normalize(text: str) -> str:
    return " ".join(text.strip().lower().split())


def compute_exact_match(prediction: str, reference: str) -> bool:
    return _normalize(prediction) == _normalize(reference)


def compute_invalid_output_rate(outputs: Sequence[str]) -> float:
    if not outputs:
        return 0.0

    invalid_count = 0
    for output in outputs:
        normalized = _normalize(output)
        if not normalized:
            invalid_count += 1
            continue
        if not any(character.isalnum() for character in normalized):
            invalid_count += 1
            continue
        if "<unk>" in normalized or "nan" in normalized:
            invalid_count += 1

    return invalid_count / len(outputs)


def compute_tau(acceptance_lengths: Iterable[int]) -> float:
    values = list(acceptance_lengths)
    if not values:
        return 0.0
    return sum(values) / len(values)


@dataclass
class SingleResult:
    prediction: str
    reference: str
    original_tokens: int = 0
    compressed_tokens: int = 0
    acceptance_lengths: list[int] = field(default_factory=list)


@dataclass
class MetricsCollector:
    results: list[SingleResult] = field(default_factory=list)

    def add(self, result: SingleResult) -> None:
        self.results.append(result)

    def summary(self) -> dict[str, float]:
        if not self.results:
            return {"exact_match": 0.0, "invalid_output_rate": 0.0, "tau": 0.0}

        exact_match = sum(compute_exact_match(r.prediction, r.reference) for r in self.results) / len(
            self.results
        )
        invalid_output_rate = compute_invalid_output_rate([r.prediction for r in self.results])
        taus = [compute_tau(r.acceptance_lengths) for r in self.results]
        tau = sum(taus) / len(taus)
        return {"exact_match": exact_match, "invalid_output_rate": invalid_output_rate, "tau": tau}