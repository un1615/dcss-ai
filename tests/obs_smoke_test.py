import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from webtiles.observation import fetch_observation
from webtiles.observation import observation_to_ai_dict
from controller.action_to_queue import action_json_to_queue

if __name__ == "__main__":
    obs = fetch_observation("http://localhost:9090", "MinZZang", log_n=20)

    # print("OK:", obs.user, obs.game_id, obs.running)
    # print("WHERE:", obs.where)
    # print("TURN:", obs.turn, "IDLE:", obs.idle_time)

    # print("LOG (last 5):")
    # for line in obs.recent_msgs[-5:]:
    #     print(" -", line)

    print("\nSCREEN_TEXT:")
    if obs.screen_text:
        lines = obs.screen_text.splitlines()
        print(f"LINE_COUNT: {len(lines)}")

        for i, line in enumerate(lines):
            print(f"{i:02d}: {repr(line)}")
    else:
        print("(none)")

    print("ASCII_MAP:")
    print(obs.ascii_map if obs.ascii_map else "(none)")

    print("PLAYER_POS:", obs.player_pos)
    print("VISIBLE_MONSTERS:", obs.visible_monsters)


from core.state_parser import split_screen_regions

print("\n=== SPLIT CHECK ===")
regions = split_screen_regions(obs.screen_text)

print("\n[MAP]")
for line in regions["map_lines"]:
    print(line)

print("\n[STATUS]")
for line in regions["status_lines"]:
    print(line)

print("\n[MESSAGES]")
for line in regions["message_lines"]:
    print(line)

print("HP_INFO:", obs.hp_info)


from webtiles.observation import observation_to_ai_dict
from brain.brain_openai import decide_next_action

ai_dict = observation_to_ai_dict(obs)

print("\nAI_DICT:")
print(ai_dict)

ai_action = decide_next_action(ai_dict)

print("\nAI_ACTION:")
print(ai_action)

from webtiles.webtiles_input import send_keys

direction = ai_action["dir"]

print("SEND KEYS:", direction)

result = send_keys(direction)

print("SEND RESULT:", result)
