import sys, os, json

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import requests

BASE_URL = "http://localhost:9090"
USER = "MinZZang"

if __name__ == "__main__":
    url = f"{BASE_URL}/bot/state?username={USER}"
    j = requests.get(url, timeout=5).json()

    print("TOP-LEVEL KEYS:", list(j.keys()))
    print("\nFULL JSON (depth):")
    print(json.dumps(j, ensure_ascii=False, indent=2))
