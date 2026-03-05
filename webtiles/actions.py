# webtiles/actions.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict
import requests


@dataclass
class SendResult:
    ok: bool
    sent: str
    raw: Dict[str, Any]


def send_keys(
    base_url: str, username: str, keys: str, timeout: float = 5.0
) -> SendResult:
    """
    DCSS WebTiles bot input endpoint로 키 입력을 보낸다.
    """
    url = f"{base_url}/bot/input"
    payload = {"user": username, "keys": keys}
    r = requests.post(url, json=payload, timeout=timeout)
    r.raise_for_status()
    j = r.json()
    return SendResult(ok=bool(j.get("ok", False)), sent=keys, raw=j)
