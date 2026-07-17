"""Fixed and rolling-tau block-size policy."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field


@dataclass
class BlockPolicy:
    mode: str
    fixed_block_size: int
    allowed_block_sizes: tuple[int, ...]
    rolling_window: int
    low_tau_threshold: float
    high_tau_threshold: float
    low_tau_block_size: int
    mid_tau_block_size: int
    high_tau_block_size: int
    history: deque[float] = field(init=False)

    def __post_init__(self) -> None:
        self.history = deque(maxlen=max(int(self.rolling_window), 1))
        if self.mode not in {"fixed", "adaptive"}:
            raise ValueError(f"unsupported block policy mode: {self.mode}")

    @classmethod
    def from_config(cls, data: dict) -> "BlockPolicy":
        return cls(
            mode=str(data["mode"]),
            fixed_block_size=int(data["fixed_block_size"]),
            allowed_block_sizes=tuple(int(value) for value in data["allowed_block_sizes"]),
            rolling_window=int(data["rolling_window"]),
            low_tau_threshold=float(data["low_tau_threshold"]),
            high_tau_threshold=float(data["high_tau_threshold"]),
            low_tau_block_size=int(data["low_tau_block_size"]),
            mid_tau_block_size=int(data["mid_tau_block_size"]),
            high_tau_block_size=int(data["high_tau_block_size"]),
        )

    def observe(self, tokens_advanced: int) -> None:
        self.history.append(float(tokens_advanced))

    @property
    def rolling_tau(self) -> float | None:
        if not self.history:
            return None
        return sum(self.history) / len(self.history)

    def next_block_size(self) -> int:
        if self.mode == "fixed" or not self.history:
            return self.fixed_block_size
        tau = float(self.rolling_tau)
        if tau < self.low_tau_threshold:
            selected = self.low_tau_block_size
        elif tau < self.high_tau_threshold:
            selected = self.mid_tau_block_size
        else:
            selected = self.high_tau_block_size
        if selected not in self.allowed_block_sizes:
            raise ValueError(f"policy selected unsupported block size: {selected}")
        return selected
