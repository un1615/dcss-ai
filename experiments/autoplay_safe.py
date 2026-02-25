import time
import hashlib
import os
from datetime import datetime

import pyautogui                 # 스크린샷/픽셀검사용
import pydirectinput as pdi      # 키입력용(DCSS에 잘 먹음)
import pygetwindow as gw         # 창 찾기(activate는 안 씀)
from openai import OpenAI        # LLM 호출

# ===== 기본 설정 =====
STUCK_SECONDS = 4
LOOP_INTERVAL = 1.0
LOG_DIR = "run_logs"

# ===== LLM 비용 통제 설정 =====
LLM_ENABLED = True
LLM_MODEL = "gpt-4o-mini"
LLM_COOLDOWN_SEC = 30
LLM_MAX_CALLS_PER_RUN = 30

os.makedirs(LOG_DIR, exist_ok=True)


def find_dcss_window():
    for w in gw.getAllWindows():
        t = (w.title or "").lower()
        if "crawl" in t or "dungeon" in t or "stone soup" in t or "dcss" in t:
            return w
    return None


def focus_dcss(win):
    # activate()는 윈도우에서 가끔 꼬여서 클릭만 사용
    cx = win.left + win.width // 2
    cy = win.top + win.height // 2
    pdi.click(cx, cy)
    time.sleep(0.15)


def screen_hash():
    img = pyautogui.screenshot()
    return hashlib.md5(img.tobytes()).hexdigest()


def log_event(tag: str):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(LOG_DIR, f"{ts}_{tag}.png")
    pyautogui.screenshot(path)
    print(f"[LOG] saved: {path}")


def enemy_likely():
    """
    적/위험 경고 감지: 왼쪽 아래 로그 영역에 빨간 텍스트 픽셀이 많으면 True
    """
    img = pyautogui.screenshot()
    w, h = img.size
    px = img.load()

    x0 = 0
    y0 = int(h * 0.72)
    x1 = int(w * 0.35)
    y1 = h - 1

    step = 6
    red = 0
    total = 0

    for y in range(y0, y1, step):
        for x in range(x0, x1, step):
            r, g, b = px[x, y][:3]
            total += 1
            if r > 120 and r > g + 25 and r > b + 25:
                red += 1

    ratio = red / max(total, 1)
    return ratio > 0.006


def hp_likely_low():
    """
    HP 위험(아주 대충): 왼쪽 위 영역에서 초록(HP바) 픽셀이 너무 적으면 True
    """
    img = pyautogui.screenshot()
    w, h = img.size
    px = img.load()

    x0 = 0
    y0 = 0
    x1 = int(w * 0.35)
    y1 = int(h * 0.20)

    step = 6
    green = 0
    total = 0

    for y in range(y0, y1, step):
        for x in range(x0, x1, step):
            r, g, b = px[x, y][:3]
            total += 1
            if g > 120 and g > r + 20 and g > b + 20:
                green += 1

    ratio = green / max(total, 1)
    return ratio < 0.002


def llm_decide_low_hp(enemy_now: bool):
    """
    HP 위험할 때만 LLM 호출. 출력은 rest/fight/explore 중 하나.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key or not LLM_ENABLED:
        return "rest"

    client = OpenAI(api_key=api_key)

    system = (
        "너는 DCSS 자동플레이 AI의 생존 판단 뇌다.\n"
        "반드시 셋 중 하나만 출력: rest / fight / explore\n"
        "- rest: 쉬어서 회복(Shift+5)\n"
        "- fight: 위험 낮으면 전투(tab)\n"
        "- explore: 위험 낮고 애매하면 탐험(o)\n"
        "생존 우선."
    )
    user = (
        f"상황: HP가 낮아 보임.\n"
        f"적 경고(enemy_likely): {enemy_now}\n"
        "셋 중 하나만 답해: rest / fight / explore"
    )

    resp = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )

    out = (resp.choices[0].message.content or "").strip().lower()
    if "rest" in out:
        return "rest"
    if "fight" in out:
        return "fight"
    return "explore"


# ===== 메인 =====
print("DCSS 창을 찾는 중...")
win = find_dcss_window()
if not win:
    print("DCSS 창을 못 찾았어. DCSS를 켜고 다시 실행해줘.")
    raise SystemExit

print("5초 뒤 시작! 그 전에 DCSS 화면(던전)으로 가둬.")
time.sleep(5)

focus_dcss(win)

print("시작!")
print("- 적 경고 뜨면 tab 전투")
print("- 평소엔 o 탐험")
print("- HP 낮아 보이면(이벤트)만 LLM 호출")
print("중단: Ctrl+C")

prev = screen_hash()
same_count = 0
recovery_cooldown = 0

llm_last_call = 0.0
llm_calls = 0

while True:
    if recovery_cooldown > 0:
        time.sleep(1)
        recovery_cooldown -= 1
        prev = screen_hash()
        same_count = 0
        continue

    # ===== 행동 결정 =====
    if hp_likely_low():
        now = time.time()
        can_call = (llm_calls < LLM_MAX_CALLS_PER_RUN) and (now - llm_last_call >= LLM_COOLDOWN_SEC)

        if can_call:
            print("HP 위험 감지! LLM 판단 호출")
            log_event("lowhp")
            focus_dcss(win)

            decision = llm_decide_low_hp(enemy_likely())
            llm_last_call = now
            llm_calls += 1
            print(f"LLM 결정: {decision} (calls={llm_calls})")
        else:
            decision = "rest"

        if decision == "rest":
             # 메뉴/정보창 떠있을 수 있으니 ESC 한 번 정리
            pdi.press("esc")
            time.sleep(0.05)

            # '기다리기(휴식)'을 안전하게 여러 번
            pdi.press("5", presses=8, interval=0.05)          
        elif decision == "fight":
            pdi.press("enter")
            time.sleep(0.05)
            pdi.press("tab")
        else:
            pdi.press("o")

    else:
        if enemy_likely():
            pdi.press("enter")
            time.sleep(0.05)
            pdi.press("tab")
        else:
            pdi.press("o")

    time.sleep(LOOP_INTERVAL)

    # ===== 멈춤 감지/복구 =====
    cur = screen_hash()
    if cur == prev:
        same_count += 1
    else:
        same_count = 0
        prev = cur

    if same_count >= STUCK_SECONDS:
        print("멈춤 감지! 복구 시도")
        log_event("stuck")
        focus_dcss(win)

        pdi.press("esc")
        time.sleep(0.2)
        pdi.press("esc")
        time.sleep(0.2)
        pdi.press("enter")
        time.sleep(0.2)

        recovery_cooldown = 3
        prev = screen_hash()
        same_count = 0