"""TRAKKART animation timeline (MIT, clean-room). No dependencies.

Layers animate render params over frames: {prop, frm, to, ease, start, end}.
- prop: one of ANIM_PROPS (render-kwarg names).
- frm/to: values at span start/end (clamped to the prop range).
- ease: linear | in | out.
- start/end: frame window (0-23, swapped if reversed, clamped).
- Outside every span the base preset value rules; later layers win.
- Loop: the timeline loops (VIDEO loops, GIF ping-pong optional).

Pure math + dicts: fully testable without Qt or ffmpeg.
"""

from __future__ import annotations

EASES = ("linear", "in", "out")

# prop -> (min, max, kind). kind int values round on eval.
ANIM_PROPS: dict[str, tuple[float, float, str]] = {
    "threshold": (1.0, 254.0, "float"),
    "pixel_size": (1.0, 8.0, "int"),
    "pre_hue": (-180.0, 180.0, "float"),
    "grain": (0.0, 100.0, "float"),
    "glow_intensity": (0.0, 100.0, "float"),
    "glitch_chroma": (0.0, 20.0, "int"),
    "wave": (0.0, 30.0, "int"),
    "jpeg": (0.0, 100.0, "float"),
    "fade": (0.0, 100.0, "float"),
    "split_tone": (0.0, 100.0, "float"),
}

MAX_SPAN = 23


def ease_value(ease: str, t: float) -> float:
    """Eased 0..1 for t in 0..1. Unknown ease -> linear."""
    t = min(1.0, max(0.0, float(t)))
    if ease == "in":
        return t * t
    if ease == "out":
        return 1.0 - (1.0 - t) * (1.0 - t)
    return t


def normalize_layers(raw: list | tuple | dict | None) -> list[dict]:
    """Validate/coerce a layer list. Unknown props/eases dropped."""
    items: list[dict] = []
    if isinstance(raw, dict):
        raw = [raw]
    for entry in list(raw or []):
        if not isinstance(entry, dict):
            continue
        prop = str(entry.get("prop", ""))
        if prop not in ANIM_PROPS:
            continue
        lo, hi, _kind = ANIM_PROPS[prop]
        ease = str(entry.get("ease", "linear"))
        if ease not in EASES:
            ease = "linear"

        def _num(v, default):
            try:
                return min(hi, max(lo, float(v)))
            except (TypeError, ValueError):
                return float(default)

        try:
            start = max(0, min(MAX_SPAN, int(entry.get("start", 0))))
            end = max(0, min(MAX_SPAN, int(entry.get("end", MAX_SPAN))))
        except (TypeError, ValueError):
            start, end = 0, MAX_SPAN
        if start > end:
            start, end = end, start
        items.append({
            "prop": prop,
            "frm": _num(entry.get("frm", lo), lo),
            "to": _num(entry.get("to", hi), hi),
            "ease": ease,
            "start": start,
            "end": end,
        })
    return items


def eval_layers(layers: list | dict | None, base: dict, frame: int, n_frames: int) -> dict:
    """Override base kwargs with active layers at `frame`. Returns a new dict."""
    out = dict(base)
    norm = normalize_layers(layers)
    i = max(0, min(max(1, int(n_frames)) - 1, int(frame)))
    for layer in norm:
        if not layer["start"] <= i <= layer["end"]:
            continue
        span = max(1, layer["end"] - layer["start"])
        t = ease_value(layer["ease"], (i - layer["start"]) / span)
        v = layer["frm"] + (layer["to"] - layer["frm"]) * t
        _, _, kind = ANIM_PROPS[layer["prop"]]
        out[layer["prop"]] = int(round(v)) if kind == "int" else float(v)
    return out


def animated_props(layers: list | dict | None) -> list[str]:
    """Sorted props touched by at least one valid layer (for control locks)."""
    return sorted({layer["prop"] for layer in normalize_layers(layers)})


__all__ = ["ANIM_PROPS", "EASES", "MAX_SPAN", "animated_props", "ease_value", "eval_layers", "normalize_layers"]
