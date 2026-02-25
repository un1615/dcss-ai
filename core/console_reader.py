# core/console_reader.py
from __future__ import annotations

import os
import time
import traceback
from dataclasses import dataclass

import psutil
import win32console
import win32api


@dataclass
class ConsoleDumpResult:
    ok: bool
    text: str | None
    error: str | None


def _log(path: str, msg: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(msg.rstrip() + "\n")


def _find_crawl_console_pid() -> int | None:
    """
    crawl-console 프로세스를 찾는다.
    exe 이름이 환경마다 달라서 'crawl'과 'console' 키워드로 최대한 넓게 잡는다.
    """
    candidates = []
    for p in psutil.process_iter(["pid", "name", "exe", "cmdline"]):
        try:
            name = (p.info.get("name") or "").lower()
            exe = (p.info.get("exe") or "").lower()
            cmd = " ".join(p.info.get("cmdline") or []).lower()

            blob = " ".join([name, exe, cmd])
            if "crawl" in blob and ("console" in blob or "crawl-console" in blob):
                candidates.append(p.info["pid"])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    # 여러 개면 가장 마지막에 뜬 걸 고르는 게 낫지만,
    # 여기선 첫 번째로 충분한 경우가 대부분이라 그냥 첫 번째 사용
    return candidates[0] if candidates else None


def attach_to_crawl_console(status_log_path: str) -> bool:
    pid = _find_crawl_console_pid()
    if not pid:
        _log(status_log_path, "=== reader start ===")
        _log(status_log_path, "crawl-console을 켠 상태에서 실행해야 함")
        _log(status_log_path, "error: crawl-console PID를 찾지 못함")
        return False

    try:
        # 현재 콘솔(보통 VSCode 터미널 콘솔)에서 분리
        try:
            win32console.FreeConsole()
        except Exception:
            pass

        # crawl-console 콘솔에 붙기
        win32console.AttachConsole(pid)
        return True

    except Exception as e:
        _log(status_log_path, "=== reader start ===")
        _log(status_log_path, "crawl-console을 켠 상태에서 실행해야 함")
        _log(status_log_path, f"error: AttachConsole 실패: {repr(e)}")
        _log(status_log_path, traceback.format_exc())
        return False


def read_crawl_console_to_text(
    width: int = 120,
    height: int = 40,
    status_log_path: str = "run_logs/reader_status.log",
) -> ConsoleDumpResult:
    """
    AttachConsole(pid) 후, GetStdHandle로 콘솔 버퍼를 읽는다.
    """
    try:
        # STD_OUTPUT_HANDLE = -11
        h = win32console.GetStdHandle(win32console.STD_OUTPUT_HANDLE)
        if not h or int(h) == 0:
            raise RuntimeError("GetStdHandle(STD_OUTPUT_HANDLE) 실패 (핸들 0)")

        # 스크린 버퍼 래핑
        sb = win32console.PyConsoleScreenBufferType(h)

        origin = win32console.PyCOORDType(0, 0)
        length = int(width) * int(height)

        text = sb.ReadConsoleOutputCharacter(length, origin)
        return ConsoleDumpResult(ok=True, text=text, error=None)

    except Exception as e:
        _log(status_log_path, "=== reader start ===")
        _log(status_log_path, "crawl-console을 켠 상태에서 실행해야 함")
        _log(status_log_path, f"error: {repr(e)}")
        _log(status_log_path, traceback.format_exc())
        return ConsoleDumpResult(ok=False, text=None, error=repr(e))