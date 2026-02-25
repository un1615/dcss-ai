# main.py (controller)
import os
import sys
import time
import subprocess
from collections import deque

# NOTE:
# - This controller MUST NOT call AttachConsole / ReadConsoleOutputCharacter.
# - It reads run_logs/console_dump.txt written by reader_worker.py.
# - Ctrl+C is handled here and will reliably stop both workers.

OUT_DIR = r"C:\Users\Oh\Desktop\ai_dcss\run_logs"
DUMP_PATH = os.path.join(OUT_DIR, "console_dump.txt")
CMD_PATH = os.path.join(OUT_DIR, "command.txt")
QUEUE_PATH = os.path.join(OUT_DIR, "queue.txt")

# HP thresholds (with hysteresis)
CAUTION_ENTER = 0.55
CAUTION_EXIT = 0.65
PANIC_ENTER = 0.30
PANIC_EXIT = 0.40


def kill_process_tree(pid: int) -> None:
    """Hard stop a process + its children on Windows."""
    subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True)


def read_dump_text() -> str:
    try:
        with open(DUMP_PATH, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except FileNotFoundError:
        return ""


def is_queue_empty(queue_path: str) -> bool:
    try:
        if not os.path.exists(queue_path):
            return True
        with open(queue_path, "r", encoding="utf-8", errors="ignore") as f:
            return len(f.read().strip()) == 0
    except Exception:
        return True


import re

MON_PANEL_RE = re.compile(r"^\s*([A-Za-z]+)\s+(.+?)(?:\s*\(([^)]*)\))?\s*$")
NEARBY_RE = re.compile(r"_?\s*(?:a|an)\s+(.+?)\s+is nearby!", re.IGNORECASE)


def detect_flags_from_text(text: str) -> dict:
    lines = text.splitlines()

    # 1) 최근 메시지(아래쪽)만 보는 용도
    recent = "\n".join([ln.lower() for ln in lines[-15:]])
    generic_nearby = "there are monsters nearby" in recent

    # ✅ 추가: 근접 전투/포위 신호 감지
    melee_contact = (
        "hits you" in recent
        or "misses you" in recent
        or "closely misses you" in recent
        or "you encounter" in recent
    )
    confirm_y = ("(y/n)" in recent) or ("pick up" in recent and "y/n" in recent)
    shop_like = "welcome to" in recent and "shop" in recent

    # 2) 'nearby' 메시지 기반(현재 위협 신호)
    nearby = []
    for ln in lines[-40:]:
        s = ln.strip()
        # 정확히 "... is nearby!" 형식만 인정
        if s.lower().endswith("is nearby!") or s.lower().endswith("are nearby!"):
            m = NEARBY_RE.search(s)
            if m:
                nearby.append(m.group(1).strip())

    # 3) 우측 패널 몬스터 라인 기반(가장 강력)
    monsters_panel = []
    for ln in lines:
        # 예: "S   ball python (constriction, asleep)"
        m = MON_PANEL_RE.match(ln)
        if m:
            glyph = m.group(1)  # g, ggg 같은 것
            name = m.group(2).strip()  # Robin, hobgoblin, 3 goblins 등
            status = (m.group(3) or "").strip().lower()
            monsters_panel.append((name, status))

    # 4) 기존 'comes into view'는 "발견 이벤트"로만(진입 트리거용)
    monster_seen_msg = "comes into view" in recent

    monsters_present = (len(monsters_panel) > 0) or (len(nearby) > 0) or generic_nearby
    # ✅ 추가: count + asleep 플래그
    monster_count = len(monsters_panel) if len(monsters_panel) > 0 else len(nearby)
    if monster_count == 0 and monsters_present:
        monster_count = 1
    monster_asleep = any("asleep" in status for (_, status) in monsters_panel) or (
        "(asleep)" in text.lower()
    )
    return {
        "confirm_y": confirm_y,
        "shop_like": shop_like,
        # 발견 이벤트(에지 트리거용)
        "monster_seen": monster_seen_msg,
        # 상태 확인(유지/판단용)
        "monsters_present": monsters_present,
        "monster_count": monster_count,
        "monster_asleep": monster_asleep,
        "melee_contact": melee_contact,
        "monsters_panel": monsters_panel[:5],
        "nearby": nearby[:5],
    }


# --- parsing / ratio ---
try:
    from core.state_parser import parse_hp, compute_hp_ratio  # preferred
except Exception:
    # fallback (keeps controller runnable even if core/state_parser.py isn't updated yet)
    import re

    def parse_hp(text: str):
        m = re.search(r"Health:\s*(\d+)/(\d+)", text)
        if m:
            return int(m.group(1)), int(m.group(2))
        return None

    def compute_hp_ratio(hp):
        if not hp:
            return None
        cur, max_ = hp
        if max_ <= 0:
            return 0.0
        r = cur / max_
        if r < 0.0:
            return 0.0
        if r > 1.0:
            return 1.0
        return r


def update_mode(last_mode: str, hp_ratio: float) -> str:
    """3-state mode with hysteresis to avoid flapping."""
    mode = last_mode

    if last_mode == "NORMAL":
        if hp_ratio < PANIC_ENTER:
            mode = "PANIC"
        elif hp_ratio < CAUTION_ENTER:
            mode = "CAUTION"

    elif last_mode == "CAUTION":
        if hp_ratio < PANIC_ENTER:
            mode = "PANIC"
        elif hp_ratio >= CAUTION_EXIT:
            mode = "NORMAL"

    else:  # PANIC
        if hp_ratio >= PANIC_EXIT:
            mode = "CAUTION"

    return mode


def emit_command(cmd: str) -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(CMD_PATH, "w", encoding="utf-8") as f:
        f.write(cmd)


def evaluate_threat(flags, mode):
    # HP가 위험하면 무조건 HIGH
    if mode == "PANIC":
        return "HIGH"
    if mode == "CAUTION":
        return "HIGH"

    # ✅ 추가: 근접 전투/포위 신호면 무조건 HIGH
    if flags.get("melee_contact", False):
        return "HIGH"

    # 몬스터 없으면 LOW
    if not flags.get("monsters_present", False) and not flags.get(
        "monster_seen", False
    ):
        return "LOW"

    count = flags.get("monster_count", 1)
    asleep = flags.get("monster_asleep", False)

    # 2마리 이상이면 위험
    if count >= 2:
        return "HIGH"

    # 1마리 + asleep + HP 정상 => 안전(공격 가능)
    if count == 1 and asleep and mode == "NORMAL":
        return "LOW"

    # 그 외는 애매(일단 MID)
    return "MID"


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)

    # Start workers
    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0

    reader_worker = subprocess.Popen(
        [sys.executable, "reader_worker.py"], creationflags=creationflags
    )
    input_worker = subprocess.Popen(
        [sys.executable, "input_worker.py"], creationflags=creationflags
    )

    print(f"[controller] reader_worker pid={reader_worker.pid} started.")
    print(f"[controller] input_worker  pid={input_worker.pid} started.")
    print("[controller] Press Ctrl+C to stop.")

    ratio_buf = deque(maxlen=3)  # use conservative min() for survival
    last_mode = "NORMAL"

    last_autoexplore_time = 0.0
    AUTOEXPLORE_COOLDOWN = 3.0
    last_monster_seen = False
    ai_state = "EXPLORE"
    alert_until = 0.0  # ALERT 상태 유지 시간(초)
    RETREAT_HOLD_SEC = 3.0
    retreat_until = 0.0
    ALERT_HOLD_SEC = 3.0  # 몬스터 감지 후, 탐색을 최소 3초 멈춤
    alert_action_done = False
    repeat_esc_sent = False
    more_sent = False
    no_monsters_streak = 0
    NO_MONSTERS_CONFIRM = 2  # 2프레임 연속 "없음"이면 진짜 없음으로 인정
    try:

        while True:
            text = read_dump_text()
            hp = parse_hp(text)
            ratio = compute_hp_ratio(hp)

            if ratio is None:
                print("[HP] not found (frame skip)")
                time.sleep(1.0)
                continue

            ratio_buf.append(ratio)
            stable_ratio = min(ratio_buf)
            if last_mode == "PANIC":
                stable_ratio = ratio
            # HP가 정상(>= CAUTION_EXIT)으로 올라오면 버퍼 리셋해서 stale min 제거
            if ratio >= CAUTION_EXIT and stable_ratio < CAUTION_EXIT:
                ratio_buf.clear()
                ratio_buf.append(ratio)
                stable_ratio = ratio

            mode = update_mode(last_mode, stable_ratio)

            # PANIC에 "진입한 순간"에만 계획(큐) 작성 — 스팸 방지
            if mode == "PANIC" and last_mode != "PANIC":
                os.makedirs(OUT_DIR, exist_ok=True)
                with open(QUEUE_PATH, "w", encoding="utf-8") as f:
                    f.write("MOVE h\nMOVE j\nMOVE l\n")
                print("[PLAN] wrote PANIC queue: MOVE x3")

            if mode != last_mode:
                print(f"[MODE] {last_mode} -> {mode} (hp={stable_ratio*100:.1f}%)")
                last_mode = mode

            # ===== Explore policy (FSM 기반) =====

            if mode == "PANIC":
                # PANIC: 계속 도망 (큐가 비면 한 칸 이동)
                if is_queue_empty(QUEUE_PATH):
                    with open(QUEUE_PATH, "w", encoding="utf-8") as f:
                        f.write("MOVE h\n")  # 일단 고정: 왼쪽(안전 확인용)
                    print("[PLAN] PANIC -> queued MOVE h")
                print("[INFO] PANIC -> skip explore policy")

            else:
                flags = detect_flags_from_text(text)
                # ---- no_monsters_streak 업데이트 ----
                if flags.get("monsters_present", False):
                    no_monsters_streak = 0
                else:
                    no_monsters_streak += 1
                flags["melee_contact"] = bool(flags.get("melee_contact")) and bool(
                    flags.get("monsters_present")
                )
                print(f"[DBG2] monsters_panel={flags.get('monsters_panel')}")
                print(
                    f"[DBG2] nearby={flags.get('nearby')}, monsters_present={flags.get('monsters_present')}, monster_seen={flags.get('monster_seen')}"
                )
                seen_now = flags.get("monsters_present", False) or flags.get(
                    "monster_seen", False
                )
                monster_edge = seen_now and not last_monster_seen
                last_monster_seen = seen_now

                now = time.time()

                # ---- FSM transition ----
                just_entered_alert = False

                if monster_edge:
                    ai_state = "ALERT"
                    alert_until = now + ALERT_HOLD_SEC
                    alert_action_done = False
                    just_entered_alert = True

                if ai_state == "ALERT" and now >= alert_until:
                    if flags.get("monsters_present", False):
                        alert_until = now + 1.0
                        print("[INFO] ALERT extend (monster still visible)")
                    else:
                        if no_monsters_streak >= NO_MONSTERS_CONFIRM:
                            ai_state = "EXPLORE"
                            print("[STATE] ALERT -> EXPLORE (confirmed no monsters)")
                        else:
                            alert_until = now + 0.5
                            print("[INFO] ALERT hold (no_monsters not confirmed yet)")

                # ---- threat-based transition (DEBUG 포함) ----
                if ai_state == "ALERT" and not just_entered_alert:
                    threat = evaluate_threat(flags, mode)
                    print(
                        f"[DEBUG] threat={threat}, mode={mode}, count={flags.get('monster_count')}, "
                        f"asleep={flags.get('monster_asleep')}, melee={flags.get('melee_contact')}, "
                        f"monsters_present={flags.get('monsters_present')}"
                    )

                    if threat == "HIGH":
                        # ✅ HP가 낮으면 싸우지 말고 후퇴가 우선
                        if mode in ("CAUTION", "PANIC"):
                            print("[STATE] ALERT -> RETREAT (HIGH but low HP)")
                            ai_state = "RETREAT"
                            retreat_until = now + RETREAT_HOLD_SEC
                        else:
                            print("[STATE] ALERT -> FIGHT (HIGH: melee/breakout)")
                            ai_state = "FIGHT"

                    elif threat == "MID":
                        # MID는 아직 보수적으로 후퇴 (나중에 FIGHT로 일부 전환)
                        print("[STATE] ALERT -> RETREAT (MID)")
                        ai_state = "RETREAT"
                        retreat_until = now + RETREAT_HOLD_SEC

                    elif threat == "LOW":
                        if no_monsters_streak >= NO_MONSTERS_CONFIRM:
                            print("[STATE] ALERT -> EXPLORE (confirmed no monsters)")
                            ai_state = "EXPLORE"
                        else:
                            print("[INFO] ALERT hold (LOW but not confirmed)")
                            alert_until = now + 0.5

                # ---- RETREAT exit conditions ----
                if ai_state == "RETREAT":
                    no_monsters = (not flags.get("monsters_present", False)) and (
                        not flags.get("monster_seen", False)
                    )

                    if no_monsters:
                        print("[STATE] RETREAT -> EXPLORE (no monsters)")
                        ai_state = "EXPLORE"
                        alert_action_done = False

                    elif now >= retreat_until:
                        if mode in ("CAUTION", "PANIC") and flags.get(
                            "monsters_present", False
                        ):
                            # HP 낮고 아직 적이 보이면, 후퇴 계속
                            print("[STATE] RETREAT extend (low HP & monsters present)")
                            retreat_until = now + RETREAT_HOLD_SEC
                        else:
                            print("[STATE] RETREAT timeout -> EXPLORE")
                            ai_state = "EXPLORE"

                more_prompt = "--more--" in text.lower()
                if more_prompt:
                    if (not more_sent) and is_queue_empty(QUEUE_PATH):
                        with open(QUEUE_PATH, "w", encoding="utf-8") as f:
                            f.write("MORE\n")
                        more_sent = True
                        print("[PLAN] more prompt -> queued MORE (once)")
                else:
                    if more_sent:
                        print("[INFO] more prompt cleared")
                    more_sent = False

                # ---- repeat command 프롬프트 처리 ----
                repeat_prompt = (
                    "number of times to repeat" in text.lower()
                    and "command key" in text.lower()
                )

                if repeat_prompt:
                    # 프롬프트가 떠 있는 동안엔 탐색/전투 정책을 멈추고 ESC만 관리
                    if (not repeat_esc_sent) and is_queue_empty(QUEUE_PATH):
                        with open(QUEUE_PATH, "w", encoding="utf-8") as f:
                            f.write("ESC\n")
                        repeat_esc_sent = True
                        print("[PLAN] repeat prompt -> queued ESC (once)")
                else:
                    # 프롬프트가 사라지면 다음에 또 쓸 수 있도록 리셋
                    if repeat_esc_sent:
                        print("[INFO] repeat prompt cleared")
                    repeat_esc_sent = False

                if not repeat_prompt and not more_prompt:
                    # ---- 메뉴/프롬프트 우선 처리 ----
                    if flags.get("shop_like") and is_queue_empty(QUEUE_PATH):
                        with open(QUEUE_PATH, "w", encoding="utf-8") as f:
                            f.write("ESC\n")
                        print("[PLAN] shop screen -> queued ESC")

                    elif flags.get("confirm_y") and is_queue_empty(QUEUE_PATH):
                        with open(QUEUE_PATH, "w", encoding="utf-8") as f:
                            f.write("CONFIRM_Y\n")
                        print("[PLAN] confirm prompt -> queued CONFIRM_Y")

                    # ---- FSM actions ----
                    else:
                        if ai_state == "ALERT":
                            if (not alert_action_done) and is_queue_empty(QUEUE_PATH):
                                with open(QUEUE_PATH, "w", encoding="utf-8") as f:
                                    f.write("WAIT\n")
                                print("[PLAN] ALERT -> queued WAIT x1")
                                alert_action_done = True
                            print("[INFO] ALERT: holding explore")

                        elif ai_state == "RETREAT":
                            if is_queue_empty(QUEUE_PATH):
                                import random

                                move_keys = ["h", "j", "k", "l", "y", "u", "b", "n"]
                                key = random.choice(move_keys)
                                with open(QUEUE_PATH, "w", encoding="utf-8") as f:
                                    f.write(f"MOVE {key}\n")
                                print(f"[PLAN] RETREAT -> queued MOVE {key}")
                            print("[INFO] RETREAT: trying to move away")

                        elif ai_state == "FIGHT":
                            if is_queue_empty(QUEUE_PATH):
                                with open(QUEUE_PATH, "w", encoding="utf-8") as f:
                                    f.write("ATTACK\n")
                                print("[PLAN] FIGHT -> queued ATTACK (TAB)")

                                # ✅ 공격 후 바로 ALERT로 복귀해서 재평가
                                ai_state = "ALERT"
                                alert_until = now + 0.5
                                alert_action_done = False

                        elif ai_state == "EXPLORE" and not flags.get(
                            "monsters_present", False
                        ):
                            if is_queue_empty(QUEUE_PATH):
                                if mode == "NORMAL":
                                    if (
                                        now - last_autoexplore_time
                                        >= AUTOEXPLORE_COOLDOWN
                                    ):
                                        with open(
                                            QUEUE_PATH, "w", encoding="utf-8"
                                        ) as f:
                                            f.write("AUTOEXPLORE\n")
                                        last_autoexplore_time = now
                                        print("[PLAN] EXPLORE -> queued AUTOEXPLORE")
                                else:
                                    # CAUTION/PANIC 등: 일단 안전하게 피 회복(휴식)
                                    with open(QUEUE_PATH, "w", encoding="utf-8") as f:
                                        f.write("WAIT\n")
                                    print("[PLAN] EXPLORE(CAUTION) -> queued WAIT")

            print(f"HP parsed: {hp}")
            print(f"HP%: {stable_ratio*100:.1f}% (raw={ratio*100:.1f}%)")
            time.sleep(1.0)

    except KeyboardInterrupt:
        print("\n[controller] Ctrl+C received. Stopping workers...")
        kill_process_tree(reader_worker.pid)
        kill_process_tree(input_worker.pid)
        print("[controller] stopped.")
