import os, asyncio, binascii
import websockets

WS_URL = os.environ.get("DCSS_WS_URL", "ws://localhost:9090/socket")
COOKIE = os.environ.get("DCSS_COOKIE", "")


async def main():
    headers = {}
    if COOKIE.strip():
        headers["Cookie"] = COOKIE.strip()

    async with websockets.connect(WS_URL, extra_headers=headers) as ws:
        print("[ok] connected. Probing 10 frames...\n")
        for i in range(10):
            msg = await ws.recv()
            if isinstance(msg, str):
                print(f"[{i}] TEXT {msg[:200]}")
            else:
                b = bytes(msg)
                head = b[:64]
                print(f"[{i}] BYTES len={len(b)} hex={binascii.hexlify(head).decode()}")
        print("\n[done]")


if __name__ == "__main__":
    asyncio.run(main())
