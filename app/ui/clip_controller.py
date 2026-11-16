"""Clip controller (v2.0 Fase A): session-only clip store + timeline scrub.

Source-only preview (no dither yet — Fase B reuses render_spec per
frame). Batch stays stills-only; the clip never touches presets.
"""

from __future__ import annotations


def has_clip(win) -> bool:
    return bool(getattr(win, "_clip_frames", []))


def trimmed(win) -> list:
    frames = list(getattr(win, "_clip_frames", []) or [])
    if not frames:
        return []
    try:
        s = int(getattr(win, "spn_clip_start", None).value())
    except Exception:  # noqa: BLE001
        s = 0
    try:
        e = int(getattr(win, "spn_clip_end", None).value())
    except Exception:  # noqa: BLE001
        e = len(frames) - 1
    s = max(0, min(len(frames) - 1, s))
    e = max(0, min(len(frames) - 1, e))
    if s > e:
        return []
    return frames[s:e + 1]


def open_dialog(win) -> None:
    from PySide6.QtWidgets import QFileDialog

    path, _ = QFileDialog.getOpenFileName(
        win, "Open clip", "", "Clips (*.mp4 *.gif *.webp)")
    if path:
        open_path(win, path)


def open_path(win, path) -> bool:
    from pathlib import Path

    from PySide6.QtWidgets import QMessageBox

    from app.clip import VideoBackendMissing, import_clip

    try:
        frames, info = import_clip(Path(path))
    except VideoBackendMissing as e:
        QMessageBox.warning(win, "TRAKKART", str(e))
        return False
    except Exception as e:  # noqa: BLE001
        QMessageBox.warning(win, "TRAKKART", f"Could not open clip:\n{e}")
        return False
    win._clip_frames = frames
    win._clip_info = info
    win._clip_start = 0
    win._clip_end = len(frames) - 1
    sync_ui(win)
    scrub(win, 0)
    try:
        trunc = " · truncated to 120f" if info.get("truncated") else ""
        win._status(f"Clip: {Path(path).name} · {len(frames)}f"
                    f" @{info.get('fps', 24)}fps{trunc} (proxy 720p)")
    except Exception:  # noqa: BLE001
        pass
    return True


def close_clip(win) -> None:
    win._clip_frames = []
    win._clip_info = {}
    win._clip_start = 0
    win._clip_end = -1
    sync_ui(win)
    try:
        win._status("Clip closed (session-only, stills untouched)")
    except Exception:  # noqa: BLE001
        pass


def set_range(win) -> None:
    if not has_clip(win):
        return
    n = len(win._clip_frames)
    try:
        s = max(0, min(n - 1, int(win.spn_clip_start.value())))
        e = max(0, min(n - 1, int(win.spn_clip_end.value())))
    except Exception:  # noqa: BLE001
        return
    if s > e:
        e = s
        try:
            win.spn_clip_end.blockSignals(True)
            win.spn_clip_end.setValue(e)
        finally:
            win.spn_clip_end.blockSignals(False)
    win._clip_start, win._clip_end = s, e
    try:
        win.sld_clip.blockSignals(True)
        win.sld_clip.setRange(s, e)
        win.sld_clip.setValue(max(s, min(e, int(win.sld_clip.value()) or s)))
    finally:
        win.sld_clip.blockSignals(False)
    scrub(win, int(win.sld_clip.value()))
    sync_info(win)


def scrub(win, idx: int) -> None:
    if not has_clip(win):
        return
    n = len(win._clip_frames)
    try:
        s = max(0, min(n - 1, int(win.spn_clip_start.value())))
        e = max(0, min(n - 1, int(win.spn_clip_end.value())))
    except Exception:  # noqa: BLE001
        s, e = 0, n - 1
    i = max(s, min(e, int(idx)))
    show_frame(win, i)


def show_frame(win, idx: int) -> None:
    frames = getattr(win, "_clip_frames", []) or []
    if not frames:
        return
    i = max(0, min(len(frames) - 1, int(idx)))
    frame = frames[i]
    tag = "proxy"
    if _dither_on(win):
        try:
            frame = dithered_frame(win, i)
            tag = "dithered"
        except Exception:  # noqa: BLE001
            frame = frames[i]
    try:
        from app.ui.preview_canvas import PREVIEW_MAX_SIDE
        from app.ui.qt_image import pil_to_pixmap

        win.lbl_res.set_wipe_mode(False)
        win.lbl_res.setPixmap(pil_to_pixmap(frame, max_side=PREVIEW_MAX_SIDE))
        win.lbl_res_title.setText(
            f"CLIP · {frame.width}x{frame.height} · f{i + 1}/{len(frames)} ({tag})")
        win.lbl_clip_pos.setText(f"{i + 1}/{len(frames)}")
    except Exception:  # noqa: BLE001
        pass
    try:
        if int(win.sld_clip.value()) != i:
            win.sld_clip.blockSignals(True)
            win.sld_clip.setValue(i)
            win.sld_clip.blockSignals(False)
    except Exception:  # noqa: BLE001
        pass


def _dither_on(win) -> bool:
    try:
        return bool(win.chk_clip_dither.isChecked())
    except Exception:  # noqa: BLE001
        return False


def _recipe_key(win):
    """Current preset recipe fingerprint (cache key; None = unknown)."""
    try:
        preset = win.current_params() if hasattr(win, "current_params") else None
        meta = preset.meta() if preset is not None and hasattr(preset, "meta") else None
    except Exception:  # noqa: BLE001
        return None
    try:
        import json

        return json.dumps(meta, sort_keys=True, default=str)
    except (TypeError, ValueError):
        return None


def dithered_frame(win, idx: int):
    """Frame `idx` through the live preset (cached per recipe; sync)."""
    from app.clip import _spec_for
    from app.pipeline import render_spec

    frames = list(getattr(win, "_clip_frames", []) or [])
    i = max(0, min(len(frames) - 1, int(idx)))
    key = _recipe_key(win)
    cache = getattr(win, "_clip_dither_cache", None)
    if not isinstance(cache, dict):
        cache = {}
        win._clip_dither_cache = cache
    hit = cache.get(i)
    if hit is not None and hit[0] == key:
        return hit[1]
    n = len(frames)
    try:
        preset = win.current_params()
    except Exception:  # noqa: BLE001
        return frames[i]
    out = render_spec(frames[i].convert("RGB"), _spec_for(preset, i, n))
    cache[i] = (key, out)
    # Session cap: trimmed range at most (proxy RAM, no hoard).
    if len(cache) > max(8, n + 1):
        cache.pop(next(iter(cache)))
    return out


def toggle_dither(win) -> None:
    if _dither_on(win):
        cache = getattr(win, "_clip_dither_cache", None)
        if isinstance(cache, dict):
            cache.clear()
    try:
        cur = int(win.sld_clip.value())
    except Exception:  # noqa: BLE001
        cur = int(getattr(win, "_clip_start", 0) or 0)
    show_frame(win, cur)


def note_preset_changed(win) -> None:
    """Refresh hook: stale dither cache drops, live frame re-renders.

    Called at the top of refresh(); cheap when no clip (one hasattr).
    """
    if not has_clip(win) or not _dither_on(win):
        return
    cache = getattr(win, "_clip_dither_cache", None)
    key = _recipe_key(win)
    keys = [v[0] for v in cache.values()] if isinstance(cache, dict) else []
    if keys and all(k == key for k in keys):
        return  # recipe untouched: cache stays
    if isinstance(cache, dict):
        cache.clear()
    try:
        cur = int(win.sld_clip.value())
    except Exception:  # noqa: BLE001
        return
    show_frame(win, cur)


def sync_info(win) -> None:
    try:
        info = dict(getattr(win, "_clip_info", {}) or {})
        n = len(getattr(win, "_clip_frames", []) or [])
        s = int(win.spn_clip_start.value())
        e = int(win.spn_clip_end.value())
        name = __import__("pathlib").Path(str(info.get("path", "clip"))).name
        trunc = " · capped at 120f" if info.get("truncated") else ""
        win.lbl_clip_info.setText(
            f"{name} · {n}f @{info.get('fps', 24)}fps · trim {s}-{e}{trunc} · 720p proxy")
    except Exception:  # noqa: BLE001
        pass


def sync_ui(win) -> None:
    on = has_clip(win)
    n = len(getattr(win, "_clip_frames", []) or [])
    for attr in ("btn_clip_close", "spn_clip_start", "spn_clip_end", "sld_clip",
                 "chk_clip_dither"):
        try:
            getattr(win, attr).setEnabled(on)
        except Exception:  # noqa: BLE001
            pass
    if on:
        try:
            for spn in (win.spn_clip_start, win.spn_clip_end):
                spn.blockSignals(True)
                spn.setRange(0, max(0, n - 1))
            win.spn_clip_start.setValue(0)
            win.spn_clip_end.setValue(max(0, n - 1))
            for spn in (win.spn_clip_start, win.spn_clip_end):
                spn.blockSignals(False)
            win.sld_clip.blockSignals(True)
            win.sld_clip.setRange(0, max(0, n - 1))
            win.sld_clip.setValue(0)
            win.sld_clip.blockSignals(False)
        except Exception:  # noqa: BLE001
            pass
    else:
        try:
            win.lbl_clip_info.setText("No clip (session-only, ≤120f · 720p proxy)")
            win.lbl_clip_pos.setText("–")
        except Exception:  # noqa: BLE001
            pass
        return
    sync_info(win)


__all__ = ["has_clip", "trimmed", "open_dialog", "open_path", "close_clip",
           "set_range", "scrub", "show_frame", "sync_info", "sync_ui",
           "dithered_frame", "toggle_dither", "note_preset_changed"]
