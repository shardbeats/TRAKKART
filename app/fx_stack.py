"""TRAKKART FX stack registry (v1.2).

The pipeline used to be a fixed chain; now the post-dither chain is an
ordered stack of effect ids. Params still live in RenderSpec legacy
fields (single source of truth); the stack only stores ORDER + ENABLED,
so old presets migrate to the default order with byte-identical output
and reordering visibly changes the result (commutativity tested).
"""

from __future__ import annotations

import logging

log = logging.getLogger("trakkart")

# Legacy order = pipeline.render_spec order before the stack.
# brand (replace_white) stays pinned right after the dither (not reordered:
# it is brand mapping, not creative FX).
DEFAULT_FX_ORDER: tuple[str, ...] = (
    "split_tone",
    "fade",
    "glow",
    "grain",
    "halftone",
    "dust",
    "vignette",
    "scanlines",
    "grille",
    "border",
    "letterbox",
    "chroma",
    "slice",
    "pixelsort",
    "wave",
    "mosh",
    "jpeg",
    "post_blur",
    "post_sharpen",
    "pasteup",
)

FX_IDS: frozenset[str] = frozenset(DEFAULT_FX_ORDER)

# Short labels for the ADD combo / list.
FX_LABELS: dict[str, str] = {
    "split_tone": "Split tone",
    "fade": "Fade",
    "glow": "Halo",
    "grain": "Grain",
    "halftone": "Halftone dots",
    "dust": "Dust",
    "vignette": "Vignette",
    "scanlines": "Scanlines",
    "grille": "RGB grille",
    "border": "Border",
    "letterbox": "Letterbox",
    "chroma": "Chromatic aberration",
    "slice": "Slice shift",
    "pixelsort": "Pixel sort",
    "wave": "Wave",
    "mosh": "Datamosh",
    "jpeg": "JPEG glitch",
    "post_blur": "Post blur",
    "post_sharpen": "Post sharpen",
    "pasteup": "Paste-Up",
}


def normalize_stack(raw: list | tuple | None) -> list[dict]:
    """Validates/normalizes a stack [{id, enabled}] or a plain [id, ...] list.

    None -> full enabled default (legacy). Unknown ids are
    ignored; duplicates collapse (first occurrence wins).
    """
    if raw is None:
        return [{"id": fid, "enabled": True} for fid in DEFAULT_FX_ORDER]
    items: list[dict] = []
    seen: set[str] = set()
    seq = list(raw) if isinstance(raw, (list, tuple)) else []
    for entry in seq:
        if isinstance(entry, str):
            fid, enabled = entry, True
        elif isinstance(entry, dict):
            fid = entry.get("id", "")
            enabled = bool(entry.get("enabled", True))
        else:
            log.warning("fx_stack: ignoring unsupported entry %r", entry)
            continue
        if fid not in FX_IDS:
            log.warning("fx_stack: ignoring unknown effect id %r", fid)
            continue
        if fid in seen:
            continue
        seen.add(fid)
        items.append({"id": fid, "enabled": enabled})
    # Missing effects are appended enabled (forward migration:
    # partial-stack presets stay complete).
    for fid in DEFAULT_FX_ORDER:
        if fid not in seen:
            items.append({"id": fid, "enabled": True})
    return items


def stack_ids(stack: list[dict]) -> list[str]:
    return [e["id"] for e in normalize_stack(stack) if e.get("enabled")]


__all__ = ["DEFAULT_FX_ORDER", "FX_IDS", "FX_LABELS", "normalize_stack", "stack_ids"]
