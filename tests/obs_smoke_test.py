import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from webtiles.observation import fetch_observation

if __name__ == "__main__":
    obs = fetch_observation("http://localhost:9090", "MinZZang", log_n=20)
    print("OK:", obs.user, obs.game_id, obs.running)
    print("WHERE:", obs.where)
    print("TURN:", obs.turn, "IDLE:", obs.idle_time)
    print("LOG (last 5):")
    for line in obs.recent_log_lines[-5:]:
        print(" -", line)
