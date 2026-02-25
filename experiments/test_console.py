import time
import win32gui
import win32con
import win32console


def find_crawl_console():
    def enum_windows_callback(hwnd, results):
        title = win32gui.GetWindowText(hwnd)
        if "Dungeon Crawl" in title:
            results.append(hwnd)
    windows = []
    win32gui.EnumWindows(enum_windows_callback, windows)
    return windows


def read_console_text(hwnd):
    try:
        handle = win32console.GetStdHandle(win32console.STD_OUTPUT_HANDLE)
        csbi = handle.GetConsoleScreenBufferInfo()
        left, top, right, bottom = csbi["Window"]
        width = right - left + 1
        height = bottom - top + 1

        data = handle.ReadConsoleOutputCharacter(
            (left, top),
            width * height
        )
        return data
    except Exception as e:
        return None


print("crawl-console 창을 활성화한 상태로 두세요...")
time.sleep(5)

while True:
    windows = find_crawl_console()
    if windows:
        text = read_console_text(windows[0])
        if text:
            print("=== 콘솔 텍스트 일부 출력 ===")
            print(text[:800])
            break
    time.sleep(1)