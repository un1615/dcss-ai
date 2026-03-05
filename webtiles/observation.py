from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List
import requests
import json
import re


@dataclass
class Observation:
    user: str
    game_id: str
    running: bool
    where: str
    idle_time: int
    turn: int
    blocked: List[str]
    last_activity_time: float
    recent_text: str
    input_mode: int | None

    recent_msgs: List[str]
    msg_tail_raw: List[str]


_TAG_RE = re.compile(r"<[^>]+>")


def _strip_tags(s: str) -> str:
    return _TAG_RE.sub("", s)


def _json_unescape(s: str) -> str:
    try:
        return json.loads(f'"{s}"')
    except Exception:
        return s


def _extract_text_messages_from_msg_tail(msg_tail_items):
    """
    msg_tail은 JSON 문자열 리스트지만 종종 (trunc) 때문에 깨진다.
    그래서
    1) json.loads 시도
    2) 실패하면 regex fallback
    """

    out = []

    if not isinstance(msg_tail_items, list):
        return out

    text_re = re.compile(r"\"text\"\s*:\s*\"(.*?)\"", re.DOTALL)

    for item in msg_tail_items:
        if not isinstance(item, str):
            continue

        parsed = None

        try:
            parsed = json.loads(item)
        except Exception:
            parsed = None

        if isinstance(parsed, dict):

            msgs = parsed.get("msgs", [])

            for m in msgs:
                if not isinstance(m, dict):
                    continue

                if m.get("msg") != "msgs":
                    continue

                messages = m.get("messages", [])

                for mm in messages:
                    text = mm.get("text")

                    if not text:
                        continue

                    out.append(_strip_tags(str(text)).strip())

            continue

        # fallback regex
        for g in text_re.findall(item):

            unescaped = _json_unescape(g)

            out.append(_strip_tags(unescaped).strip())

    # 연속 중복 제거
    dedup = []

    for t in out:
        if not t:
            continue

        if not dedup or dedup[-1] != t:
            dedup.append(t)

    return dedup


def fetch_observation(
    base_url: str,
    username: str,
    log_n: int = 20,
    timeout: float = 5.0,
) -> Observation:

    state_url = f"{base_url}/bot/state?username={username}"

    r = requests.get(state_url, timeout=timeout)
    r.raise_for_status()
    s = r.json()

    if not s.get("ok"):
        raise RuntimeError("state not ok")

    msg_tail_raw = s.get("msg_tail", []) or []

    # --- input_mode 파싱 추가 ---
    input_mode = None
    for item in msg_tail_raw:
        if not isinstance(item, str):
            continue
        try:
            parsed = json.loads(item)
        except Exception:
            continue
        if not isinstance(parsed, dict):
            continue
        msgs = parsed.get("msgs", [])
        for m in msgs:
            if isinstance(m, dict) and m.get("msg") == "input_mode":
                try:
                    input_mode = int(m.get("mode"))
                except Exception:
                    input_mode = None

    recent_msgs = _extract_text_messages_from_msg_tail(msg_tail_raw)
    recent_text = "\n".join(recent_msgs).lower()

    blocked_val = s.get("blocked", [])

    if isinstance(blocked_val, list):
        blocked_list = blocked_val
    elif isinstance(blocked_val, (set, tuple)):
        blocked_list = list(blocked_val)
    else:
        blocked_list = [str(blocked_val)]

    return Observation(
        user=s.get("user", username),
        game_id=s.get("game_id", ""),
        running=bool(s.get("running", False)),
        where=str(s.get("where", "")),
        idle_time=int(s.get("idle_time", 0)),
        turn=int(s.get("turn", 0)),
        blocked=blocked_list,
        last_activity_time=float(s.get("last_activity_time", 0.0)),
        recent_msgs=recent_msgs,
        msg_tail_raw=msg_tail_raw,
        recent_text=recent_text,
        input_mode=input_mode,
    )
