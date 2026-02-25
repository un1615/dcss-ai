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

MON_PANEL_RE = re.compile(
    r"^\s*[A-Za-z]\s{2,}([a-zA-Z][a-zA-Z '\-]+)\s*\(([^)]*)\)\s*$"
)
NEARBY_RE = re.compile(r"_A (.+?) is nearby!", re.IGNORECASE)


def detect_flags_from_text(text: str) -> dict:
    lines = text.splitlines()

    # 1) 최근 메시지(아래쪽)만 보는 용도
    recent = "\n".join([ln.lower() for ln in lines[-15:]])

    confirm_y = ("(y/n)" in recent) or ("pick up" in recent and "y/n" in recent)
    shop_like = "welcome to" in recent and "shop" in recent

    # 2) 'nearby' 메시지 기반(현재 위협 신호)
    nearby = []
    for ln in lines[-30:]:  # 메시지는 보통 아래쪽에 몰림
        m = NEARBY_RE.search(ln)
        if m:
            nearby.append(m.group(1).strip())

    # 3) 우측 패널 몬스터 라인 기반(가장 강력)
    monsters_panel = []
    for ln in lines:
        # 예: "S   ball python (constriction, asleep)"
        m = MON_PANEL_RE.match(ln)
        if m:
            name = m.group(1).strip()
            status = m.group(2).strip().lower()
            monsters_panel.append((name, status))

    # 4) 기존 'comes into view'는 "발견 이벤트"로만(진입 트리거용)
    monster_seen_msg = "comes into view" in recent

    monsters_present = (len(monsters_panel) > 0) or (len(nearby) > 0)

    return {
        "confirm_y": confirm_y,
        "shop_like": shop_like,
        # 발견 이벤트(에지 트리거용)
        "monster_seen": monster_seen_msg,
        # 상태 확인(유지/판단용)
        "monsters_present": monsters_present,
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
    ALERT_HOLD_SEC = 3.0  # 몬스터 감지 후, 탐색을 최소 3초 멈춤
    alert_action_done = False
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
                    f.write("WAIT\nWAIT\nWAIT\n")
                print("[PLAN] wrote PANIC queue: WAIT x3")

            if mode != last_mode:
                print(f"[MODE] {last_mode} -> {mode} (hp={stable_ratio*100:.1f}%)")
                last_mode = mode

            # ===== Explore policy (FSM 기반) =====

            if mode == "PANIC":
                print("[INFO] PANIC -> skip explore policy")

            else:
                flags = detect_flags_from_text(text)
                seen_now = flags.get("monsters_present", False) or flags.get(
                    "monster_seen", False
                )
                monster_edge = seen_now and not last_monster_seen
                last_monster_seen = seen_now

                now = time.time()

                # ---- FSM transition ----
                if monster_edge:
                    ai_state = "ALERT"
                    alert_until = now + ALERT_HOLD_SEC
                    alert_action_done = False

                if ai_state == "ALERT" and now >= alert_until:
                    if flags.get("monsters_present", False):
                        alert_until = now + 1.0
                        print("[INFO] ALERT extend (monster still visible)")
                    else:
                        ai_state = "EXPLORE"

                # ---- 메뉴/프롬프트 우선 처리 ----
                if flags.get("shop_like") and is_queue_empty(QUEUE_PATH):
                    with open(QUEUE_PATH, "w", encoding="utf-8") as f:
                        f.write("ESC\n")
                    print("[PLAN] shop screen -> queued ESC")

                elif flags["confirm_y"] and is_queue_empty(QUEUE_PATH):
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

                    elif ai_state == "EXPLORE":
                        if mode in ("NORMAL", "CAUTION") and is_queue_empty(QUEUE_PATH):
                            if now - last_autoexplore_time >= AUTOEXPLORE_COOLDOWN:
                                with open(QUEUE_PATH, "w", encoding="utf-8") as f:
                                    f.write("AUTOEXPLORE\n")
                                last_autoexplore_time = now
                                print("[PLAN] EXPLORE -> queued AUTOEXPLORE")

            print(f"HP parsed: {hp}")
            print(f"HP%: {stable_ratio*100:.1f}% (raw={ratio*100:.1f}%)")
            time.sleep(1.0)

    except KeyboardInterrupt:
        print("\n[controller] Ctrl+C received. Stopping workers...")
        kill_process_tree(reader_worker.pid)
        kill_process_tree(input_worker.pid)
        print("[controller] stopped.")
