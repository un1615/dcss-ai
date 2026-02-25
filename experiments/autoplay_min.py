import time
import pyautogui

print("5초 뒤 시작! 그 전에 DCSS 창을 클릭해서 포커스 주세요.")
time.sleep(5)

print("시작! 1초마다 o(자동탐험)를 누릅니다. 멈추려면 Ctrl+C")

while True:
    pyautogui.press('o')   # DCSS 자동탐험(기본키)
    time.sleep(1)