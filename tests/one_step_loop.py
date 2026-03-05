import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from webtiles.observation import fetch_observation
from webtiles.actions import send_keys
from policy.simple_policy import choose_action

BASE_URL = "http://localhost:9090"
USER = "MinZZang"

if __name__ == "__main__":
    obs = fetch_observation(BASE_URL, USER, log_n=50)
    act = choose_action(obs)

    print("WHERE:", obs.where)
    print("TURN:", obs.turn, "IDLE:", obs.idle_time)
    print("CHOSEN ACTION:", repr(act))

    res = send_keys(BASE_URL, USER, act)
    print("SENT:", res.ok, res.raw)
