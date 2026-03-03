from webtiles_client import WebTilesClient

BASE_URL = "http://localhost:9090"
USERNAME = "MinZZang"

if __name__ == "__main__":
    c = WebTilesClient(BASE_URL, USERNAME)

    state = c.get_state()
    log = c.get_log(n=20)

    print("=== STATE ===")
    print(state)

    print("\n=== LOG tail ===")
    for line in log.get("lines", []):
        print(line)
