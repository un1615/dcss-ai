import time
import pydirectinput as pdi
import pygetwindow as gw

print("5초 후 DCSS 창을 찾아 활성화하고 (DirectInput)으로 ESC/Q를 보냅니다.")
time.sleep(5)

# DCSS 창 찾기
windows = gw.getAllWindows()
target = None
for w in windows:
    t = (w.title or "").lower()
    if "crawl" in t or "dungeon" in t or "stone soup" in t or "dcss" in t:
        target = w
        break

if not target:
    print("DCSS 창을 못 찾았어. 열린 창 제목들:")
    for w in windows:
        if w.title:
            print("-", w.title)
    raise SystemExit

print("찾은 창:", target.title)

# 창 활성화
target.activate()
time.sleep(0.3)

# 포커스 강제 클릭 (pydirectinput 사용)
cx = target.left + target.width // 2
cy = target.top + target.height // 2
pdi.click(cx, cy)
time.sleep(0.3)

print("ESC 3번 전송")
pdi.press('esc')
time.sleep(0.2)
pdi.press('esc')
time.sleep(0.2)
pdi.press('esc')
time.sleep(0.2)

print("혹시 ESC가 안 먹는 경우 대비해서 Q도 전송")
pdi.press('q')

print("끝! 인벤토리(i)가 닫혔으면 성공.")