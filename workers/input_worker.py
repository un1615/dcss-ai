# input_worker.py
# Reads run_logs/queue.txt and sends key input to crawl-console window (Windows).
# Uses PID-based window lookup + forced foreground to reduce focus failures.
# Single-instance enforced via Windows Named Mutex.

import os
import sys
import time

import win32con
import win32gui
import win32api
import win32process
import win32event
import psutil

OUT_DIR = r"C:\Users\Oh\Desktop\ai_dcss\run_logs"
QUEUE_PATH = os.path.join(OUT_DIR, "queue.txt")

PROC_NAMES = ["crawl-console.exe", "crawl.exe"]

LAST_ATTACK_TIME = 0.0
ATTACK_MIN_INTERVAL = 0.25

MUTEX_NAME = "Global\\AI_DCSS_INPUT_WORKER_MUTEX_V1"


def acquire_single_instance_or_exit():
    h = win32event.CreateMutex(None, False, MUTEX_NAME)
    err = win32api.GetLastError()
    if err == 183:
        print("[input_worker] another instance is already running -> exit")
        sys.exit(0)
    return h


def find_crawl_pid() -> int | None:
    names = {n.lower() for n in PROC_NAMES}
    for p in psutil.process_iter(["pid", "name"]):
        try:
            name = (p.info.get("name") or "").lower()
            if name in names:
                return int(p.info["pid"])
        except Exception:
            continue
    return None


def find_window_by_pid(target_pid: int):
    result = {"hwnd": None}

    def enum_handler(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        if pid == target_pid:
            result["hwnd"] = hwnd

    win32gui.EnumWindows(enum_handler, None)
    return result["hwnd"]


def force_foreground_window(hwnd: int) -> bool:
    if hwnd is None or not win32gui.IsWindow(hwnd):
        return False
    try:
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)

        fg = win32gui.GetForegroundWindow()
        fg_tid, _ = win32process.GetWindowThreadProcessId(fg) if fg else (0, 0)
        tgt_tid, _ = win32process.GetWindowThreadProcessId(hwnd)

        if fg_tid and fg_tid != tgt_tid:
            win32process.AttachThreadInput(fg_tid, tgt_tid, True)

        try:
            win32gui.SetForegroundWindow(hwnd)
            win32gui.BringWindowToTop(hwnd)
            win32gui.SetActiveWindow(hwnd)
        finally:
            if fg_tid and fg_tid != tgt_tid:
                win32process.AttachThreadInput(fg_tid, tgt_tid, False)

        return win32gui.GetForegroundWindow() == hwnd
    except Exception:
        return False


def focus_crawl_console(crawl_pid: int, retries: int = 10, delay: float = 0.1) -> bool:
    hwnd = find_window_for_crawl(crawl_pid)
    if not hwnd:
        return False
    for _ in range(retries):
        if force_foreground_window(hwnd):
            return True
        time.sleep(delay)
    return False


def press_key(char: str):
    vk = ord(char.upper())
    win32api.keybd_event(vk, 0, 0, 0)
    time.sleep(0.02)
    win32api.keybd_event(vk, 0, win32con.KEYEVENTF_KEYUP, 0)


def press_period():
    VK_OEM_PERIOD = 0xBE
    win32api.keybd_event(VK_OEM_PERIOD, 0, 0, 0)
    time.sleep(0.02)
    win32api.keybd_event(VK_OEM_PERIOD, 0, win32con.KEYEVENTF_KEYUP, 0)


def press_esc():
    win32api.keybd_event(win32con.VK_ESCAPE, 0, 0, 0)
    time.sleep(0.02)
    win32api.keybd_event(win32con.VK_ESCAPE, 0, win32con.KEYEVENTF_KEYUP, 0)


def press_space():
    win32api.keybd_event(win32con.VK_SPACE, 0, 0, 0)
    time.sleep(0.02)
    win32api.keybd_event(win32con.VK_SPACE, 0, win32con.KEYEVENTF_KEYUP, 0)


def press_tab():
    win32api.keybd_event(win32con.VK_TAB, 0, 0, 0)
    time.sleep(0.02)
    win32api.keybd_event(win32con.VK_TAB, 0, win32con.KEYEVENTF_KEYUP, 0)


def pop_queue():
    if not os.path.exists(QUEUE_PATH):
        return None
    try:
        with open(QUEUE_PATH, "r", encoding="utf-8", errors="ignore") as f:
            lines = [ln.strip() for ln in f.readlines()]
        lines = [ln for ln in lines if ln]
        if not lines:
            return None

        cmd = lines[0]
        rest = lines[1:]
        with open(QUEUE_PATH, "w", encoding="utf-8") as f:
            f.write("\n".join(rest))
        return cmd
    except Exception:
        return None


def push_front_queue(cmd: str) -> None:
    cmd = (cmd or "").strip()
    if not cmd:
        return
    try:
        if os.path.exists(QUEUE_PATH):
            with open(QUEUE_PATH, "r", encoding="utf-8", errors="ignore") as f:
                rest = [ln.strip() for ln in f.readlines() if ln.strip()]
        else:
            rest = []
        with open(QUEUE_PATH, "w", encoding="utf-8") as f:
            f.write(cmd + "\n")
            if rest:
                f.write("\n".join(rest) + "\n")
    except Exception:
        pass


def find_console_hwnd_fallback():
    # 콘솔 창(DCSS 콘솔)들은 대개 이 클래스명
    try:
        hwnd = win32gui.FindWindow("ConsoleWindowClass", None)
        if hwnd and win32gui.IsWindowVisible(hwnd):
            return hwnd
    except Exception:
        pass
    return None


def find_window_for_crawl(crawl_pid: int):
    # 1) PID 기반
    hwnd = find_window_by_pid(crawl_pid)
    if hwnd:
        return hwnd

    # 2) fallback: 콘솔 클래스 창 하나라도 잡기
    return find_console_hwnd_fallback()


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    mutex_handle = acquire_single_instance_or_exit()
    print("[input_worker] start")

    crawl_pid = None
    last_pid_check = 0.0

    while True:
        cmd = pop_queue()
        if not cmd:
            time.sleep(0.05)
            continue

        now = time.time()
        if (crawl_pid is None) or (now - last_pid_check > 2.0):
            crawl_pid = find_crawl_pid()
            last_pid_check = now

        if not crawl_pid:
            print(f"[input_worker] crawl pid not found for cmd={cmd}")
            continue

        if not focus_crawl_console(crawl_pid):
            crawl_pid = find_crawl_pid()
            last_pid_check = now
            if not crawl_pid or (not focus_crawl_console(crawl_pid)):
                print(
                    f"[input_worker] failed to focus window for cmd={cmd} pid={crawl_pid}"
                )
                push_front_queue(cmd)
                time.sleep(0.2)
                continue

        if cmd == "WAIT":
            press_period()
            print("[input_worker] sent: . (wait)")

        elif cmd == "AUTOEXPLORE":
            press_key("o")
            print("[input_worker] sent: o (autoexplore)")

        elif cmd == "CONFIRM_Y":
            press_key("y")
            print("[input_worker] sent: y (confirm)")

        elif cmd == "ESC":
            press_esc()
            print("[input_worker] sent: ESC")

        elif cmd == "MORE":
            press_space()
            print("[input_worker] sent: SPACE (more)")

        elif cmd == "ATTACK":
            now2 = time.time()
            if (now2 - LAST_ATTACK_TIME) < ATTACK_MIN_INTERVAL:
                push_front_queue(cmd)
                time.sleep(0.05)
                continue
            press_tab()
            LAST_ATTACK_TIME = now2
            print("[input_worker] sent: TAB (attack)")

        elif cmd.startswith("MOVE "):
            parts = cmd.split()
            if len(parts) == 2 and len(parts[1]) == 1:
                press_key(parts[1])
                print(f"[input_worker] sent: {parts[1]} (move)")
            else:
                print(f"[input_worker] bad MOVE cmd={cmd}")

        elif cmd.startswith("KEYS "):
            # multiple sequential keypresses, e.g. "KEYS za."
            seq = cmd[5:].strip()
            if seq:
                for ch in seq:
                    if ch == " ":
                        continue
                    if ch == ".":
                        press_period()
                    elif ch == "\x1b":
                        press_esc()
                    else:
                        press_key(ch)
                    time.sleep(0.03)
                print(f"[input_worker] sent: {seq} (keys)")
            else:
                print(f"[input_worker] bad KEYS cmd={cmd}")

        elif cmd.startswith("KEY "):
            parts = cmd.split()
            if len(parts) == 2 and len(parts[1]) == 1:
                press_key(parts[1])
                print(f"[input_worker] sent: {parts[1]} (key)")
            else:
                print(f"[input_worker] bad KEY cmd={cmd}")

        else:
            print(f"[input_worker] unknown cmd={cmd}")
