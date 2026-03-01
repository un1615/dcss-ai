# policy_openai.py - V3: tool-forced JSON action output (no non-json fallback)
import json
import os
from openai import OpenAI

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

MODEL = os.environ.get("OPENAI_MODEL", "gpt-5-mini")  # 네가 쓰는 모델명 유지

ACTION_TOOL = [
    {
        "type": "function",
        "function": {
            "name": "next_action",
            "description": "Choose the next DCSS action from the observation. Output ONLY one action.",
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": [
                            "move",
                            "attack",
                            "wait",
                            "autoexplore",
                            "key",
                            "keys",
                            "esc",
                            "more",
                            "confirm",
                            "levelup",
                        ],
                    },
                    "dir": {
                        "type": ["string", "null"],
                        "enum": ["h", "j", "k", "l", "y", "u", "b", "n", None],
                    },
                    "key": {"type": ["string", "null"]},
                    "keys": {
                        "type": ["string", "null"],
                        "description": "multiple keypresses in sequence, e.g. 'za.'",
                    },
                    "reason": {"type": "string"},
                    "risk": {"type": "string", "enum": ["low", "med", "high"]},
                    "stop_explore": {"type": ["boolean", "null"]},
                },
                "required": ["type", "reason", "risk"],
            },
        },
    }
]


SYSTEM = """You are an AI playing Dungeon Crawl Stone Soup (DCSS).
You must output exactly ONE action via the tool call next_action.

Rules:
- Use only allowed_actions from obs.
- If last_action_failed==true or flags.move_blocked==true, do NOT repeat the same blocked move direction.
- If poisoned and low HP, prioritize survival (kite, retreat, heal if possible).
- If in melee contact and safe, attack (TAB).
- If a prompt exists, controller will handle it; you can still reason about it but choose a normal action.

Return tool call only.
"""


def choose_action_openai(obs: dict) -> str:
    # Keep obs small-ish: already tail-only.
    user = json.dumps(obs, ensure_ascii=False)

    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
        ],
        tools=ACTION_TOOL,
        tool_choice={"type": "function", "function": {"name": "next_action"}},
        # IMPORTANT:
        # - do NOT pass temperature if your model rejects non-default values
        # - do NOT pass max_tokens; use max_completion_tokens only if needed and model supports it
        # We'll omit both for maximum compatibility.
    )

    msg = resp.choices[0].message

    # tool-forced -> should exist
    if not msg.tool_calls:
        # ultra-safe fallback
        return json.dumps(
            {"type": "wait", "reason": "no_tool_call_fallback", "risk": "low"},
            ensure_ascii=False,
        )

    args = msg.tool_calls[0].function.arguments
    # args is a JSON string
    try:
        obj = json.loads(args)
    except Exception:
        return json.dumps(
            {"type": "wait", "reason": "tool_args_parse_fail", "risk": "low"},
            ensure_ascii=False,
        )

    # minimal sanitation
    if obj.get("type") == "move":
        d = obj.get("dir")
        if d not in ["h", "j", "k", "l", "y", "u", "b", "n"]:
            obj["type"] = "wait"
            obj["reason"] = "bad_move_dir_sanitized"
            obj["risk"] = "low"

    return json.dumps(obj, ensure_ascii=False)
