from __future__ import annotations

from webtiles.observation import Observation
from policy.simple_policy import choose_action
from brain.brain_base import BrainDecision


class RuleFallbackBrain:
    def decide(self, obs: Observation) -> BrainDecision:
        act = choose_action(obs)
        return BrainDecision(action=act, reason="rule_fallback")
