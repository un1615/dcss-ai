import sys

sys.path.append("..")

import time
from webtiles.actions import send_keys

BASE_URL = "http://localhost:9090"
USER = "MinZZang"

tests = [
    ".",
    "o",
    "5",
    " ",
    "\t",
    "\x1b",
]

for k in tests:
    try:
        r = send_keys(BASE_URL, USER, k, timeout=3.0)
        print("sent", repr(k), "->", r.ok)
    except Exception as e:
        print("error", repr(k), type(e).__name__)

    time.sleep(0.5)
