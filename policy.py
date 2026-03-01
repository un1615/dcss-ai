# policy.py
import json
from typing import Dict, Any


def choose_action(obs: Dict[str, Any]) -> str:
    """
    더미 정책: 지금은 안전하게만.
    - more_prompt면 key(space)
    - repeat_prompt면 key(esc)
    - 몬스터 있으면 attack
    - 그 외는 autoexplore
    """
    if obs.get("more_prompt"):
        return json.dumps(
            {
                "type": "key",
                "key": " ",
                "reason": "more",
                "risk": "low",
                "stop_explore": True,
            }
        )

    if obs.get("repeat_prompt"):
        return json.dumps(
            {
                "type": "key",
                "key": "esc",
                "reason": "repeat prompt",
                "risk": "low",
                "stop_explore": True,
            }
        )

    if obs.get("monsters_present"):
        return json.dumps(
            {
                "type": "attack",
                "reason": "monster present (dummy)",
                "risk": "med",
                "stop_explore": True,
            }
        )

    return json.dumps(
        {
            "type": "autoexplore",
            "reason": "explore (dummy)",
            "risk": "low",
            "stop_explore": False,
        }
    )
