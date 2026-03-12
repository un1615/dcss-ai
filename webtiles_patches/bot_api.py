import ipaddress
import tornado.web
from tornado.escape import json_decode, json_encode, utf8

# ✅ 추가
import os

from webtiles import ws_handler

import re

_ANSI_RE = re.compile(r"\x1b(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
_CTRL_RE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")
_CSI_CURSOR_RE = re.compile(r"\x1b\[(\d*);(\d*)H")
_CSI_ERASE_LINE_RE = re.compile(r"\x1b\[K")
_CSI_SGR_RE = re.compile(r"\x1b\[[0-9;]*m")
_OTHER_ESC_RE = re.compile(r"\x1b\][^\x07]*\x07|\x1b[@-Z\\-_]")


def _render_ansi_screen(output_buffer, width=80, height=24) -> str:
    if not isinstance(output_buffer, (bytes, bytearray)):
        return ""

    try:
        text = output_buffer.decode("utf-8", errors="replace")
    except Exception:
        return ""

    screen = [[" " for _ in range(width)] for _ in range(height)]
    row, col = 0, 0
    i = 0
    n = len(text)

    def clamp():
        nonlocal row, col
        row = max(0, min(height - 1, row))
        col = max(0, min(width - 1, col))

    while i < n:
        ch = text[i]

        # CSI cursor position: ESC[row;colH
        if text.startswith("\x1b[", i):
            m = _CSI_CURSOR_RE.match(text, i)
            if m:
                r = int(m.group(1) or "1")
                c = int(m.group(2) or "1")
                row = r - 1
                col = c - 1
                clamp()
                i = m.end()
                continue

            m = _CSI_ERASE_LINE_RE.match(text, i)
            if m:
                for c2 in range(col, width):
                    screen[row][c2] = " "
                i = m.end()
                continue

            m = _CSI_SGR_RE.match(text, i)
            if m:
                i = m.end()
                continue

            # 처리 안 하는 CSI는 마지막 알파벳까지 스킵
            j = i + 2
            while j < n and not ("@" <= text[j] <= "~"):
                j += 1
            i = min(j + 1, n)
            continue

        # OSC / 기타 ESC 시퀀스 제거
        m = _OTHER_ESC_RE.match(text, i)
        if m:
            i = m.end()
            continue

        # 제어문자 처리
        if ch == "\r":
            col = 0
            i += 1
            continue
        if ch == "\n":
            row += 1
            col = 0
            clamp()
            i += 1
            continue
        if ch == "\x0f":
            i += 1
            continue
        if ord(ch) < 32 or ord(ch) == 127:
            i += 1
            continue

        # 일반 문자 출력
        if 0 <= row < height and 0 <= col < width:
            screen[row][col] = ch
        col += 1
        if col >= width:
            col = width - 1
        i += 1

    lines = ["".join(line).rstrip() for line in screen]
    return "\n".join(lines).rstrip()


def _clean_terminal_text(text: str) -> str:
    # ANSI escape 제거
    text = _ANSI_RE.sub("", text)

    # \r\n / \r 정리
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # 남은 제어문자 제거 (단, \n은 살림)
    text = _CTRL_RE.sub("", text)

    # 빈 줄 너무 많으면 압축
    lines = [line.rstrip() for line in text.split("\n")]
    return "\n".join(lines)


def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


def _extract_screen_text_from_output_buffer(output_buffer) -> str:
    if not isinstance(output_buffer, (bytes, bytearray)):
        return ""

    try:
        text = output_buffer.decode("utf-8", errors="replace")
    except Exception:
        return ""

    # ANSI 대충 제거
    import re

    text = re.sub(r"\x1b(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])", "", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", "", text)

    if len(text) > 6000:
        text = text[-6000:]

    return text


def _socket_debug_snapshot():
    """디버그용: 현재 소켓 목록 요약(개인정보 최소)"""
    out = []
    for i, s in enumerate(list(ws_handler.sockets)):
        try:
            out.append(
                {
                    "i": i,
                    "user": getattr(s, "username", None),
                    "game_id": getattr(s, "game_id", None),
                    "running": bool(s.is_running()),
                    "has_process": bool(getattr(s, "process", None)),
                }
            )
        except Exception as e:
            out.append({"i": i, "err": str(e)})
    return {
        "socket_count": len(list(ws_handler.sockets)),
        "sockets": out[:5],  # 너무 길어지지 않게 앞 5개만
    }


def _proc_turn_candidates(proc):
    """
    proc 안에서 'turn' 관련 속성/함수를 찾아서 값(가능하면)을 뽑아본다.
    """
    results = []

    # 1) proc의 turn 관련 이름들
    for name in [a for a in dir(proc) if "turn" in a.lower()]:
        try:
            v = getattr(proc, name)
            if callable(v):
                try:
                    v = v()
                except TypeError:
                    v = "<callable>"
            results.append((f"proc.{name}", v))
        except Exception as e:
            results.append((f"proc.{name}", f"<err:{type(e).__name__}>"))

    # 2) proc 안에 자주 있는 하위 객체들도 조금만 뒤져보기
    for sub in ["crawl", "game", "state", "player"]:
        if hasattr(proc, sub):
            obj = getattr(proc, sub)
            for name in [a for a in dir(obj) if "turn" in a.lower()]:
                try:
                    v = getattr(obj, name)
                    if callable(v):
                        try:
                            v = v()
                        except TypeError:
                            v = "<callable>"
                    results.append((f"proc.{sub}.{name}", v))
                except Exception as e:
                    results.append((f"proc.{sub}.{name}", f"<err:{type(e).__name__}>"))

    # 너무 길어질 수 있으니 앞쪽만 잘라서 반환
    return results[:80]


def _deep_find_keys(
    obj,
    keys=("turn", "turns", "time", "aut", "tick", "move", "moves"),
    max_results=50,
    max_depth=4,
):
    """
    obj 내부(dict/list 등)를 얕게 탐색해서
    turn/time 관련 키 후보를 찾는다.
    JSON 안전하게 반환한다.
    """
    results = []

    def walk(x, path, depth):
        if len(results) >= max_results or depth > max_depth:
            return

        # dict 처리
        if isinstance(x, dict):
            for k, v in list(x.items()):
                if len(results) >= max_results:
                    return

                k_str = str(k).lower()

                # 키워드 포함되면 기록
                if any(kw in k_str for kw in keys):
                    results.append((".".join(path + [str(k)]), _json_safe(v)))

                # 계속 내려가기
                walk(v, path + [str(k)], depth + 1)

        # list / tuple 처리
        elif isinstance(x, (list, tuple)):
            for i, v in enumerate(list(x)[:50]):
                if len(results) >= max_results:
                    return
                walk(v, path + [f"[{i}]"], depth + 1)

        # 그 외 타입은 무시

    try:
        walk(obj, ["root"], 0)
    except Exception as e:
        results.append(("scan_error", _json_safe(e)))

    return results


def _json_safe(v, max_len=400):
    """어떤 값이 와도 JSON에 넣을 수 있게 문자열로 안전 변환."""
    try:
        if v is None or isinstance(v, (bool, int, float, str)):
            return v
        if isinstance(v, bytes):
            return v[:max_len].decode("utf-8", errors="replace")
        # dict/list/tuple/set 등은 길이 커질 수 있으니 repr로
        s = repr(v)
    except Exception:
        s = "<unreprable>"
    if len(s) > max_len:
        s = s[:max_len] + "...(trunc)"
    return s


def _is_local(remote_ip: str) -> bool:
    try:
        ip = ipaddress.ip_address(remote_ip)
    except ValueError:
        return False
    return ip.is_loopback or ip.is_private or ip.is_link_local


def _tail_lines(path: str, n: int = 50) -> list[str]:
    """텍스트 파일 마지막 n줄을 안전하게 읽는다."""
    n = max(1, min(int(n or 50), 300))  # 1~300 제한
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.read().splitlines()
        return lines[-n:]
    except FileNotFoundError:
        return []
    except Exception as e:
        return [f"<read_error: {e}>"]


def _find_target_socket(username: str | None):
    if username:
        for s in list(ws_handler.sockets):
            if (
                getattr(s, "username", None)
                and s.username.lower() == username.lower()
                and s.is_running()
            ):
                return s
    for s in list(ws_handler.sockets):
        if s.is_running() and getattr(s, "username", None):
            return s
    return None


def _find_numbers_near(obj, target, max_results=30, max_depth=4):
    """
    dict/list 내부를 얕게 탐색해서 int로 보이는 값 중 target 근처 값을 찾는다.
    JSON 안전하게 (경로, 값) 리스트 반환.
    """
    results = []

    def to_int(v):
        if isinstance(v, int):
            return v
        if isinstance(v, str) and v.isdigit():
            try:
                return int(v)
            except Exception:
                return None
        return None

    def walk(x, path, depth):
        if len(results) >= max_results or depth > max_depth:
            return

        if isinstance(x, dict):
            for k, v in list(x.items())[:200]:
                iv = to_int(v)
                if iv is not None and abs(iv - target) <= 50:
                    results.append((".".join(path + [str(k)]), iv))
                walk(v, path + [str(k)], depth + 1)

        elif isinstance(x, (list, tuple)):
            for i, v in enumerate(list(x)[:100]):
                iv = to_int(v)
                if iv is not None and abs(iv - target) <= 50:
                    results.append((".".join(path + [f"[{i}]"]), iv))
                walk(v, path + [f"[{i}]"], depth + 1)

    try:
        walk(obj, ["root"], 0)
    except Exception as e:
        results.append(("scan_error", _json_safe(e)))

    return results


def _truncate(s: str, n: int = 200) -> str:
    s = s.replace("\r", "\\r").replace("\n", "\\n")
    return s if len(s) <= n else (s[:n] + "...(trunc)")


def _extract_textish(obj):
    """
    다양한 구조(dict/list/str)에서 '메시지처럼 보이는 문자열'만 뽑아낸다.
    """
    out = []

    if obj is None:
        return out

    # 문자열이면 그대로
    if isinstance(obj, str):
        s = obj.strip()
        if s:
            out.append(_truncate(s))
        return out

    # bytes면 decode 시도
    if isinstance(obj, (bytes, bytearray)):
        try:
            s = obj.decode("utf-8", errors="replace").strip()
            if s:
                out.append(_truncate(s))
        except Exception:
            pass
        return out

    # dict면 text/message/msg 같은 키를 우선
    if isinstance(obj, dict):
        for k in ["text", "message", "msg", "line", "body", "data"]:
            v = obj.get(k)
            if isinstance(v, str) and v.strip():
                out.append(_truncate(v.strip()))
        # dict 안에 또 nested가 있으면 살짝만 더 파고든다(너무 깊게는 X)
        for k, v in list(obj.items())[:20]:
            if isinstance(v, (str, bytes, bytearray, dict, list, tuple)):
                out.extend(_extract_textish(v))
        return out[:20]

    # list/tuple면 몇 개만 훑기
    if isinstance(obj, (list, tuple)):
        for v in obj[-30:]:
            out.extend(_extract_textish(v))
        return out[:30]

    # 그 외 타입은 문자열로 바꿔서 “정보”만 남김
    try:
        s = str(obj).strip()
        if s:
            out.append(_truncate(s))
    except Exception:
        pass
    return out[:10]


def _get_log_tail(proc, n: int = 12):
    """
    CrawlProcessHandler(proc)에서 로그 후보를 여러 군데에서 찾아 최근 n줄만 반환.
    """
    tail = []

    d = getattr(proc, "__dict__", {}) or {}

    # 1) 가장 유력: queue_messages (웹소켓으로 내보내는 메시지 큐)
    qm = d.get("queue_messages")
    if qm is not None:
        try:
            # deque/list 가정. 뒤에서 n개를 스캔
            items = list(qm)[-50:]
            for it in items:
                tail.extend(_extract_textish(it))
        except Exception:
            pass

    # 2) proc.where.time 같은 거 말고, “최근 이벤트”가 있을 법한 키들
    for k in ["last_milestone", "where", "blocked", "kicked"]:
        if k in d:
            tail.extend(_extract_textish(d.get(k)))

    # 중복 제거 + 최근순 유지(대충)
    cleaned = []
    seen = set()
    for x in tail[-200:]:
        if not x:
            continue
        if x in seen:
            continue
        seen.add(x)
        cleaned.append(x)

    return cleaned[-n:]


def _scan_log_candidates(obj_dict, max_items=8):
    """
    proc.__dict__에서 '로그일 가능성이 있는' 컨테이너(list/tuple/deque 등)를 찾아 샘플을 반환한다.
    - 값이 iterable(list/tuple/set/deque 비슷)이고
    - 그 안에 dict/str/bytes 같은 게 섞인 경우를 후보로 본다
    """
    out = []
    if not isinstance(obj_dict, dict):
        return out

    for k, v in obj_dict.items():
        # queue_messages 처럼 bool은 제외
        if isinstance(v, bool) or v is None:
            continue

        # 너무 큰/복잡한 객체는 스킵(대표적인 파일/소켓/프로세스 핸들)
        if k in ("process", "conn", "logger"):
            continue

        # list/tuple/set/deque 비슷한 것만
        if isinstance(v, (list, tuple, set)):
            items = list(v)
        else:
            # deque 등 iterable일 수 있으나, 문자열/bytes는 제외
            if isinstance(v, (str, bytes, bytearray, dict, int, float)):
                continue
            try:
                items = list(v)  # iterable인지 시험
            except Exception:
                continue

        if not items:
            continue

        # 안에 text/dict가 있는지 대충 검사
        score = 0
        sample = items[-max_items:]
        for it in sample:
            if isinstance(it, (str, bytes, bytearray, dict)):
                score += 1

        if score == 0:
            continue

        out.append(
            {
                "key": k,
                "type": str(type(v)),
                "len": len(items),
                "sample_tail": sample[-3:],  # 너무 길지 않게
            }
        )

    # 길이 큰 후보가 위로 오게
    out.sort(key=lambda x: x["len"], reverse=True)
    return out[:12]


def _scan_socket_for_text_buffers(s):
    """
    websocket socket 객체(s)에서 '최근 메시지/로그 버퍼'로 보이는 필드를 탐색.
    """
    out = []
    d = getattr(s, "__dict__", {}) or {}

    # 어떤 키가 있는지 훑어보기(너무 길면 앞부분만)
    keys = list(d.keys())
    out.append({"socket_dict_keys": keys[:120]})

    # 값이 list/tuple/deque/str 이고 text가 있는 것만 추려서 샘플
    candidates = []
    for k, v in d.items():
        if v is None or isinstance(v, (int, float, bool)):
            continue

        # 문자열 자체면 후보
        if isinstance(v, str):
            if any(
                word in v
                for word in (
                    "You ",
                    "Unknown command",
                    "There",
                    "Done waiting",
                    "start waiting",
                )
            ):
                candidates.append(
                    {"key": k, "type": str(type(v)), "sample": _truncate(v, 200)}
                )
            continue

        # 컨테이너면 마지막 몇 개 샘플
        if isinstance(v, (list, tuple, set)):
            items = list(v)
        else:
            # deque 등 iterable 시도
            if isinstance(v, (dict, bytes, bytearray)):
                continue
            try:
                items = list(v)
            except Exception:
                continue

        if not items:
            continue

        sample_tail = items[-5:]
        textish = []
        for it in sample_tail:
            textish.extend(_extract_textish(it))
        if textish:
            candidates.append(
                {
                    "key": k,
                    "type": str(type(v)),
                    "len": len(items),
                    "textish_tail": textish[-10:],
                }
            )

    # 길이 큰 후보 우선
    candidates.sort(key=lambda x: x.get("len", 0), reverse=True)
    out.append({"socket_candidates": candidates[:15]})
    return out


def _safe_list_tail(x, n=5):
    """iterable이면 list로 바꾸고 tail n개만. 안 되면 에러 문자열 반환."""
    try:
        return list(x)[-n:]
    except Exception as e:
        return f"<not_iterable {type(x)}: {e}>"


def _safe_repr(x, n=300):
    try:
        s = repr(x)
    except Exception as e:
        s = f"<repr_err {e}>"
    return s if len(s) <= n else s[:n] + "...(trunc)"


def _ensure_bot_msg_hook_installed_for_socket(s):
    """
    여러 전송 경로를 동시에 hook해서 '서버->클라' 메시지를 무조건 캡처.
    - s.write_message
    - s.ws_connection.write_message
    - s.ws_connection.write
    """
    try:
        if getattr(s, "_bot_hooks_installed", False):
            return

        def _push(msg):
            try:
                buf = getattr(s, "_bot_msg_ring", None)
                if buf is None:
                    buf = []
                    setattr(s, "_bot_msg_ring", buf)
                buf.append(msg)
                if len(buf) > 300:
                    del buf[:-300]
            except Exception:
                pass

        # 1) s.write_message
        try:
            orig1 = getattr(s, "write_message", None)
            if callable(orig1) and not getattr(s, "_bot_hooked_write_message", False):

                def hooked1(message, *args, **kwargs):
                    try:
                        setattr(
                            s,
                            "_bot_write_message_calls",
                            getattr(s, "_bot_write_message_calls", 0) + 1,
                        )
                        _push(message)
                    except Exception:
                        pass
                    return orig1(message, *args, **kwargs)

                setattr(s, "write_message", hooked1)
                setattr(s, "_bot_hooked_write_message", True)
        except Exception:
            pass

        conn = getattr(s, "ws_connection", None)

        # 2) conn.write_message
        try:
            orig2 = getattr(conn, "write_message", None) if conn else None
            if (
                conn
                and callable(orig2)
                and not getattr(s, "_bot_hooked_wsconn_write_message", False)
            ):

                def hooked2(message, *args, **kwargs):
                    try:
                        setattr(
                            s,
                            "_bot_wsconn_write_calls",
                            getattr(s, "_bot_wsconn_write_calls", 0) + 1,
                        )
                        _push(message)
                    except Exception:
                        pass
                    return orig2(message, *args, **kwargs)

                setattr(conn, "write_message", hooked2)
                setattr(s, "_bot_hooked_wsconn_write_message", True)
        except Exception:
            pass

        # 3) conn.write (어떤 버전은 여기로 감)
        try:
            orig3 = getattr(conn, "write", None) if conn else None
            if (
                conn
                and callable(orig3)
                and not getattr(s, "_bot_hooked_wsconn_write", False)
            ):

                def hooked3(message, *args, **kwargs):
                    try:
                        setattr(
                            s,
                            "_bot_wsconn_write_raw_calls",
                            getattr(s, "_bot_wsconn_write_raw_calls", 0) + 1,
                        )
                        _push(message)
                    except Exception:
                        pass
                    return orig3(message, *args, **kwargs)

                setattr(conn, "write", hooked3)
                setattr(s, "_bot_hooked_wsconn_write", True)
        except Exception:
            pass

        setattr(s, "_bot_hooks_installed", True)
    except Exception:
        pass


class BotBaseHandler(tornado.web.RequestHandler):
    def prepare(self):
        if not _is_local(self.request.remote_ip):
            raise tornado.web.HTTPError(
                403,
                f"bot api is private-network-only (remote_ip={self.request.remote_ip})",
            )

    def write_json(self, obj, status=200):
        self.set_status(status)
        self.set_header("Content-Type", "application/json; charset=utf-8")
        self.write(json_encode(obj))


class BotStateHandler(BotBaseHandler):
    def get(self):

        username = self.get_argument("username", None)
        debug = self.get_argument("debug", "0") == "1"
        s = _find_target_socket(username)
        if not s:
            return self.write_json(
                {"ok": False, "error": "no running game socket found"}, status=404
            )
        # ✅ 여기 추가 (if 블록 밖!)
        _ensure_bot_msg_hook_installed_for_socket(s)

        proc = s.process
        where = None
        idle = None
        turn = None
        try:
            where = proc.human_readable_where()
        except Exception:
            pass
        try:
            idle = s.idle_time()
        except Exception:
            pass
        # turn 추출 (proc.__dict__["where"]["turn"])
        try:
            w = getattr(proc, "__dict__", {}).get("where")
            if isinstance(w, dict):
                t = w.get("turn")
                if isinstance(t, str) and t.isdigit():
                    turn = int(t)
                elif isinstance(t, int):
                    turn = t
        except Exception:
            pass
        screen_text = ""
        try:
            p = getattr(proc, "process", None)
            if p is not None:
                output_buffer = getattr(p, "output_buffer", None)

                width, height = 80, 24
                termsize = getattr(p, "termsize", None)
                if isinstance(termsize, (list, tuple)) and len(termsize) >= 2:
                    width, height = int(termsize[0]), int(termsize[1])

                screen_text = _render_ansi_screen(
                    output_buffer,
                    width=width,
                    height=height,
                )
        except Exception:
            pass

        # ✅ 핵심: socket에 쌓인 링버퍼에서 최근 "메시지 로그" 뽑기
        ring = getattr(s, "_bot_msg_ring", []) or []
        msg_tail = []
        for it in list(ring)[-80:]:
            msg_tail.extend(_extract_textish(it))
        msg_tail = msg_tail[-15:]

        payload = {
            "ok": True,
            "user": s.username,
            "game_id": s.game_id,
            "running": bool(s.is_running()),
            "where": where,
            "idle_time": idle,
            "turn": turn,
            "blocked": _json_safe(getattr(proc, "__dict__", {}).get("blocked")),
            "last_activity_time": _json_safe(
                getattr(proc, "__dict__", {}).get("last_activity_time")
            ),
            # ✅ 이제 msg_tail은 "진짜 로그 후보"가 들어옴
            "msg_tail": msg_tail,
            "screen_text": screen_text,
        }

        if debug:
            payload["debug_bot_msg_ring_len"] = len(
                getattr(s, "_bot_msg_ring", []) or []
            )
            payload["debug_write_message_calls"] = getattr(
                s, "_bot_write_message_calls", 0
            )
            payload["debug_wsconn_write_calls"] = getattr(
                s, "_bot_wsconn_write_calls", 0
            )
            payload["debug_wsconn_write_raw_calls"] = getattr(
                s, "_bot_wsconn_write_raw_calls", 0
            )

            proc_dict = getattr(proc, "__dict__", {}) or {}

            payload["debug_proc_keys"] = sorted(list(proc_dict.keys()))[:200]
            payload["debug_where_raw"] = _json_safe(proc_dict.get("where"))
            payload["debug_scan_log_candidates"] = _scan_log_candidates(proc_dict)
            payload["debug_turn_candidates"] = _proc_turn_candidates(proc)
            payload["debug_socket_snapshot"] = _socket_debug_snapshot()
            # proc.conn / proc.process / queue_messages 더 보기
            try:
                conn = getattr(proc, "conn", None)
                if conn is not None:
                    payload["debug_conn_type"] = str(type(conn))
                    payload["debug_conn_dir"] = [
                        x for x in dir(conn) if not x.startswith("_")
                    ][:150]
                    payload["debug_conn_dict_keys"] = sorted(
                        list(getattr(conn, "__dict__", {}).keys())
                    )[:150]
            except Exception as e:
                payload["debug_conn_err"] = str(e)

            try:
                p = getattr(proc, "process", None)
                if p is not None:
                    payload["debug_process_type"] = str(type(p))
                    payload["debug_process_dir"] = [
                        x for x in dir(p) if not x.startswith("_")
                    ][:150]
                    payload["debug_process_dict_keys"] = sorted(
                        list(getattr(p, "__dict__", {}).keys())
                    )[:150]
                    payload["debug_process_termsize"] = _json_safe(
                        getattr(p, "termsize", None)
                    )
            except Exception as e:
                payload["debug_process_err"] = str(e)

            try:
                qm = getattr(proc, "queue_messages", None)
                payload["debug_queue_messages_type"] = str(type(qm))
                if isinstance(qm, list):
                    payload["debug_queue_messages_len"] = len(qm)
                    payload["debug_queue_messages_tail"] = [
                        _json_safe(x) for x in qm[-10:]
                    ]
                else:
                    payload["debug_queue_messages_repr"] = _json_safe(qm)
            except Exception as e:
                payload["debug_queue_messages_err"] = str(e)

            for name in ["crawl", "game", "state", "player"]:
                try:
                    obj = getattr(proc, name, None)
                    if obj is not None:
                        payload[f"debug_{name}_type"] = str(type(obj))
                        payload[f"debug_{name}_dir"] = [
                            x for x in dir(obj) if not x.startswith("_")
                        ][:120]
                except Exception as e:
                    payload[f"debug_{name}_err"] = str(e)
            try:
                conn = getattr(proc, "conn", None)
                if conn is not None:
                    msg_buffer = getattr(conn, "msg_buffer", None)
                    payload["debug_msg_buffer_type"] = str(type(msg_buffer))
                    if isinstance(msg_buffer, list):
                        payload["debug_msg_buffer_len"] = len(msg_buffer)
                        payload["debug_msg_buffer_tail"] = [
                            _json_safe(x) for x in msg_buffer[-10:]
                        ]
                    else:
                        payload["debug_msg_buffer_repr"] = _json_safe(msg_buffer)
            except Exception as e:
                payload["debug_msg_buffer_err"] = str(e)

            try:
                p = getattr(proc, "process", None)
                if p is not None:
                    output_buffer = getattr(p, "output_buffer", None)
                    error_buffer = getattr(p, "error_buffer", None)

                    payload["debug_output_buffer_type"] = str(type(output_buffer))
                    payload["debug_error_buffer_type"] = str(type(error_buffer))

                    if isinstance(output_buffer, (bytes, bytearray)):
                        payload["debug_output_buffer_len"] = len(output_buffer)
                        payload["debug_output_buffer_tail"] = repr(
                            output_buffer[-1000:]
                        )
                    else:
                        payload["debug_output_buffer_repr"] = _json_safe(output_buffer)

                    if isinstance(error_buffer, (bytes, bytearray)):
                        payload["debug_error_buffer_len"] = len(error_buffer)
                        payload["debug_error_buffer_tail"] = repr(error_buffer[-1000:])
                    else:
                        payload["debug_error_buffer_repr"] = _json_safe(error_buffer)
            except Exception as e:
                payload["debug_output_buffer_err"] = str(e)
        return self.write_json(payload)


class BotLogHandler(BotBaseHandler):
    def get(self):
        username = self.get_argument("username", None)
        n = self.get_argument("n", "50")

        if not username:
            return self.write_json(
                {"ok": False, "error": "username is required"}, status=400
            )

        # ✅ 현재 우리가 찾은 로그 파일 위치
        path = f"/data/rcs/{username}/{username}.txt"

        lines = _tail_lines(path, n=int(n))
        return self.write_json(
            {
                "ok": True,
                "user": username,
                "path": path,
                "n": int(n),
                "lines": lines,
            }
        )


class BotInputHandler(BotBaseHandler):
    def post(self):
        try:
            body = self.request.body.decode("utf-8", errors="strict")
            obj = json_decode(body) if body else {}
        except Exception:
            raise tornado.web.HTTPError(400, "invalid json")

        keys = obj.get("keys", "")
        username = obj.get("username", None)

        if not isinstance(keys, str) or not keys:
            raise tornado.web.HTTPError(400, "keys must be a non-empty string")

        s = _find_target_socket(username)
        if not s or not s.is_running() or not s.process:
            raise tornado.web.HTTPError(409, "no running game to send input")

        # ✅ WebTiles가 원래 입력 처리하는 경로를 그대로 탄다.
        # process_handler.CrawlProcessHandler.handle_input()는 {"msg":"input","text":...}를 받아
        # 내부 terminal.write_input()로 내려보낸다.
        msg = json_encode({"msg": "input", "text": keys})
        s.process.handle_input(msg)

        return self.write_json({"ok": True, "sent": keys, "user": s.username})
