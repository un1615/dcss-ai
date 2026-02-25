# reader_worker.py
# Reads crawl-console Win32 CONOUT$ buffer and writes run_logs/console_dump.txt every 1s.
# This process may not respond to Ctrl+C reliably (AttachConsole), and that's OK.
# Controller will stop it with taskkill.

import os
import time
import psutil
import win32con
import win32console
import win32file

OUT_DIR = r"C:\Users\Oh\Desktop\ai_dcss\run_logs"
DUMP_PATH = os.path.join(OUT_DIR, "console_dump.txt")
STATUS_PATH = os.path.join(OUT_DIR, "reader_status.log")


def log(msg: str):
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(STATUS_PATH, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


def find_crawl_pid():
    for proc in psutil.process_iter(["pid", "name"]):
        name = (proc.info["name"] or "").lower()
        if "crawl-console" in name:
            return proc.info["pid"]
    return None


def dump_once(width=120, height=45):
    pid = find_crawl_pid()
    if not pid:
        raise RuntimeError("crawl-console.exe를 찾지 못함")

    try:
        win32console.FreeConsole()
    except Exception:
        pass

    win32console.AttachConsole(pid)

    h = win32file.CreateFile(
        "CONOUT$",
        win32con.GENERIC_READ | win32con.GENERIC_WRITE,
        win32con.FILE_SHARE_READ | win32con.FILE_SHARE_WRITE,
        None,
        win32con.OPEN_EXISTING,
        0,
        None,
    )

    sb = win32console.PyConsoleScreenBufferType(h)
    coord = win32console.PyCOORDType(0, 0)
    text = sb.ReadConsoleOutputCharacter(width * height, coord)

    try:
        win32console.FreeConsole()
    except Exception:
        pass

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(DUMP_PATH, "w", encoding="utf-8", errors="replace") as f:
        f.write(text)

    return text


if __name__ == "__main__":
    log("=== reader_worker start ===")
    # Optional: lightweight heartbeat every 10s (uncomment if you want)
    # last_beat = 0.0

    while True:
        try:
            dump_once()
            # now = time.time()
            # if now - last_beat >= 10.0:
            #     log("heartbeat: dumping ok")
            #     last_beat = now
            time.sleep(1.0)
        except Exception as e:
            log(f"worker ERROR: {repr(e)}")
            time.sleep(1.0)
