"""TRAKK family theme (QSS with dev/frozen fallback + variants).

Single source: app/ui/theme.qss is the Dark recipe. Variants are
token swaps over the same file, so every theme styles every selector.
"""

from __future__ import annotations

from pathlib import Path

THEME_FILE = Path(__file__).with_name("theme.qss")

THEMES: dict[str, dict[str, str]] = {
    "dark": {
        "label": "Dark",
        "bg": "#151617", "panel": "#1C1D1F", "surface": "#202124",
        "hover": "#2A2C30", "border": "#45474A", "text": "#E5E5E5",
        "dim": "#92959A", "disabled": "#383B40", "accent": "#F5A623",
        "on_accent": "#161617", "accent_hover": "#FFB52E",
        "accent_pressed": "#D8901D", "track": "#5A451F",
    },
    "light": {
        "label": "Light",
        "bg": "#EDEDED", "panel": "#FFFFFF", "surface": "#F5F5F5",
        "hover": "#E0E0E0", "border": "#BDBDBD", "text": "#1B1B1B",
        "dim": "#616161", "disabled": "#9E9E9E", "accent": "#C46A00",
        "on_accent": "#FFFFFF", "accent_hover": "#E07B00",
        "accent_pressed": "#9E5600", "track": "#E8C87E",
    },
    "green": {
        "label": "Handheld green",
        "bg": "#101A10", "panel": "#182418", "surface": "#1F2F1F",
        "hover": "#2A402A", "border": "#3D5A3D", "text": "#D7E8B0",
        "dim": "#7A9463", "disabled": "#3A4A3A", "accent": "#8BC34A",
        "on_accent": "#101A10", "accent_hover": "#A5D66A",
        "accent_pressed": "#6FA038", "track": "#3D5A23",
    },
    "pink": {
        "label": "Pink",
        "bg": "#1D1319", "panel": "#291B22", "surface": "#33232C",
        "hover": "#432E3A", "border": "#5E4252", "text": "#F6D9E4",
        "dim": "#A97F92", "disabled": "#4E3642", "accent": "#FF6FA5",
        "on_accent": "#1D1319", "accent_hover": "#FF8FB9",
        "accent_pressed": "#D6568A", "track": "#6E3A50",
    },
}

# Base (dark) tokens as written in theme.qss, in replace-safe order
# (longest first is unnecessary: all tokens are distinct 7-char hexes).
_BASE_TOKENS = ("#151617", "#1C1D1F", "#202124", "#2A2C30", "#45474A",
                "#E5E5E5", "#92959A", "#383B40", "#F5A623", "#161617",
                "#FFB52E", "#D8901D", "#5A451F")
_TOKEN_KEYS = ("bg", "panel", "surface", "hover", "border", "text",
               "dim", "disabled", "accent", "on_accent", "accent_hover",
               "accent_pressed", "track")


def theme_names() -> list[str]:
    return list(THEMES.keys())


def theme_label(name: str) -> str:
    return THEMES.get(name, THEMES["dark"])["label"]


def load_stylesheet(name: str = "dark") -> str:
    """Read theme.qss and swap tokens for the variant. Empty if missing."""
    try:
        if not THEME_FILE.exists():
            return ""
        css = THEME_FILE.read_text(encoding="utf-8")
    except Exception:
        return ""
    tokens = THEMES.get(name, THEMES["dark"])
    for hex_base, key in zip(_BASE_TOKENS, _TOKEN_KEYS):
        css = css.replace(hex_base, tokens[key])
    return css


def set_theme(app, name: str) -> str:
    """Apply a variant to the QApplication. Returns the resolved name.

    Idempotent per app instance: re-applying the same theme is a no-op.
    (Repolishing the whole app on every MainWindow() made startup O(n²)
    across the test-suite and slowed real restarts for nothing.)
    """
    resolved = name if name in THEMES else "dark"
    try:
        if app is not None and app.property("_trakkart_theme") == resolved:
            return resolved
        app.setStyleSheet(load_stylesheet(resolved))
        app.setProperty("_trakkart_theme", resolved)
    except Exception:
        pass
    return resolved


def accent(name: str = "dark") -> str:
    return THEMES.get(name, THEMES["dark"])["accent"]
