from __future__ import annotations

import os
import json
from typing import List
from brain.brain_base import BrainDecision
from webtiles.observation import Observation

# OpenAI 최신 SDK(권장) 사용
from openai import OpenAI


ALLOWED_ACTIONS = {
    "TAB": "\t",
    "AUTOEXPLORE": "o",
    "WAIT": ".",
    "REST": "5",
    "SPACE": " ",
    "ESC": "\x1b",
}

SYSTEM_PROMPT = """You are the 'Brain' of a Dungeon Crawl Stone Soup (DCSS) autopilot.
You must output a single JSON object with keys:
- action: one of ["TAB","AUTOEXPLORE","WAIT","REST","SPACE","ESC"]
- reason: short reason in Korean (max 1 sentence)

Rules:
- If there is any sign of danger/monsters nearby -> action="TAB"
- If the game is waiting for --more--/confirmation -> action="SPACE"
- Otherwise explore -> action="AUTOEXPLORE"
- Never output anything except valid JSON.
"""


def _build_obs_text(obs: Observation) -> str:
    # 최근 메시지 몇 개만 AI에 제공 (너무 길면 비용/혼선 ↑)
    last_msgs: List[str] = obs.recent_msgs[-10:] if obs.recent_msgs else []
    msg_block = "\n".join(f"- {m}" for m in last_msgs)

    return f"""STATE
where: {obs.where}
turn: {obs.turn}
idle_time: {obs.idle_time}
recent_messages:
{msg_block}
"""


class OpenAIBrain:
    def __init__(self, model: str = "gpt-4.1-mini"):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def decide(self, obs: Observation) -> BrainDecision:
        user_prompt = _build_obs_text(obs)

        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            timeout=2.0,  # ✅ 이거 추가
        )

        text = resp.choices[0].message.content.strip()

        try:
            data = json.loads(text)
        except Exception:
            # AI가 JSON을 깨먹으면 안전하게 탐험 대신 WAIT
            return BrainDecision(action=".", reason="ai_json_parse_failed")

        act_name = str(data.get("action", "")).strip().upper()
        reason = str(data.get("reason", "")).strip()

        if act_name not in ALLOWED_ACTIONS:
            return BrainDecision(action=".", reason="ai_invalid_action")

        return BrainDecision(action=ALLOWED_ACTIONS[act_name], reason=f"ai:{reason}")
