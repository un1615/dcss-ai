# action_to_queue.py
import json
from typing import Any, Dict, List, Tuple

VALID_DIRS = set(list("hjkl yubn".replace(" ", "")))


def _write_queue(queue_path: str, lines: List[str]) -> None:
    with open(queue_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).strip() + ("\n" if lines else ""))


def action_json_to_queue(action_json: str, queue_path: str) -> Dict[str, Any]:
    """
    Accepts JSON string like:
      {"type":"attack"}
      {"type":"move","dir":"h"}
      {"type":"wait"}
      {"type":"autoexplore"}
      {"type":"more"}
      {"type":"esc"}
      {"type":"confirm","key":"y"}  or {"type":"confirm","key":"n"}
      {"type":"levelup","key":"s"}  (s/i/d)
      {"type":"key","key":"q"}      (single key)
      {"type":"keys","keys":["q","a","."]}  (sequence)
    Writes queue.txt lines understood by input_worker.py:
      ATTACK / MOVE h / WAIT / AUTOEXPLORE / MORE / ESC / CONFIRM_Y / KEY x
    """
    try:
        a = json.loads(action_json) if isinstance(action_json, str) else action_json
    except Exception as e:
        return {"ok": False, "error": f"bad_json:{e}", "queued": []}

    if not isinstance(a, dict):
        return {"ok": False, "error": "action_not_dict", "queued": []}

    t = (a.get("type") or "").strip().lower()
    queued: List[str] = []

    def push(cmd: str):
        queued.append(cmd)

    if t == "attack":
        push("ATTACK")

    elif t == "move":
        d = (a.get("dir") or "").strip().lower()
        if d in VALID_DIRS:
            push(f"MOVE {d}")
        else:
            return {"ok": False, "error": f"bad_dir:{d}", "queued": []}

    elif t == "wait":
        push("WAIT")

    elif t == "autoexplore":
        push("AUTOEXPLORE")

    elif t == "more":
        push("MORE")

    elif t == "esc":
        push("ESC")

    elif t == "confirm":
        k = (a.get("key") or "").strip().lower()
        if k == "y":
            push("CONFIRM_Y")
        elif k == "n":
            push("KEY n")
        else:
            return {"ok": False, "error": f"bad_confirm:{k}", "queued": []}

    elif t == "levelup":
        k = (a.get("key") or "").strip().lower()
        if k in ("s", "i", "d"):
            push(f"KEY {k}")
        else:
            return {"ok": False, "error": f"bad_levelup:{k}", "queued": []}

    elif t == "key":
        k = (a.get("key") or "").strip()
        if len(k) == 1:
            push(f"KEY {k}")
        else:
            return {"ok": False, "error": f"bad_key:{k}", "queued": []}

    elif t == "keys":
        ks = a.get("keys")
        if not isinstance(ks, list) or not ks:
            return {"ok": False, "error": "bad_keys_list", "queued": []}
        for k in ks:
            if not isinstance(k, str) or len(k) != 1:
                return {"ok": False, "error": f"bad_key_in_keys:{k}", "queued": []}
            # special convenience: "." -> WAIT is fine, but KEY "." also works if your input_worker supports it.
            if k == ".":
                push("WAIT")
            elif k == " ":
                push("MORE")
            else:
                push(f"KEY {k}")

    else:
        return {"ok": False, "error": f"unknown_type:{t}", "queued": []}

    _write_queue(queue_path, queued)
    return {"ok": True, "queued": queued, "act": a}
