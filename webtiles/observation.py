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

    ascii_map: str | None = None
    screen_text: str | None = None
    player_pos: tuple[int, int] | None = None


_TAG_RE = re.compile(r"<[^>]+>")


def _strip_tags(s: str) -> str:
    return _TAG_RE.sub("", s)


def _json_unescape(s: str) -> str:
    try:
        return json.loads(f'"{s}"')
    except Exception:
        return s


def _extract_text_messages_from_msg_tail(msg_tail_items):
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

        for g in text_re.findall(item):
            unescaped = _json_unescape(g)
            out.append(_strip_tags(unescaped).strip())

    dedup = []

    for t in out:
        if not t:
            continue

        if not dedup or dedup[-1] != t:
            dedup.append(t)

    return dedup


def _build_ascii_map_from_screen_text(screen_text: str) -> str | None:
    if not screen_text:
        return None

    lines = [line.rstrip("\n") for line in screen_text.splitlines()]
    if not lines:
        return None

    # 맵 후보 줄만 고른다.
    # @, #, ., †, ∆ 등이 있는 줄을 우선 맵 줄로 본다.
    map_candidates = []
    for line in lines:
        if any(ch in line for ch in ("@", "#", ".", "†", "∆", "<", ">")):
            map_candidates.append(line.rstrip())

    if not map_candidates:
        return None

    cleaned = []

    # 왼쪽 맵 영역만 최대한 남기기
    # 오른쪽 상태창 텍스트(Health, Magic, XL, Place...)가 붙는 경우가 있어
    # 그런 키워드가 나오기 전까지만 잘라낸다.
    cut_keywords = [
        "Health:",
        "Magic:",
        "AC:",
        "EV:",
        "SH:",
        "XL:",
        "Place:",
        "Noise:",
        "Time:",
        "a) ",
        "Throw:",
    ]

    for line in map_candidates:
        cut_pos = len(line)
        for kw in cut_keywords:
            pos = line.find(kw)
            if pos != -1:
                cut_pos = min(cut_pos, pos)

        left = line[:cut_pos].rstrip()

        # 맵 문자만 남긴다. (중요: '.' 포함)
        allowed = set(" #.@<>†∆:+")
        row = "".join(ch for ch in left if ch in allowed)

        # 공백만 있는 줄은 버린다
        if row.strip() and len(row.strip()) >= 8:
            cleaned.append(row.rstrip())

    if not cleaned:
        return None

    return "\n".join(cleaned)


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
    screen_text = s.get("screen_text", "") or ""
    ascii_map = _build_ascii_map_from_screen_text(screen_text)
    player_pos = find_player_position(ascii_map)

    print("=== msg_tail_raw sample ===")
    for i, item in enumerate(msg_tail_raw[:3]):
        print(f"\n--- item {i} ---")
        print(item[:2000] if isinstance(item, str) else item)

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
        screen_text=screen_text,
        ascii_map=ascii_map,
        player_pos=player_pos,
    )


def find_player_position(ascii_map: str):
    lines = ascii_map.splitlines()

    for y, line in enumerate(lines):
        for x, ch in enumerate(line):
            if ch == "@":
                return (x, y)

    return None
