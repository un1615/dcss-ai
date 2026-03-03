import requests


class WebTilesClient:
    def __init__(self, base_url: str, username: str, timeout: float = 2.0):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.timeout = timeout

    def get_state(self, debug: bool = False) -> dict:
        params = {"username": self.username}
        if debug:
            params["debug"] = "1"
        r = requests.get(
            f"{self.base_url}/bot/state", params=params, timeout=self.timeout
        )
        r.raise_for_status()
        return r.json()

    def get_log(self, n: int = 40) -> dict:
        params = {"username": self.username, "n": str(n)}
        r = requests.get(
            f"{self.base_url}/bot/log", params=params, timeout=self.timeout
        )
        r.raise_for_status()
        return r.json()

    def send_keys(self, keys: str) -> dict:
        payload = {"username": self.username, "keys": keys}
        r = requests.post(
            f"{self.base_url}/bot/input", json=payload, timeout=self.timeout
        )
        r.raise_for_status()
        return r.json()
