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
