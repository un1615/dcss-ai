import time
import requests

from webtiles.observation import fetch_observation
from webtiles.actions import send_keys
from policy.simple_policy import choose_action

BASE_URL = "http://localhost:9090"
USER = "MinZZang"

POLL_SEC = 0.3
MIN_SEND_INTERVAL_SEC = 0.35


def main():
    print("[autopilot_v2] start. Ctrl+C to stop.")
    last_sent = 0.0

    while True:
        try:
            obs = fetch_observation(BASE_URL, USER, log_n=10, timeout=3.0)
        except requests.exceptions.RequestException as e:
            print("[net] fetch failed:", type(e).__name__)
            time.sleep(1.0)
            continue

        act = choose_action(obs)

        # 보기 좋게 상태 출력
        mode = "FIGHT" if act == "\t" else "EXPLORE"
        last_msgs = obs.recent_msgs[-2:] if obs.recent_msgs else []
        print(
            f"[OBS] turn={obs.turn} idle={obs.idle_time} where={obs.where} mode={mode} msgs={last_msgs}"
        )

        now = time.time()
        if now - last_sent >= MIN_SEND_INTERVAL_SEC:
            try:
                res = send_keys(BASE_URL, USER, act, timeout=3.0)
                print("[SENT]", repr(act), res.ok)
                last_sent = now
            except requests.exceptions.RequestException as e:
                print("[net] send failed:", type(e).__name__)

        time.sleep(POLL_SEC)


if __name__ == "__main__":
    main()
