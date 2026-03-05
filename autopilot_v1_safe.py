import time
import requests

from webtiles.observation import fetch_observation
from webtiles.actions import send_keys

BASE_URL = "http://localhost:9090"
USER = "MinZZang"

# 너무 잦은 호출 방지
POLL_SEC = 0.5

# 키 연타 방지
MIN_SEND_INTERVAL_SEC = 1.2

# "진행이 있는지" 체크: turn이 안 오르면 자동탐험 계속 누르지 않음
STUCK_TURN_LIMIT = 3


def main():
    print("[autopilot_v1_safe] start. Ctrl+C to stop.")
    last_sent_at = 0.0
    last_turn = None
    stuck = 0

    while True:
        try:
            # log_n을 줄여서 서버 부담 낮추기 (우선 안정성)
            obs = fetch_observation(BASE_URL, USER, log_n=20, timeout=3.0)
        except requests.exceptions.RequestException as e:
            print("[net] fetch failed -> sleep:", type(e).__name__)
            time.sleep(1.0)
            continue

        turn = obs.turn
        idle = obs.idle_time
        print(f"[OBS] turn={turn} idle={idle} where={obs.where}")

        # turn 정체 감지
        if last_turn is not None and turn == last_turn:
            stuck += 1
        else:
            stuck = 0
        last_turn = turn

        # 진행이 멈춰있으면(예: 몬스터로 autoexplore 취소/막힘 가능성) 자동탐험을 더 누르지 않는다
        if stuck >= STUCK_TURN_LIMIT:
            print(
                "[SAFE] turn not advancing -> STOP sending. (possible danger or blocked)"
            )
            # 안전하게 기다리기만 함
            time.sleep(1.0)
            continue

        now = time.time()
        if now - last_sent_at < MIN_SEND_INTERVAL_SEC:
            time.sleep(POLL_SEC)
            continue

        # ✅ 지금 단계의 안전 정책:
        # - 자동탐험(o)은 “idle이 충분히 크고(>=2), 진행이 있는 동안에만” 아주 천천히
        if idle >= 2:
            act = "o"
        else:
            act = "."  # 너무 직후면 대기

        print("[ACT]", repr(act))
        try:
            res = send_keys(BASE_URL, USER, act, timeout=3.0)
            print("[SENT]", res.ok, res.raw)
            last_sent_at = now
        except requests.exceptions.RequestException as e:
            print("[net] send failed:", type(e).__name__)

        time.sleep(POLL_SEC)


if __name__ == "__main__":
    main()
