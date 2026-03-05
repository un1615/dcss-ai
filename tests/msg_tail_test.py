import sys, os

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from webtiles.observation import fetch_observation

BASE_URL = "http://localhost:9090"
USER = "MinZZang"

if __name__ == "__main__":
    obs = fetch_observation(BASE_URL, USER, log_n=10)
    print("recent_msgs:")
    for m in obs.recent_msgs[-10:]:
        print(" -", m)
