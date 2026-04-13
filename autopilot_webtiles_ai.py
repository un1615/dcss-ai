import time

from webtiles.observation import fetch_observation, observation_to_ai_dict
from brain.brain_openai import decide_next_action
from webtiles.webtiles_input import send_keys

BASE_URL = "http://localhost:9090"
USERNAME = "MinZZang"
STEP_DELAY = 0.4
MAX_STEPS = 20


def run_autopilot():
    print("[autopilot] start")

    for step in range(MAX_STEPS):
        try:
            obs = fetch_observation(BASE_URL, USERNAME, log_n=20)
            # 상태 유지용
            if not hasattr(run_autopilot, "last_player_pos"):
                run_autopilot.last_player_pos = None
                run_autopilot.last_hp_info = None

            if obs.player_pos:
                run_autopilot.last_player_pos = obs.player_pos
            else:
                obs.player_pos = run_autopilot.last_player_pos

            if obs.hp_info:
                run_autopilot.last_hp_info = obs.hp_info
            else:
                obs.hp_info = run_autopilot.last_hp_info
            ai_dict = observation_to_ai_dict(obs)
            ai_action = decide_next_action(ai_dict)

            print(f"\n[step {step + 1}]")
            print("where:", obs.where)
            print("player_pos:", obs.player_pos)
            print("hp_info:", obs.hp_info)
            print("visible_monsters:", obs.visible_monsters)
            # 몬스터가 없으면 AI 호출 없이 자동탐색
            if not obs.visible_monsters:
                print(
                    "auto_action:",
                    {"type": "autoexplore", "reason": "no visible monsters"},
                )
                result = send_keys("o", base_url=BASE_URL)
                print("send_result:", result)
                time.sleep(STEP_DELAY)
                continue

            # 몬스터가 있으면 AI 판단
            ai_dict = observation_to_ai_dict(obs)
            ai_action = decide_next_action(ai_dict)

            print("ai_action:", ai_action)

            if ai_action.get("type") != "move":
                print("[autopilot] skip: non-move action")
                time.sleep(STEP_DELAY)
                continue

            direction = ai_action.get("dir")
            if not direction:
                print("[autopilot] skip: no dir")
                time.sleep(STEP_DELAY)
                continue

            result = send_keys(direction, base_url=BASE_URL)
            print("send_result:", result)
        except KeyboardInterrupt:
            print("\n[autopilot] stopped by user")
            break
        except Exception as e:
            print(f"[autopilot] error: {e}")

        time.sleep(STEP_DELAY)

    print("[autopilot] end")


if __name__ == "__main__":
    run_autopilot()
