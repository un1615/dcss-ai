# input_worker.py
# Reads run_logs/queue.txt and sends key input to crawl-console window (Windows).
# Uses PID-based window lookup + forced foreground to reduce focus failures.

import os
import time
import win32con
import win32gui
import win32api
import win32process

import psutil

OUT_DIR = r"C:\Users\Oh\Desktop\ai_dcss\run_logs"
QUEUE_PATH = os.path.join(OUT_DIR, "queue.txt")

# process name candidates (adjust if needed)
PROC_NAMES = ["crawl-console.exe", "crawl.exe"]


def find_crawl_pid() -> int | None:
    """Find PID of crawl-console process."""
    for p in psutil.process_iter(["pid", "name"]):
        try:
            name = (p.info.get("name") or "").lower()
            if name in [n.lower() for n in PROC_NAMES]:
                return int(p.info["pid"])
        except Exception:
            continue
    return None


def find_window_by_pid(target_pid: int):
    """Return first visible top-level hwnd owned by target_pid, else None."""
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
    """Best-effort: bring hwnd to foreground even under focus restrictions."""
    if hwnd is None or not win32gui.IsWindow(hwnd):
        return False

    try:
        # Restore if minimized
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)

        fg = win32gui.GetForegroundWindow()
        fg_tid, _ = win32process.GetWindowThreadProcessId(fg) if fg else (0, 0)
        tgt_tid, _ = win32process.GetWindowThreadProcessId(hwnd)

        # Attach input threads to bypass focus-stealing restrictions
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
    hwnd = find_window_by_pid(crawl_pid)
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
    VK_OEM_PERIOD = 0xBE  # '.' key
    win32api.keybd_event(VK_OEM_PERIOD, 0, 0, 0)
    time.sleep(0.02)
    win32api.keybd_event(VK_OEM_PERIOD, 0, win32con.KEYEVENTF_KEYUP, 0)


def press_esc():
    win32api.keybd_event(win32con.VK_ESCAPE, 0, 0, 0)
    time.sleep(0.02)
    win32api.keybd_event(win32con.VK_ESCAPE, 0, win32con.KEYEVENTF_KEYUP, 0)


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


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    print("[input_worker] start")

    crawl_pid = None
    last_pid_check = 0.0

    while True:
        cmd = pop_queue()
        if not cmd:
            time.sleep(0.05)
            continue

        # Refresh PID periodically (process can restart)
        now = time.time()
        if (crawl_pid is None) or (now - last_pid_check > 2.0):
            crawl_pid = find_crawl_pid()
            last_pid_check = now

        if not crawl_pid:
            print(f"[input_worker] crawl pid not found for cmd={cmd}")
            continue

        if not focus_crawl_console(crawl_pid):
            print(
                f"[input_worker] failed to focus window for cmd={cmd} pid={crawl_pid}"
            )
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
        elif cmd == "ATTACK":
            # Tab = attack nearest enemy (DCSS 기본)
            win32api.keybd_event(win32con.VK_TAB, 0, 0, 0)
            time.sleep(0.02)
            win32api.keybd_event(win32con.VK_TAB, 0, win32con.KEYEVENTF_KEYUP, 0)
            print("[input_worker] sent: TAB (attack)")
        elif cmd == "MORE":
            win32api.keybd_event(win32con.VK_SPACE, 0, 0, 0)
            time.sleep(0.02)
            win32api.keybd_event(win32con.VK_SPACE, 0, win32con.KEYEVENTF_KEYUP, 0)
            print("[input_worker] sent: SPACE (more)")
        elif cmd.startswith("MOVE "):
            parts = cmd.split()
            if len(parts) == 2 and len(parts[1]) == 1:
                press_key(parts[1])
                print(f"[input_worker] sent: {parts[1]} (move)")
            else:
                print(f"[input_worker] bad MOVE cmd={cmd}")
        else:
            print(f"[input_worker] unknown cmd={cmd}")
