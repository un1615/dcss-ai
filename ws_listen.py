import os
import sys
import json
import asyncio
import zlib

try:
    import websockets
except ImportError:
    print(
        "websockets 라이브러리가 필요해요. 아래 명령으로 설치하세요:\n  pip install websockets==11.0.3"
    )
    sys.exit(1)

try:
    import cbor2
except ImportError:
    print("cbor2 라이브러리가 필요해요. 아래 명령으로 설치하세요:\n  pip install cbor2")
    sys.exit(1)

WS_URL = os.environ.get("DCSS_WS_URL", "ws://localhost:9090/socket")
COOKIE = os.environ.get("DCSS_COOKIE", "")


def try_decode_bytes(b: bytes):
    # 1) CBOR 바로 디코드
    try:
        return ("cbor", cbor2.loads(b))
    except Exception:
        pass

    # 2) zlib로 한번 풀어보고 CBOR/JSON 시도 (서버에 따라 이 케이스가 있음)
    for wbits in (-15, zlib.MAX_WBITS, zlib.MAX_WBITS | 16):  # raw-deflate, zlib, gzip
        try:
            raw = zlib.decompress(b, wbits=wbits)
        except Exception:
            continue

        try:
            return (f"zlib({wbits})->cbor", cbor2.loads(raw))
        except Exception:
            pass

        try:
            return (
                f"zlib({wbits})->json",
                json.loads(raw.decode("utf-8", errors="strict")),
            )
        except Exception:
            pass

    return (None, None)


async def main():
    headers = {}
    if COOKIE.strip():
        headers["Cookie"] = COOKIE.strip()

    print(f"[connect] {WS_URL}")
    print(
        "[connect] Cookie header set"
        if headers
        else "[connect] Cookie header NOT set (may fail if server requires login session)"
    )

    async with websockets.connect(WS_URL, extra_headers=headers) as ws:
        print("[ok] connected. Listening...\n")
        while True:
            msg = await ws.recv()

            # TEXT
            if isinstance(msg, str):
                try:
                    obj = json.loads(msg)
                    print(f"[text-json] {obj.get('msg', 'unknown')}")
                except Exception:
                    print(f"[text] {msg[:200]}")
                continue

            # BYTES
            if isinstance(msg, (bytes, bytearray)):
                kind, obj = try_decode_bytes(bytes(msg))
                if obj is None:
                    print(f"[bytes] len={len(msg)} head={bytes(msg)[:16]!r}")
                    continue

                # 보기 좋게 요약
                if isinstance(obj, dict) and "msg" in obj:
                    print(f"[{kind}] msg={obj.get('msg')}")
                else:
                    # 너무 길면 앞부분만
                    s = repr(obj)
                    print(f"[{kind}] {s[:300]}")
                continue

            print(f"[unknown] {type(msg)}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[exit] bye")
