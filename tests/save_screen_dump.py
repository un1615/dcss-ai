import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from webtiles.observation import fetch_observation

if __name__ == "__main__":
    obs = fetch_observation("http://localhost:9090", "MinZZang", log_n=20)

    out_path = "screen_dump.txt"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(obs.screen_text or "")

    print("saved:", out_path)
