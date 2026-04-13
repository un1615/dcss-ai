import re


def parse_hp(text: str):
    match = re.search(r"Health:\s*(\d+)/(\d+)", text)
    if match:
        return int(match.group(1)), int(match.group(2))
    return None


def compute_hp_ratio(hp):
    """
    hp: (cur, max) or None
    returns: float 0.0~1.0 or None
    """
    if not hp:
        return None
    cur, max_ = hp
    if max_ <= 0:
        return 0.0
    r = cur / max_
    if r < 0.0:
        return 0.0
    if r > 1.0:
        return 1.0
    return r


def is_monster_char(ch: str) -> bool:
    """
    간단한 몬스터 문자 판별
    알파벳이면 일단 몬스터 후보로 본다
    """
    if not ch or len(ch) != 1:
        return False

    if ch == "@":
        return False

    return ch.isalpha()


def find_visible_monsters(ascii_map_lines, player_pos):
    monsters = []

    if not ascii_map_lines or player_pos is None:
        return monsters

    px, py = player_pos

    for y, row in enumerate(ascii_map_lines):
        if y >= 17:
            continue  # 메시지 영역 무시

        for x, ch in enumerate(row):
            if ch.isupper() and ch not in {"@", "#"}:
                dx = x - px
                dy = y - py
                dist = abs(dx) + abs(dy)

                monsters.append(
                    {
                        "char": ch,
                        "x": x,
                        "y": y,
                        "dx": dx,
                        "dy": dy,
                        "dist": dist,
                    }
                )

    monsters.sort(key=lambda m: m["dist"])
    return monsters


def split_screen_regions(screen_text: str):
    lines = screen_text.splitlines()

    status_markers = [
        "Health:",
        "Magic:",
        "AC:",
        "EV:",
        "SH:",
        "XL:",
        "Noise:",
        "Time:",
        "Place:",
        "a) ",
        "b) ",
        "c) ",
        "Throw:",
    ]

    split_at = None

    # 먼저 위쪽 화면에서 상태창 시작 x를 하나 찾는다
    for i, line in enumerate(lines):
        if i >= 17:
            continue

        for marker in status_markers:
            idx = line.find(marker)
            if idx != -1:
                if split_at is None or idx < split_at:
                    split_at = idx

    if split_at is None:
        split_at = 40

    map_lines = []
    status_lines = []
    message_lines = []

    for i, line in enumerate(lines):
        if i >= 17:
            message_lines.append(line.rstrip())
            continue

        left = line[:split_at].rstrip()
        right = line[split_at:].rstrip()

        map_lines.append(left)
        status_lines.append(right)

    return {
        "map_lines": map_lines,
        "status_lines": status_lines,
        "message_lines": [x for x in message_lines if x.strip()],
    }


def find_player_position(ascii_map: str | None):
    if not ascii_map:
        return None

    lines = ascii_map.splitlines()

    for y, line in enumerate(lines):
        for x, ch in enumerate(line):
            if ch == "@":
                return (x, y)

    return None


import re


def extract_hp(status_lines):
    for line in status_lines:
        m = re.search(r"Health:\s*(\d+)/(\d+)", line)
        if m:
            cur = int(m.group(1))
            max_hp = int(m.group(2))
            hp_pct = cur / max_hp if max_hp > 0 else 0.0
            return {
                "cur": cur,
                "max": max_hp,
                "pct": hp_pct,
            }
    return None
