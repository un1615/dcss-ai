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
    """
    ascii_map_lines : list[str]
    player_pos : (x, y)

    return:
        [
            {char,x,y,dx,dy,dist}
        ]
    """

    monsters = []

    if not ascii_map_lines or player_pos is None:
        return monsters

    px, py = player_pos

    for y, row in enumerate(ascii_map_lines):
        for x, ch in enumerate(row):

            if is_monster_char(ch):

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
