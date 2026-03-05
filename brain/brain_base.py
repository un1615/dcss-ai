from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from webtiles.observation import Observation


@dataclass
class BrainDecision:
    action: str  # 실제로 보낼 키: "\t", "o", ".", " ", "\x1b"
    reason: str = ""  # 로그용(왜 이걸 했는지)


class Brain(Protocol):
    def decide(self, obs: Observation) -> BrainDecision: ...
