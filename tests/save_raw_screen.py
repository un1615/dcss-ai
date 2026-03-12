import sys
import os
import json
import requests

BASE_URL = "http://localhost:9090"
USER = "MinZZang"

if __name__ == "__main__":
    url = f"{BASE_URL}/bot/state?username={USER}&debug=1"
    j = requests.get(url, timeout=5).json()

    with open("screen_text.txt", "w", encoding="utf-8") as f:
        f.write(j.get("screen_text", ""))

    with open("output_buffer_tail.txt", "w", encoding="utf-8") as f:
        f.write(j.get("debug_output_buffer_tail", ""))

    with open("full_state_debug.json", "w", encoding="utf-8") as f:
        json.dump(j, f, ensure_ascii=False, indent=2)

    print("saved: screen_text.txt")
    print("saved: output_buffer_tail.txt")
    print("saved: full_state_debug.json")
