# webtiles_reader.py
import requests

BASE_URL = "http://localhost:9090"


def get_state(base_url: str = BASE_URL, timeout: float = 2.0) -> dict:
    r = requests.get(f"{base_url}/bot/state", timeout=timeout)
    r.raise_for_status()
    return r.json()
