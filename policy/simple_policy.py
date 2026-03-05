from __future__ import annotations
from webtiles.observation import Observation

THREAT_PHRASES = [
    "is nearby",
    "there are monsters nearby",
    "you encounter",
    "comes into view",
    "attacks you",
    "hits you",
]

MORE_PHRASES = [
    "--more--",
    "more--",
    "--more",
]


def needs_more(obs: Observation) -> bool:
    t = (obs.recent_text or "").lower()
    return any(p in t for p in MORE_PHRASES)


def has_unknown_command(obs: Observation) -> bool:
    recent = obs.recent_msgs[-6:] if obs.recent_msgs else []
    return any("unknown command" in t.lower() for t in recent)


def has_threat(obs: Observation) -> bool:
    recent = obs.recent_msgs[-6:] if obs.recent_msgs else []
    for t in recent:
        low = t.lower()
        if "no target in view" in low:
            continue
        if any(p in low for p in THREAT_PHRASES):
            return True
    return False


def choose_action(obs: Observation) -> str:
    # 0) --more--면 무조건 space
    if needs_more(obs):
        return " "

    # 1) 위협 있으면 Tab
    if has_threat(obs):
        return "\t"

    # 2) 안전할 때만 탐험 (unknown command가 최근에 뜬 상태면 일단 대기)
    if obs.idle_time >= 2 and not has_unknown_command(obs):
        return "o"

    return "."
