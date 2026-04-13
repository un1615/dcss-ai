from __future__ import annotations

import os
import json
from typing import List
from brain.brain_base import BrainDecision
from webtiles.observation import Observation

# OpenAI 최신 SDK(권장) 사용
from openai import OpenAI


client = OpenAI()


def build_decision_prompt(obs_dict: dict) -> str:
    return f"""
You are controlling a Dungeon Crawl Stone Soup character.

Current observation:
{json.dumps(obs_dict, ensure_ascii=False)}

Choose exactly one next action.

Rules:
- Use only movement directions.
- If a visible monster exists, move toward the nearest monster.
- If no visible monsters exist, move in a reasonable exploration direction.
- Do not explain for long.

Return JSON only.
Format:
{{
  "action": "move",
  "dir": "h|j|k|l|y|u|b|n",
  "reason": "short reason"
}}

Direction meaning:
h = left
j = down
k = up
l = right
y = up-left
u = up-right
b = down-left
n = down-right
""".strip()


def decide_next_action(obs_dict: dict, model: str = "gpt-5") -> dict:
    prompt = build_decision_prompt(obs_dict)

    resp = client.responses.create(
        model=model,
        input=prompt,
    )

    print("RAW RESPONSE:", resp)

    try:
        text = resp.output_text.strip()
        print("MODEL TEXT:", text)
    except Exception as e:
        print("TEXT EXTRACT ERROR:", e)
        return {"type": "move", "dir": "h", "reason": "response parse failed"}

    try:
        data = json.loads(text)
    except Exception:
        return {
            "type": "move",
            "dir": "h",
            "reason": f"json parse failed: {text[:120]}",
        }

    action = data.get("action")
    direction = data.get("dir")
    reason = data.get("reason", "")

    allowed_dirs = {"h", "j", "k", "l", "y", "u", "b", "n"}

    if action != "move" or direction not in allowed_dirs:
        return {"type": "move", "dir": "h", "reason": f"invalid ai action: {data}"}

    return {
        "type": "move",
        "dir": direction,
        "reason": reason,
    }


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
