# webtiles_input.py
import requests

BASE_URL = "http://localhost:9090"


def send_keys(keys: str, base_url: str = BASE_URL, timeout: float = 2.0) -> dict:
    r = requests.post(f"{base_url}/bot/input", json={"keys": keys}, timeout=timeout)
    r.raise_for_status()
    return r.json()
