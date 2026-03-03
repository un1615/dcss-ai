import time
import requests

BASE_URL = "http://localhost:9090"
USERNAME = "MinZZang"


def get_state():
    r = requests.get(
        f"{BASE_URL}/bot/state", params={"username": USERNAME}, timeout=2.0
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


def send_and_sync(keys: str, max_wait_sec: float = 5.0, poll_sec: float = 0.05):
    s0 = get_state()
    t0 = s0.get("turn")
    a0 = s0.get("last_activity_time")
    idle0 = s0.get("idle_time")

    resp = send_keys(keys)

    start = time.time()
    while True:
        s1 = get_state()
        t1 = s1.get("turn")
        a1 = s1.get("last_activity_time")
        idle1 = s1.get("idle_time")

        ok = (
            (t0 is not None and t1 is not None and t1 != t0)
            or (a1 is not None and a1 != a0)
            or (idle0 is not None and idle1 is not None and idle1 < idle0)
        )
        if ok:
            return {
                "ok": True,
                "sent": keys,
                "before": s0,
                "after": s1,
                "input_resp": resp,
            }

        if time.time() - start > max_wait_sec:
            return {
                "ok": False,
                "sent": keys,
                "before": s0,
                "after": s1,
                "input_resp": resp,
                "reason": "timeout",
            }

        time.sleep(poll_sec)


def clear_ui():
    # ESC → SPACE → ENTER
    for k in ["\x1b", " "]:  # ENTER 제거
        send_and_sync(k, max_wait_sec=1.5)


def safe_step(action_keys: str):
    # 1) UI 정리
    # clear_ui()
    # 2) 행동 1개
    result = send_and_sync(action_keys, max_wait_sec=5.0)
    # 3) 보기 좋게 요약 출력
    b = result["before"]
    a = result["after"]
    print(
        {
            "sent": repr(action_keys),
            "ok": result["ok"],
            "turn": (b.get("turn"), a.get("turn")),
            "idle": (b.get("idle_time"), a.get("idle_time")),
            "act": (b.get("last_activity_time"), a.get("last_activity_time")),
            "where": a.get("where"),
        }
    )
    return result


if __name__ == "__main__":
    # ✅ AI 없이 루프 테스트: 10번만 '대기' 수행
    for i in range(10):
        safe_step(".")  # 너가 말한 한 턴 키
        time.sleep(0.2)
