import time
import requests

from webtiles.observation import fetch_observation
from webtiles.actions import send_keys
from policy.simple_policy import choose_action, has_threat, needs_more
from brain.brain_openai import OpenAIBrain
from brain.brain_rule_fallback import RuleFallbackBrain

BASE_URL = "http://localhost:9090"
USER = "MinZZang"

POLL_SEC = 0.25
SEND_INTERVAL_SEC = 0.35
EXPLORE_INTERVAL_SEC = 1.0


def main():
    print("[autopilot_v2_fight] start. Ctrl+C to stop.")

    brain = OpenAIBrain(
        model="gpt-4.1-mini"
    )  # 네 brain_openai.py 안에서 timeout 걸어주는게 베스트(아래 설명)
    fallback = RuleFallbackBrain()

    last_sent = 0.0
    tab_streak = 0

    last_turn = None
    stuck_count = 0

    recovery_esc_left = 0

    # ✅ 최근에 계단을 봤는지 기억(랜덤이동 금지 + 탈출용)
    saw_stairs_down_ttl = 0  # "stone staircase leading down"을 보면 몇 루프동안 유효
    saw_stairs_up_ttl = 0

    while True:
        try:
            obs = fetch_observation(BASE_URL, USER, timeout=3.0)
        except requests.exceptions.RequestException:
            print("[net] fetch failed")
            time.sleep(1.0)
            continue

        # ✅ 입력 가능 모드 아니면 보내지 않기
        if obs.input_mode is not None and obs.input_mode != 1:
            print(f"[SAFE] input_mode={obs.input_mode} -> skip sending")
            time.sleep(POLL_SEC)
            continue

        # --- turn 정체 감지 ---
        if last_turn is None:
            last_turn = obs.turn
            stuck_count = 0
        else:
            if obs.turn == last_turn:
                stuck_count += 1
            else:
                stuck_count = 0
                last_turn = obs.turn

        recent = obs.recent_msgs[-8:] if obs.recent_msgs else []
        recent_low = [t.lower() for t in recent]

        # --- "Unknown command" 탈출 ---
        has_unknown = any("unknown command" in t for t in recent_low)
        if has_unknown and recovery_esc_left == 0:
            recovery_esc_left = 3

        # --- 계단 메시지 감지(탈출용 메모리) ---
        if any("stone staircase leading down" in t for t in recent_low):
            saw_stairs_down_ttl = 40
        if any("stone staircase leading up" in t for t in recent_low):
            saw_stairs_up_ttl = 40
        if saw_stairs_down_ttl > 0:
            saw_stairs_down_ttl -= 1
        if saw_stairs_up_ttl > 0:
            saw_stairs_up_ttl -= 1

        # --- 저체력 탭 거부 감지(핵심) ---
        tab_refused_lowhp = any(
            "too injured to fight recklessly" in t for t in recent_low
        )

        # --- 행동 결정 ---
        if needs_more(obs):
            act = " "
            mode = "MORE"

        elif recovery_esc_left > 0:
            act = "\x1b"
            mode = f"RECOVERY_ESC({recovery_esc_left})"
            recovery_esc_left -= 1

        # ✅ 탭 거부(저체력)면: 랜덤이동 금지 / 탐험(o) 금지 / 계단 있으면 계단으로 탈출
        elif tab_refused_lowhp:
            # 1) 계단 있으면 우선 탈출 (down을 봤으면 '>'로 내려가서 시야 끊기)
            if saw_stairs_down_ttl > 0:
                act = ">"
                mode = "PANIC_STAIRS_DOWN"
            elif saw_stairs_up_ttl > 0:
                act = "<"
                mode = "PANIC_STAIRS_UP"
            else:
                # 2) 계단이 확실치 않으면 TAB 금지 + ESC 한 번(오토/선택 취소) 후 한 턴 대기('.')
                #    (랜덤 이동보다 “멈춰서 상황 읽기”가 더 안전)
                act = "\x1b"
                mode = "PANIC_ESC"

        else:
            # ✅ 여기서부터 AI 판단 (단, 느리면 fallback)
            try:
                t0 = time.time()
                decision = brain.decide(obs)  # brain_openai.py에서 timeout 권장
                if time.time() - t0 > 2.0:
                    raise TimeoutError("brain took too long")
                act = decision.action
                mode = f"AI({decision.reason})"
            except Exception:
                decision = fallback.decide(obs)
                act = decision.action
                mode = f"FALLBACK({decision.reason})"

        # tab streak
        if act == "\t":
            tab_streak += 1
        else:
            tab_streak = 0

        last_msgs = obs.recent_msgs[-2:] if obs.recent_msgs else []
        print(
            f"[OBS] turn={obs.turn} idle={obs.idle_time} where={obs.where} mode={mode} msgs={last_msgs}"
        )

        # 입력 간격
        if mode.startswith("RECOVERY"):
            interval = 0.5
        elif mode == "MORE":
            interval = 0.35
        elif mode.startswith("PANIC"):
            interval = 0.25
        else:
            interval = SEND_INTERVAL_SEC if act == "\t" else EXPLORE_INTERVAL_SEC

        now = time.time()
        if now - last_sent < interval:
            time.sleep(POLL_SEC)
            continue

        if tab_streak >= 30:
            print("[SAFE] tab streak too long -> pause 1s")
            time.sleep(1.0)
            tab_streak = 0

        try:
            res = send_keys(BASE_URL, USER, act, timeout=3.0)
            if act == "\t":
                sent_label = "TAB"
            elif act == " ":
                sent_label = "SPACE"
            elif act == "\x1b":
                sent_label = "ESC"
            else:
                sent_label = repr(act)
            print("[SENT]", sent_label, res.ok)
            last_sent = now
        except requests.exceptions.RequestException:
            print("[net] send failed")

        time.sleep(POLL_SEC)


if __name__ == "__main__":
    main()
