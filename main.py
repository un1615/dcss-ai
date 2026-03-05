# main.py (controller) - V3: minimal controller, AI decides; robust turn sync + failure feedback
import os
import sys
import time
import json
import subprocess
import re
from collections import deque

from controller.action_to_queue import action_json_to_queue
from policy.policy_openai import choose_action_openai
from webtiles.webtiles_reader import get_state
from webtiles.webtiles_input import send_keys

OUT_DIR = r"C:\Users\Oh\Desktop\ai_dcss\run_logs"
DUMP_PATH = os.path.join(OUT_DIR, "console_dump.txt")
QUEUE_PATH = os.path.join(OUT_DIR, "queue.txt")

# --- OBS only (no forced FSM) ---
CAUTION_ENTER = 0.75
PANIC_ENTER = 0.45

# --- loop / sync ---
LOOP_SLEEP = 0.02
HP_RATIO_BUF = 3

# action failure detection
FAIL_TIMEOUT_SEC = 0.35  # if TIME doesn't advance after this, treat as failed action
MAX_STUCK_BEFORE_HINT = 2  # after N fails, strongly hint AI to change action/dir

TIME_RE = re.compile(r"Time:\s*([0-9]+(?:\.[0-9]+)?)", re.IGNORECASE)
HP_RE = re.compile(r"Health:\s*(\d+)\s*/\s*(\d+)", re.IGNORECASE)
MP_RE = re.compile(r"Magic:\s*(\d+)\s*/\s*(\d+)", re.IGNORECASE)

MORE_RE = re.compile(r"--more--", re.IGNORECASE)
CONFIRM_RE = re.compile(r"\(y/n\)", re.IGNORECASE)
LEVELUP_RE = re.compile(
    r"increase\s+\(s\)trength,\s+\(i\)ntelligence,\s+or\s+\(d\)exterity\?",
    re.IGNORECASE,
)

# Right panel monster line (best-effort; your reader dump may not include the real panel reliably)
MON_LINE_RE = re.compile(r"^\s*([a-zA-Z0-9])\s*[|│]\s*(.+?)\s*$")


def kill_process_tree(pid: int) -> None:
    subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True)


def read_dump_text() -> str:
    try:
        with open(DUMP_PATH, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except FileNotFoundError:
        return ""


def is_queue_empty(path: str) -> bool:
    try:
        if not os.path.exists(path):
            return True
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return len(f.read().strip()) == 0
    except Exception:
        return True


def clear_queue(path: str) -> None:
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write("")
    except Exception:
        pass


def parse_hp(text: str):
    m = HP_RE.search(text)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def parse_mp(text: str):
    m = MP_RE.search(text)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def hp_ratio(hp):
    if not hp:
        return None
    cur, mx = hp
    if mx <= 0:
        return 0.0
    r = cur / mx
    if r < 0.0:
        r = 0.0
    if r > 1.0:
        r = 1.0
    return r


def get_turn_token(text: str) -> str:
    """If a real turn passes, Time almost always changes."""
    m = TIME_RE.search(text)
    return m.group(1) if m else "NA"


def extract_messages_tail(text: str, n: int = 35):
    lines = [ln.rstrip("\n") for ln in text.splitlines()]
    return lines[-n:] if len(lines) >= n else lines


def extract_monsters_panel(text: str, max_n: int = 10):
    mons = []
    for ln in text.splitlines():
        m = MON_LINE_RE.match(ln)
        if m:
            glyph = m.group(1)
            name = m.group(2).strip()
            if name and len(name) <= 80:
                mons.append({"glyph": glyph, "name": name})
    return mons[:max_n]


def detect_prompts(text: str) -> dict:
    return {
        "more": bool(MORE_RE.search(text)),
        "confirm_yn": bool(CONFIRM_RE.search(text)),
        "levelup": bool(LEVELUP_RE.search(text)),
    }


def detect_flags(text: str) -> dict:
    low = text.lower()
    return {
        "move_blocked": ("there's something in the way" in low),
        "poisoned": ("you feel sick" in low or "pois" in low or "poison" in low),
    }


def resolve_prompt_to_action(prompts: dict) -> dict | None:
    # Controller ONLY resolves UI prompts to avoid desync.
    if prompts.get("more"):
        return {"type": "more", "reason": "auto-resolve --more--"}
    if prompts.get("levelup"):
        # minimal: STR (s)
        return {"type": "levelup", "key": "s", "reason": "auto-pick levelup: STR"}
    if prompts.get("confirm_yn"):
        # safer default: n (you can later let AI decide)
        return {"type": "confirm", "key": "n", "reason": "auto-default confirm: n"}
    return None


def build_obs(text: str, stable_ratio: float | None, extra: dict):
    hp = parse_hp(text)
    mp = parse_mp(text)
    prompts = detect_prompts(text)
    flags = detect_flags(text)

    mode = "NORMAL"
    if stable_ratio is not None:
        if stable_ratio < PANIC_ENTER:
            mode = "PANIC"
        elif stable_ratio < CAUTION_ENTER:
            mode = "CAUTION"

    obs = {
        "mode": mode,
        "hp": hp,
        "hp_ratio": stable_ratio,
        "mp": mp,
        "prompts": prompts,
        "flags": flags,
        "monsters_panel": extract_monsters_panel(text),
        "messages_tail": extract_messages_tail(text, n=35),
        # the AI is only allowed to output these
        "allowed_actions": [
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
        "move_keys": ["h", "j", "k", "l", "y", "u", "b", "n"],
    }
    obs.update(extra or {})
    return obs


def send_and_wait_turn(keys: str, max_wait_sec: float = 2.0, poll_sec: float = 0.05):
    s0 = get_state()
    t0 = s0.get("turn")

    send_keys(keys)

    start = time.time()
    while True:
        s1 = get_state()
        t1 = s1.get("turn")
        if t0 is not None and t1 is not None and t1 != t0:
            return s0, s1

        if time.time() - start > max_wait_sec:
            return s0, s1

        time.sleep(poll_sec)


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)

    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    reader_worker = subprocess.Popen(
        [sys.executable, "workers/reader_worker.py"], creationflags=creationflags
    )
    input_worker = subprocess.Popen(
        [sys.executable, "workers/input_worker.py"], creationflags=creationflags
    )

    print(f"[controller] reader_worker pid={reader_worker.pid} started.")
    print(f"[controller] input_worker  pid={input_worker.pid} started.")
    print("[controller] Press Ctrl+C to stop.")

    ratio_buf = deque(maxlen=HP_RATIO_BUF)

    # turn sync state
    last_sent_turn = None
    waiting_turn_advance = False
    sent_at = 0.0

    # last action feedback
    last_action = None
    stuck_count = 0
    last_action_failed = False

    try:
        while True:
            text = read_dump_text()
            turn = get_turn_token(text)

            hp = parse_hp(text)
            r = hp_ratio(hp)
            if r is None:
                time.sleep(0.05)
                continue
            ratio_buf.append(r)
            stable_ratio = min(ratio_buf) if len(ratio_buf) else r

            # if queue has pending commands, wait for input_worker to consume
            if not is_queue_empty(QUEUE_PATH):
                time.sleep(LOOP_SLEEP)
                continue

            # if we sent an action, wait for turn to advance; if not, mark failure
            if waiting_turn_advance:
                if turn != last_sent_turn:
                    waiting_turn_advance = False
                    last_action_failed = False
                    stuck_count = 0
                else:
                    if time.time() - sent_at > FAIL_TIMEOUT_SEC:
                        waiting_turn_advance = False
                        last_action_failed = True
                        stuck_count += 1
                        print(
                            f"[WARN] turn did not advance (TIME unchanged) -> action failed; stuck_count={stuck_count}"
                        )
                    else:
                        time.sleep(0.01)
                        continue

            # build obs (+ failure feedback)
            extra = {
                "turn_time": turn,
                "last_action": last_action,
                "last_action_failed": last_action_failed,
                "stuck_count": stuck_count,
            }

            obs = build_obs(text, stable_ratio, extra)

            # Controller resolves UI prompts only
            prompt_action = resolve_prompt_to_action(obs["prompts"])
            if prompt_action is not None:
                action_str = json.dumps(prompt_action, ensure_ascii=False)
                dbg = action_json_to_queue(action_str, QUEUE_PATH)
                last_action = prompt_action
                last_sent_turn = turn
                waiting_turn_advance = True
                sent_at = time.time()
                print("[PROMPT]", prompt_action, dbg)
                time.sleep(LOOP_SLEEP)
                continue

            # If we're stuck, strongly hint: don't repeat same move dir
            if obs["stuck_count"] >= MAX_STUCK_BEFORE_HINT:
                obs["hint"] = (
                    "Last actions failed (TIME not advancing). Avoid repeating the same blocked move; choose different direction or different action (attack/wait/keys)."
                )

            # Ask AI (ONE action)
            action_json = choose_action_openai(obs)

            try:
                action_obj = json.loads(action_json)
            except Exception:
                # Should not happen if tool forcing works; safe fallback
                action_obj = {
                    "type": "wait",
                    "reason": "controller_parse_fail_safe",
                    "risk": "low",
                }
                action_json = json.dumps(action_obj, ensure_ascii=False)

            # Optional: if move is blocked message exists, and AI repeats same move, you can still allow (AI learns),
            # but we add a small controller safety nudge: if blocked and same move repeated 3+ times, force WAIT once
            if (
                obs["flags"].get("move_blocked")
                and obs["stuck_count"] >= 3
                and action_obj.get("type") == "move"
            ):
                action_obj = {
                    "type": "wait",
                    "reason": "forced_wait_break_stuck",
                    "risk": "med",
                }
                action_json = json.dumps(action_obj, ensure_ascii=False)

            dbg = action_json_to_queue(action_json, QUEUE_PATH)

            last_action = action_obj
            last_sent_turn = turn
            waiting_turn_advance = True
            sent_at = time.time()

            print("[AI]", action_json, dbg)
            time.sleep(LOOP_SLEEP)

    except KeyboardInterrupt:
        print("\n[controller] Ctrl+C received. Stopping workers...")
    except Exception as e:
        # SUPER IMPORTANT: ensure we kill children even on OpenAI errors etc.
        print(f"\n[controller] ERROR: {e}")
    finally:
        try:
            kill_process_tree(reader_worker.pid)
        except Exception:
            pass
        try:
            kill_process_tree(input_worker.pid)
        except Exception:
            pass
        print("[controller] stopped.")
