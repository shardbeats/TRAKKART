"""Original TRAKKART palettes (MIT).

Designed from scratch for type-beat covers. Do not copy exact values
from GPL projects; these RGB values are original to the TRAKK SUITE.
"""

PALETTES: dict[str, list[tuple[int, int, int]]] = {
    "BW": [(0, 0, 0), (255, 255, 255)],
    "SLIME": [
        (10, 18, 12),
        (46, 92, 52),
        (126, 178, 78),
        (222, 238, 178),
    ],
    "VAPOR": [
        (12, 10, 28),
        (88, 40, 140),
        (220, 70, 150),
        (250, 225, 190),
    ],
    "EMBER": [
        (16, 12, 12),
        (110, 30, 26),
        (216, 110, 40),
        (245, 230, 190),
    ],
}


def get_palette(name: str) -> list[tuple[int, int, int]] | None | str:
    """Return None for pure B&W (fast path), "SOURCE" sentinel for auto-extract,
    or an RGB list for named palettes."""
    if name == "BW":
        return None
    if name == "SOURCE":
        return "SOURCE"
    return PALETTES.get(name, PALETTES["SLIME"])


def palette_names() -> list[str]:
    return [*PALETTES.keys(), "SOURCE"]
