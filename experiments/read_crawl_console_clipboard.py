import time
import pyperclip
import win32gui

import pydirectinput as pdi  # 이미 쓰고 있지? 없으면 pip install pydirectinput

TARGET_TITLE_KEYWORD = "Dungeon Crawl"  # 창 제목에 포함되는 단어


def focus_crawl_console() -> bool:
    hwnd = win32gui.FindWindow(None, win32gui.GetWindowText(win32gui.GetForegroundWindow()))
    # 위 줄은 현재 포커스 창 핸들 얻는 용도(안전). 실제로는 EnumWindows로 찾는 게 더 확실함.
    found = []

    def enum_cb(h, _):
        title = win32gui.GetWindowText(h)
        if TARGET_TITLE_KEYWORD in title:
            found.append(h)

    win32gui.EnumWindows(enum_cb, None)
    if not found:
        return False

    # 첫 번째 매칭 창 활성화
    win32gui.SetForegroundWindow(found[0])
    return True


def grab_console_text_via_clipboard() -> str:
    # 클립보드 초기화(이전 내용과 구분)
    pyperclip.copy("")

    # 콘솔 전체 선택 -> 복사
    # ConHost(기존 콘솔)에서는 Ctrl+A 후 Enter가 "복사"로 동작하는 설정이 흔함
    # 만약 Enter로 복사가 안 되면 Ctrl+C로 바꾸면 됨.
    pdi.keyDown("ctrl"); pdi.press("a"); pdi.keyUp("ctrl")
    time.sleep(0.05)
    pdi.press("enter")  # 복사(환경 따라 ctrl+c 필요할 수 있음)
    time.sleep(0.1)

    return pyperclip.paste()


if __name__ == "__main__":
    print("5초 후 crawl-console 창으로 포커스 이동 후 텍스트를 복사합니다...")
    time.sleep(5)

    ok = focus_crawl_console()
    if not ok:
        print("crawl-console 창을 찾지 못했습니다. 실행 중인지/창 제목에 'Dungeon Crawl'이 있는지 확인해줘.")
        raise SystemExit(1)

    time.sleep(0.2)
    text = grab_console_text_via_clipboard()

    if not text.strip():
        print("클립보드에 텍스트가 비어있습니다.")
        print("해결: Enter 대신 Ctrl+C로 복사하도록 코드를 바꿔야 할 수 있어요.")
    else:
        print("=== 읽기 성공 (앞 800자) ===")
        print(text[:800])