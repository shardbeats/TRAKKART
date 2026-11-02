"""User-customizable keyboard shortcuts (single source of truth).

Before: shortcuts were hardcoded across menus (`QAction.setShortcut`),
`QShortcut` objects, `keyPressEvent`, plus a static table in the help
dialog that could drift. Now every action lives here (id, label,
default keys); menus, special keys and the editor dialog all read
from this registry. User overrides persist in `shortcuts.json` next
to the other portable data (TRAKKART_DATA_DIR aware, test seam via
explicit paths).

One single-key sequence per action (no chords): what QAction shows
and what the hold-to-compare matcher understands.
"""

from __future__ import annotations

import json
from pathlib import Path

# (action id, dialog label, default keys). "" = unbound by default
# (still assignable). Keep defaults to platform conventions.
ACTIONS: tuple[tuple[str, str, str], ...] = (
    ("file_open", "Open image...", "Ctrl+O"),
    ("file_export", "Export...", "Ctrl+Shift+S"),
    ("file_quick_export", "Quick export", "Ctrl+S"),
    ("file_batch", "Batch folder...", "Ctrl+B"),
    ("file_watch", "Watch folder...", ""),
    ("file_share_export", "Export preset...", ""),
    ("file_share_import", "Import preset...", ""),
    ("file_import_metadata", "Import metadata...", ""),
    ("file_settings", "Settings...", "Ctrl+,"),
    ("edit_undo", "Undo image", "Ctrl+Z"),
    ("edit_redo", "Redo", "Ctrl+Y"),
    ("edit_randomize", "Surprise me", "Ctrl+R"),
    ("edit_copy", "Copy result", "Ctrl+C"),
    ("edit_paste", "Paste image", "Ctrl+V"),
    ("edit_method_prev", "Previous method", "Alt+Left"),
    ("edit_method_next", "Next method", "Alt+Right"),
    ("edit_rotate_left", "Rotate left", ""),
    ("edit_rotate_right", "Rotate right", ""),
    ("edit_flip_h", "Flip H", ""),
    ("edit_flip_v", "Flip V", ""),
    ("edit_invert", "Invert", ""),
    ("view_refresh", "Refresh preview", "F5"),
    ("view_compare_hold", "Hold to compare (hold key)", "Space"),
    ("view_zoom_in", "Zoom in", "Ctrl+="),
    ("view_zoom_out", "Zoom out", "Ctrl+-"),
    ("view_zoom_fit", "Zoom fit", "Ctrl+0"),
    ("view_zoom_100", "Zoom 100%", "Ctrl+1"),
    ("help_manual", "User manual", "F1"),
    ("help_shortcuts", "Keyboard shortcuts", ""),
)

_IDS = frozenset(a for a, _, _ in ACTIONS)
_DEFAULTS = {a: d for a, _, d in ACTIONS}
_LABELS = {a: label for a, label, _ in ACTIONS}

FILENAME = "shortcuts.json"


def action_ids() -> tuple[str, ...]:
    return tuple(a for a, _, _ in ACTIONS)


def action_label(action_id: str) -> str:
    return _LABELS.get(action_id, action_id)


def default_keys(action_id: str) -> str:
    return _DEFAULTS.get(action_id, "")


def _data_path(data_dir=None) -> Path:
    from app.paths import get_data_dir

    base = Path(data_dir) if data_dir else get_data_dir()
    base.mkdir(parents=True, exist_ok=True)
    return base / FILENAME


def normalize_keys(text: str) -> str:
    """Canonical PortableText or "" (unbound/invalid)."""
    from PySide6.QtGui import QKeySequence

    try:
        seq = QKeySequence(str(text or "").strip())
    except Exception:  # noqa: BLE001
        return ""
    if seq.isEmpty() or seq.count() != 1:
        return ""
    return seq.toString(QKeySequence.SequenceFormat.PortableText)


def load_custom(data_dir=None) -> dict[str, str]:
    """User overrides {id: keys} (validated; unknown ids dropped)."""
    try:
        raw = json.loads(_data_path(data_dir).read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}
    if not isinstance(raw, dict):
        return {}
    bindings = raw.get("bindings", raw)
    if not isinstance(bindings, dict):
        return {}
    out: dict[str, str] = {}
    for action_id, keys in bindings.items():
        if action_id not in _IDS:
            continue
        norm = normalize_keys(keys) if isinstance(keys, str) else ""
        if norm:
            out[action_id] = norm
        # Empty string = explicitly unbound: record as "" so it wins
        # over the default instead of falling through.
        elif isinstance(keys, str) and keys.strip() == "":
            out[action_id] = ""
    return out


def save_custom(bindings: dict[str, str], data_dir=None) -> Path:
    """Persist overrides (only differences from defaults are kept)."""
    keep: dict[str, str] = {}
    for action_id, keys in (bindings or {}).items():
        if action_id not in _IDS:
            continue
        if not isinstance(keys, str):
            continue
        if keys.strip() == "":
            norm = ""  # explicit unbind (beats a non-empty default)
        else:
            norm = normalize_keys(keys)
            if not norm:
                continue  # garbage in: dropped, never stored
        default = normalize_keys(_DEFAULTS.get(action_id, ""))
        if norm != default:
            keep[action_id] = norm
    path = _data_path(data_dir)
    path.write_text(json.dumps({"version": 1, "bindings": keep}, indent=2),
                    encoding="utf-8")
    return path


def reset_custom(data_dir=None) -> Path:
    """Forget all overrides (back to defaults)."""
    path = _data_path(data_dir)
    try:
        if path.exists():
            path.unlink()
    except Exception:  # noqa: BLE001
        pass
    return path


def effective_keys(action_id: str, custom: dict | None = None) -> str:
    """Winning sequence: user override, else default ("" = unbound)."""
    if custom and action_id in custom:
        return custom[action_id]
    return _DEFAULTS.get(action_id, "")


def current_custom(win) -> dict:
    """Runtime overrides attached to the window ({} when none)."""
    try:
        return dict(getattr(win, "_shortcuts_custom", None) or {})
    except Exception:  # noqa: BLE001
        return {}


def effective_for(win, action_id: str) -> str:
    """Effective sequence for this window (override or default)."""
    return normalize_keys(effective_keys(action_id, current_custom(win)))


def find_conflicts(custom: dict | None = None) -> dict[str, list[str]]:
    """Normalized sequence -> action ids sharing it (only real dupes)."""
    seen: dict[str, list[str]] = {}
    for action_id in action_ids():
        keys = normalize_keys(effective_keys(action_id, custom))
        if keys:
            seen.setdefault(keys, []).append(action_id)
    return {k: v for k, v in seen.items() if len(v) > 1}


def event_matches(event, sequence_text: str) -> bool:
    """Does this QKeyEvent equal a registered single-key sequence?"""
    from PySide6.QtCore import Qt

    norm = normalize_keys(sequence_text)
    if not norm:
        return False
    from PySide6.QtGui import QKeySequence

    try:
        combo = QKeySequence(norm)[0]
    except Exception:  # noqa: BLE001
        return False
    try:
        want_mods = combo.keyboardModifiers()
    except Exception:  # noqa: BLE001
        return False
    mask = (Qt.KeyboardModifier.ShiftModifier | Qt.KeyboardModifier.ControlModifier
            | Qt.KeyboardModifier.AltModifier | Qt.KeyboardModifier.MetaModifier)
    try:
        if event.isAutoRepeat():
            return False
    except Exception:  # noqa: BLE001
        pass
    try:
        return event.key() == combo.key() and (event.modifiers() & mask) == (want_mods & mask)
    except Exception:  # noqa: BLE001
        return False


def event_to_text(event) -> str:
    """PortableText for a QKeyEvent (editor capture), "" if unusable."""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QKeySequence

    try:
        if event.isAutoRepeat():
            return ""
    except Exception:  # noqa: BLE001
        pass
    try:
        mods = event.modifiers()
        parts = []
        if mods & Qt.KeyboardModifier.ControlModifier:
            parts.append("Ctrl")
        if mods & Qt.KeyboardModifier.ShiftModifier:
            parts.append("Shift")
        if mods & Qt.KeyboardModifier.AltModifier:
            parts.append("Alt")
        if mods & Qt.KeyboardModifier.MetaModifier:
            parts.append("Meta")
        key_text = QKeySequence(int(event.key())).toString(
            QKeySequence.SequenceFormat.PortableText)
        if not key_text:
            return ""
        parts.append(key_text)
        return normalize_keys("+".join(parts))
    except Exception:  # noqa: BLE001
        return ""


def apply_shortcuts(win, custom: dict | None = None) -> None:
    """Push effective sequences into registered QAction/QShortcut objects.

    Widgets register as win._shortcut_actions[action_id] = [objects].
    With no map given, the window's stored overrides apply; an explicit
    map is stored on the window first (editor path).
    """
    if custom is None:
        custom = current_custom(win)
    else:
        try:
            win._shortcuts_custom = dict(custom)
        except Exception:  # noqa: BLE001
            pass
    registry = getattr(win, "_shortcut_actions", None) or {}
    for action_id, objects in registry.items():
        keys = normalize_keys(effective_keys(action_id, custom))
        for obj in list(objects or []):
            try:
                if hasattr(obj, "setShortcuts"):
                    obj.setShortcuts([keys] if keys else [])
                elif hasattr(obj, "setShortcut"):
                    obj.setShortcut(keys)
                elif hasattr(obj, "setKey"):
                    obj.setKey(keys)
            except Exception:  # noqa: BLE001
                continue


__all__ = ["ACTIONS", "FILENAME", "action_ids", "action_label",
           "apply_shortcuts", "default_keys", "effective_keys",
           "event_matches", "event_to_text", "find_conflicts",
           "load_custom", "normalize_keys", "reset_custom", "save_custom"]
