import time
import requests

BASE_URL = "http://localhost:9090"
USERNAME = "MinZZang"


def get_state():
    r = requests.get(
        f"{BASE_URL}/bot/state",
        params={"username": USERNAME},
        timeout=2.0,
    )
    r.raise_for_status()
    return r.json()


def send_keys(keys: str):
    r = requests.post(
        f"{BASE_URL}/bot/input",
        json={"keys": keys, "username": USERNAME},
        timeout=2.0,
    )
    r.raise_for_status()
    return r.json()


def send_and_wait_turn(keys: str, max_wait_sec: float = 5.0, poll_sec: float = 0.05):
    s0 = get_state()
    t0 = s0.get("turn")
    a0 = s0.get("last_activity_time")
    idle0 = s0.get("idle_time")

    print("[before] turn=", t0, "idle=", idle0, "act=", a0, "where=", s0.get("where"))

    resp = send_keys(keys)
    print("[input_resp]", resp)

    start = time.time()
    while True:
        s1 = get_state()
        t1 = s1.get("turn")
        a1 = s1.get("last_activity_time")
        idle1 = s1.get("idle_time")

        # ✅ 성공 조건: (1) 턴 변화 OR (2) activity 변화 OR (3) idle_time 리셋
        if (
            (t0 is not None and t1 is not None and t1 != t0)
            or (a1 is not None and a1 != a0)
            or (idle0 is not None and idle1 is not None and idle1 < idle0)
        ):
            print(
                "[after ] turn=",
                t1,
                "idle=",
                idle1,
                "act=",
                a1,
                "where=",
                s1.get("where"),
            )
            return True

        if time.time() - start > max_wait_sec:
            print(
                "[timeout] turn=",
                t1,
                "idle=",
                idle1,
                "act=",
                a1,
                "where=",
                s1.get("where"),
            )
            return False

        time.sleep(poll_sec)


if __name__ == "__main__":
    # ✅ '.' 대신 's'로 대기(턴 진행) 테스트
    ok = send_and_wait_turn("s", max_wait_sec=5.0)
    print("OK" if ok else "FAIL")
