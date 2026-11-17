"""Clip controller: session-only clip store + timeline scrub + play.

The canvas always shows the clip dithered through the live preset
(what you see is what the Export window renders). Batch stays
stills-only; the clip never touches presets.
"""

from __future__ import annotations


def has_clip(win) -> bool:
    return bool(getattr(win, "_clip_frames", []))


def clip_fps(win) -> int:
    """Playback/export fps: session clip rate, clamped 2–60."""
    try:
        from app.clip import _clamp_fps

        return _clamp_fps(dict(getattr(win, "_clip_info", {}) or {}).get("fps", 24))
    except Exception:  # noqa: BLE001
        return 24


def motion_source(win) -> str:
    """Selected Motion source: "clip" only when its radio is checked."""
    try:
        if bool(win.rb_motion_clip.isChecked()):
            return "clip"
    except Exception:  # noqa: BLE001
        pass
    return "still"


def set_motion_source(win, which: str) -> None:
    """Show one Motion source; the other stops writing the canvas.

    Opening a clip selects footage; enabling procedural motion selects
    the still. Timers of the deselected side stop, so the canvas has a
    single writer again.
    """
    which = "clip" if str(which) == "clip" else "still"
    for attr, on in (("rb_motion_still", which == "still"),
                     ("rb_motion_clip", which == "clip")):
        try:
            w = getattr(win, attr)
            w.blockSignals(True)
            w.setChecked(on)
            w.blockSignals(False)
        except Exception:  # noqa: BLE001
            pass
    for attr, on in (("_motion_still_box", which == "still"),
                     ("_motion_clip_box", which == "clip")):
        try:
            getattr(win, attr).setVisible(on)
        except Exception:  # noqa: BLE001
            pass
    if which == "clip":
        try:
            from app.ui import video_controller as _vc

            _vc.pause(win)
        except Exception:  # noqa: BLE001
            pass
        if has_clip(win):
            try:
                scrub(win, int(win.sld_clip.value()))
            except Exception:  # noqa: BLE001
                scrub(win, 0)
    else:
        stop(win)
        try:
            win.refresh()
        except Exception:  # noqa: BLE001
            pass
    try:
        from app.ui import envelope_controller as _env

        _env.sync_envelope_source(win)
    except Exception:  # noqa: BLE001
        pass


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


STRIP_MAX_THUMBS = 10


def strip_indices(n: int, max_thumbs: int = STRIP_MAX_THUMBS) -> list[int]:
    """Evenly spaced frame indices for the filmstrip (pure, pinned).

    Always includes 0 and the last frame; short clips show every frame.
    """
    try:
        total = max(0, int(n))
        cap = max(1, int(max_thumbs))
    except (TypeError, ValueError):
        return []
    if total <= 0:
        return []
    if total <= cap:
        return list(range(total))
    return sorted({round(i * (total - 1) / (cap - 1)) for i in range(cap)})


def build_strip(win) -> None:
    """Filmstrip under the scrub row: raw proxy thumbs, click to jump.

    Thumbs are source pixels (no dither cost); the dithered canvas still
    lands async on arrival. Rebuilt on open (frames are import-fixed).
    """
    try:
        from PySide6.QtCore import QSize
        from PySide6.QtGui import QIcon
        from PySide6.QtWidgets import QPushButton

        from app.ui.qt_image import pil_to_pixmap
    except Exception:  # noqa: BLE001
        return
    try:
        box = getattr(win, "_clip_strip", None)
        lay = box.layout() if box is not None else None
        if box is None or lay is None:
            return
        while lay.count():
            item = lay.takeAt(0)
            try:
                w = item.widget()
                if w is not None:
                    w.deleteLater()
            except Exception:  # noqa: BLE001
                pass
        frames = list(getattr(win, "_clip_frames", []) or [])
        btns: list = []
        for i in strip_indices(len(frames)):
            try:
                pm = pil_to_pixmap(frames[i], max_side=48)
                b = QPushButton()
                b.setIcon(QIcon(pm))
                b.setIconSize(pm.size().boundedTo(QSize(36, 28)))
                b.setFixedSize(42, 34)
                b.setFlat(True)
                b.setToolTip(f"Frame {i + 1}/{len(frames)}")
                b.clicked.connect(lambda _c=False, j=i: scrub(win, int(j)))
                lay.addWidget(b)
                btns.append((b, int(i)))
            except Exception:  # noqa: BLE001
                continue
        lay.addStretch()
        win._clip_thumb_btns = btns
    except Exception:  # noqa: BLE001
        pass
    try:
        highlight_strip(win, int(getattr(win, "_clip_start", 0) or 0))
    except Exception:  # noqa: BLE001
        pass


def clear_strip(win) -> None:
    """Drop the filmstrip (close clip)."""
    try:
        box = getattr(win, "_clip_strip", None)
        lay = box.layout() if box is not None else None
        if lay is not None:
            while lay.count():
                item = lay.takeAt(0)
                try:
                    w = item.widget()
                    if w is not None:
                        w.deleteLater()
                except Exception:  # noqa: BLE001
                    pass
        win._clip_thumb_btns = []
    except Exception:  # noqa: BLE001
        pass


def highlight_strip(win, idx: int) -> None:
    """Amber frame on the thumb nearest the canvas (cheap, sync)."""
    try:
        btns = list(getattr(win, "_clip_thumb_btns", []) or [])
        if not btns:
            return
        best = min(btns, key=lambda bj: abs(int(bj[1]) - int(idx)))[1]
        for b, j in btns:
            try:
                b.setStyleSheet(
                    "border: 2px solid #F5A623; border-radius: 2px;"
                    if int(j) == int(best) else "")
            except Exception:  # noqa: BLE001
                pass
    except Exception:  # noqa: BLE001
        pass


def open_dialog(win) -> None:
    from PySide6.QtWidgets import QFileDialog

    from app.clip import CLIP_EXTS

    filt = "Clips (*%s)" % " *".join(CLIP_EXTS)
    path, _ = QFileDialog.getOpenFileName(win, "Open clip", "", filt)
    if path:
        open_path(win, path)


def open_path(win, path) -> bool:
    from pathlib import Path

    from PySide6.QtWidgets import QMessageBox

    from app.clip import VideoBackendMissing, import_clip

    try:
        start_s = max(0.0, float(win.spn_clip_start_s.value()))
    except Exception:  # noqa: BLE001
        start_s = 0.0
    _busy(win, True, "Importing clip...")
    try:
        frames, info = import_clip(Path(path), start_s=start_s)
    except VideoBackendMissing as e:
        QMessageBox.warning(win, "TRAKKART", str(e))
        return False
    except Exception as e:  # noqa: BLE001
        QMessageBox.warning(win, "TRAKKART", f"Could not open clip:\n{e}")
        return False
    finally:
        _busy(win, False)
    stop(win)
    win._clip_frames = frames
    win._clip_info = info
    win._clip_start = 0
    win._clip_end = len(frames) - 1
    win._clip_audio = ""
    # New clip = new pixels: a stale cache keyed by frame index would
    # show the previous clip's frames when the recipe is unchanged.
    try:
        if isinstance(getattr(win, "_clip_dither_cache", None), dict):
            win._clip_dither_cache.clear()
    except Exception:  # noqa: BLE001
        pass
    build_strip(win)
    set_motion_source(win, "clip")
    sync_ui(win)
    scrub(win, 0)
    try:
        trunc = " · truncated to 120f" if info.get("truncated") else ""
        start_tag = f" · from {info.get('start_s', 0.0):.1f}s" if info.get("start_s") else ""
        win._status(f"Clip: {Path(path).name} · {len(frames)}f"
                    f" @{info.get('fps', 24)}fps{start_tag}{trunc} (proxy 720p)")
    except Exception:  # noqa: BLE001
        pass
    return True


def close_clip(win) -> None:
    stop(win)
    clear_strip(win)
    win._clip_frames = []
    win._clip_info = {}
    win._clip_start = 0
    win._clip_end = -1
    win._clip_audio = ""
    try:
        cache = getattr(win, "_clip_dither_cache", None)
        if isinstance(cache, dict):
            cache.clear()
    except Exception:  # noqa: BLE001
        pass
    set_motion_source(win, "still")
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
    """Scrub target: slider + title follow now, dithered pixels async.

    The dithered canvas no longer blocks on ED recipes: a cache hit
    paints sync, otherwise `request_clip_frame` renders in thread and
    the canvas lands on arrival (latest token wins, playback coalesces).
    """
    frames = getattr(win, "_clip_frames", []) or []
    if not frames:
        return
    i = max(0, min(len(frames) - 1, int(idx)))
    n = len(frames)
    try:
        if int(win.sld_clip.value()) != i:
            win.sld_clip.blockSignals(True)
            win.sld_clip.setValue(i)
            win.sld_clip.blockSignals(False)
    except Exception:  # noqa: BLE001
        pass
    try:
        src = frames[i]
        win.lbl_res_title.setText(
            f"MOTION · {src.width}×{src.height} · f{i + 1}/{n} (clip)")
        win.lbl_clip_pos.setText(f"{i + 1}/{n}")
    except Exception:  # noqa: BLE001
        pass
    highlight_strip(win, i)
    request_clip_frame(win, i)


def _paint_clip_frame(win, image, idx: int) -> None:
    """Blit a dithered frame (GUI thread only)."""
    try:
        from app.ui.preview_canvas import PREVIEW_MAX_SIDE
        from app.ui.qt_image import pil_to_pixmap

        win.lbl_res.set_wipe_mode(False)
        win.lbl_res.setPixmap(pil_to_pixmap(image, max_side=PREVIEW_MAX_SIDE))
        n = len(getattr(win, "_clip_frames", []) or [])
        win.lbl_res_title.setText(
            f"MOTION · {image.width}×{image.height} · f{idx + 1}/{max(1, n)} (clip)")
    except Exception:  # noqa: BLE001
        pass


def _worker_running(win) -> bool:
    try:
        w = getattr(win, "_clip_worker", None)
        return bool(w is not None and callable(getattr(w, "isRunning", None)) and w.isRunning())
    except Exception:  # noqa: BLE001
        return False


def request_clip_frame(win, idx: int) -> str:
    """Paint frame `idx`: cache hit sync, else one in-flight render.

    Returns "hit" | "launched" | "coalesced" | "empty". Rapid scrubbing
    only moves `win._clip_pending`; the done slot drains it, so the GUI
    thread never queues renders and an ED recipe degrades to
    slow-motion instead of a freeze.
    """
    frames = list(getattr(win, "_clip_frames", []) or [])
    if not frames:
        return "empty"
    i = max(0, min(len(frames) - 1, int(idx)))
    try:
        key = _recipe_key(win)
    except Exception:  # noqa: BLE001
        key = None
    try:
        cache = getattr(win, "_clip_dither_cache", None)
        if not isinstance(cache, dict):
            cache = {}
            win._clip_dither_cache = cache
        hit = cache.get(i)
        if hit is not None and hit[0] == key:
            _paint_clip_frame(win, hit[1], i)
            return "hit"
    except Exception:  # noqa: BLE001
        pass
    win._clip_pending = i
    if _worker_running(win):
        return "coalesced"
    return _launch_clip_frame(win, i, key)


def _launch_clip_frame(win, idx: int, key) -> str:
    """Start the worker for `idx` (GUI thread; snapshot inputs first)."""
    from app.ui.preview_worker import ClipFrameWorker
    from app.ui import thread_safe as _ts

    frames = list(getattr(win, "_clip_frames", []) or [])
    if not frames:
        return "empty"
    i = max(0, min(len(frames) - 1, int(idx)))
    try:
        preset = win.current_params()
    except Exception:  # noqa: BLE001
        return "empty"
    try:
        env = dict(getattr(win, "_envelopes", {}) or {})
    except Exception:  # noqa: BLE001
        env = {}
    try:
        src = frames[i].copy()
    except Exception:  # noqa: BLE001
        return "empty"
    _ts.retire(getattr(win, "_clip_worker", None))
    win._clip_token = int(getattr(win, "_clip_token", 0) or 0) + 1
    worker = ClipFrameWorker(src, preset, i, len(frames), key,
                             win._clip_token, envelopes=env, parent=win)
    win._clip_worker = worker
    try:
        worker.finished_ok.connect(
            lambda image, j, k, t: _on_clip_frame_done(win, image, j, k, t))
        worker.finished_err.connect(
            lambda msg, j, t: _on_clip_frame_error(win, msg, j, t))
    except Exception:  # noqa: BLE001
        pass
    try:
        worker.start()
    except Exception:  # noqa: BLE001
        return "empty"
    return "launched"


def _wanted_index(win) -> int | None:
    try:
        return int(win.sld_clip.value())
    except Exception:  # noqa: BLE001
        return None


def _on_clip_frame_done(win, image, idx: int, key, token: int) -> None:
    """Worker arrival (GUI thread): cache always, paint when current."""
    try:
        if int(token) != int(getattr(win, "_clip_token", 0) or 0):
            return  # superseded: never paint stale pixels
    except Exception:  # noqa: BLE001
        return
    try:
        cache = getattr(win, "_clip_dither_cache", None)
        if not isinstance(cache, dict):
            cache = {}
            win._clip_dither_cache = cache
        cache[int(idx)] = (key, image)
        if len(cache) > max(8, len(getattr(win, "_clip_frames", []) or []) + 1):
            cache.pop(next(iter(cache)))
    except Exception:  # noqa: BLE001
        pass
    try:
        if _wanted_index(win) == int(idx):
            _paint_clip_frame(win, image, int(idx))
    except Exception:  # noqa: BLE001
        pass
    try:
        nxt = getattr(win, "_clip_pending", None)
        win._clip_pending = None
        if nxt is not None and int(nxt) != int(idx) and has_clip(win):
            request_clip_frame(win, int(nxt))
    except Exception:  # noqa: BLE001
        pass


def _on_clip_frame_error(win, msg: str, idx: int, token: int) -> None:
    """Worker failure (GUI thread): report once, drain pending."""
    try:
        if int(token) != int(getattr(win, "_clip_token", 0) or 0):
            return
    except Exception:  # noqa: BLE001
        return
    try:
        win._status(f"Clip preview error: {msg}")
    except Exception:  # noqa: BLE001
        pass
    try:
        nxt = getattr(win, "_clip_pending", None)
        win._clip_pending = None
        if nxt is not None and has_clip(win):
            request_clip_frame(win, int(nxt))
    except Exception:  # noqa: BLE001
        pass


def playpause(win) -> None:
    """Toggle trim-range playback (dithered, no audio in-app)."""
    if not has_clip(win):
        return
    try:
        from app.ui import video_controller as _vc

        _vc.pause(win)
    except Exception:  # noqa: BLE001
        pass
    set_motion_source(win, "clip")
    playing = not bool(getattr(win, "_clip_playing", False))
    win._clip_playing = playing
    try:
        win.btn_clip_play.setText("Pause" if playing else "Play")
    except Exception:  # noqa: BLE001
        pass
    timer = getattr(win, "_clip_timer", None)
    if playing and timer is not None:
        try:
            timer.setInterval(max(33, 1000 // max(1, clip_fps(win))))
            if not timer.isActive():
                timer.start()
        except Exception:  # noqa: BLE001
            pass
    elif timer is not None:
        try:
            timer.stop()
        except Exception:  # noqa: BLE001
            pass


def next_frame(win) -> None:
    """Timer tick: advance within the trim range, loop at the end."""
    if not bool(getattr(win, "_clip_playing", False)):
        return
    if not has_clip(win):
        stop(win)
        return
    n = len(win._clip_frames)
    try:
        s = max(0, min(n - 1, int(win._clip_start)))
        e = max(0, min(n - 1, int(win._clip_end)))
    except Exception:  # noqa: BLE001
        s, e = 0, n - 1
    try:
        cur = int(win.sld_clip.value())
    except Exception:  # noqa: BLE001
        cur = s
    nxt = cur + 1 if cur < e else s
    scrub(win, nxt)


def stop(win) -> None:
    win._clip_playing = False
    try:
        # A late arrival must never paint over the stopped state.
        win._clip_token = int(getattr(win, "_clip_token", 0) or 0) + 1
        win._clip_pending = None
    except Exception:  # noqa: BLE001
        pass
    try:
        from app.ui import thread_safe as _ts

        _ts.retire(getattr(win, "_clip_worker", None))
        win._clip_worker = None
    except Exception:  # noqa: BLE001
        pass
    try:
        timer = getattr(win, "_clip_timer", None)
        if timer is not None:
            timer.stop()
    except Exception:  # noqa: BLE001
        pass
    try:
        win.btn_clip_play.setText("Play")
    except Exception:  # noqa: BLE001
        pass


def _busy(win, on: bool, msg: str = "") -> None:
    """Cursor + status for the synchronous import/export (no worker yet)."""
    from PySide6.QtWidgets import QApplication

    try:
        if on:
            from PySide6.QtCore import Qt

            win.setCursor(Qt.WaitCursor)
            if msg:
                win._status(msg)
        else:
            win.unsetCursor()
        QApplication.processEvents()
    except Exception:  # noqa: BLE001
        pass


def _replace(src, dst) -> None:
    """Move an export into place (Windows-safe over an existing file)."""
    from pathlib import Path

    s, d = Path(src), Path(dst)
    d.parent.mkdir(parents=True, exist_ok=True)
    try:
        d.unlink(missing_ok=True)
    except OSError:
        pass
    s.replace(d)


def _recipe_key(win):
    """Current preset recipe fingerprint (cache key; None = unknown).

    Session envelopes ride along: a curve change must invalidate the
    cache exactly like a preset change (same pixels rule as export).
    """
    try:
        preset = win.current_params() if hasattr(win, "current_params") else None
        meta = preset.meta() if preset is not None and hasattr(preset, "meta") else None
    except Exception:  # noqa: BLE001
        return None
    try:
        import json

        from app.envelopes import envelopes_signature

        env = envelopes_signature(getattr(win, "_envelopes", {}) or {})
        return json.dumps(meta, sort_keys=True, default=str) + "|env=" + env
    except (TypeError, ValueError):
        return None


def dithered_frame(win, idx: int):
    """Frame `idx` through the live preset (cached per recipe; sync).

    Session envelopes apply here exactly like in export: preview ==
    pixels. The async path (`request_clip_frame`) shares the pixels
    via `render_clip_frame`; this stays sync for tests and fallback.
    """
    from app.ui.preview_worker import render_clip_frame

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
    try:
        env = dict(getattr(win, "_envelopes", {}) or {})
    except Exception:  # noqa: BLE001
        env = {}
    out = render_clip_frame(frames[i], preset, i, n, env)
    cache[i] = (key, out)
    # Session cap: trimmed range at most (proxy RAM, no hoard).
    if len(cache) > max(8, n + 1):
        cache.pop(next(iter(cache)))
    return out


def note_preset_changed(win) -> None:
    """Refresh hook: stale dither cache drops, live frame re-renders async.

    Called at the top of refresh(); cheap when no clip (one hasattr).
    The re-render coalesces: an ED recipe no longer freezes the slider
    that changed it.
    """
    if not has_clip(win):
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
    request_clip_frame(win, cur)


def sync_info(win) -> None:
    try:
        from app.clip import clip_duration

        info = dict(getattr(win, "_clip_info", {}) or {})
        n = len(getattr(win, "_clip_frames", []) or [])
        s = int(win.spn_clip_start.value())
        e = int(win.spn_clip_end.value())
        fps = _export_fps(win)
        name = __import__("pathlib").Path(str(info.get("path", "clip"))).name
        trunc = " · capped at 120f" if info.get("truncated") else ""
        start_tag = f" · from {info.get('start_s', 0.0):.1f}s" if info.get("start_s") else ""
        span = max(0, e - s + 1)
        win.lbl_clip_info.setText(
            f"{name} · {n}f @{info.get('fps', 24)}fps{start_tag} · trim {s}-{e}"
            f" (= {clip_duration(span, fps):.1f}s @ {fps}fps){trunc} · 720p proxy")
    except Exception:  # noqa: BLE001
        pass


def sync_ui(win) -> None:
    on = has_clip(win)
    n = len(getattr(win, "_clip_frames", []) or [])
    for attr in ("btn_clip_close", "spn_clip_start", "spn_clip_end",
                 "sld_clip", "btn_clip_play"):
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


def _export_fps(win, fps: int | None = None) -> int:
    """Clip fps for export/playback: explicit value wins, then session rate."""
    if fps is not None:
        try:
            return max(2, min(60, int(fps)))
        except (TypeError, ValueError):
            pass
    try:
        return max(2, min(60, int(win.spn_clip_fps.value())))
    except Exception:  # noqa: BLE001
        pass
    return clip_fps(win)


def pick_audio(win) -> None:
    from PySide6.QtWidgets import QFileDialog

    path, _ = QFileDialog.getOpenFileName(
        win, "Soundtrack (MP4 only, optional)",
        "", "Audio (*.mp3 *.wav *.ogg *.m4a *.flac *.aac)")
    if path:
        win._clip_audio = str(path)
        try:
            win.txt_clip_audio.setText(str(path))
            win._status(f"Soundtrack: {__import__('pathlib').Path(path).name} (MP4 mux)")
        except Exception:  # noqa: BLE001
            pass


def clear_audio(win) -> None:
    win._clip_audio = ""
    try:
        win.txt_clip_audio.setText("")
        win._status("Soundtrack cleared (MP4 will be silent)")
    except Exception:  # noqa: BLE001
        pass


def _clip_base(win) -> str:
    from app.exporter import sanitize_base

    try:
        stem = __import__("pathlib").Path(
            str(dict(getattr(win, "_clip_info", {}) or {}).get("path", "clip"))).stem
    except Exception:  # noqa: BLE001
        stem = "clip"
    return sanitize_base(stem or "clip")


def _free_path(path):
    """First free name (`base`, `base_2`, `base_3`…) — never overwrite."""
    from pathlib import Path

    p = Path(path)
    if not p.exists():
        return p
    for n in range(2, 1000):
        cand = p.with_name(f"{p.stem}_{n}{p.suffix}")
        if not cand.exists():
            return cand
    return p


def clip_names(base: str) -> dict:
    """Export filenames per kind for a base (dialog plan + collisions)."""
    return {"gif": f"{base}_clip.gif", "zip": f"{base}_frames.zip",
            "mp4": f"{base}_clip.mp4"}


def render_clip_export_long(win, preset, fps: int, out, track: str = "",
                            res: str = "proxy", quality: int = 8):
    """Full-length MP4 from the source file (streaming, O(window) RAM).

    From the session in-point (`_clip_info.start_s`) to the source end,
    capped at 3600f. Same pixels as a full-RAM render over the range
    (global seeds/progress + session envelopes). Trim spins do not apply
    (they drive the 120f preview + short exports); the dialog says so.
    `res` = "proxy" (720p, light) or "source" (native ≤1920, heavy);
    `quality` = imageio 0-10 q. Muxes `track` like the short path
    (video copied, never re-encoded).
    """
    from pathlib import Path

    from app.clip import (CLIP_PROXY_SIDE, CLIP_SOURCE_SIDE,
                          clip_full_length, iter_dither_source, mux_soundtrack)

    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        info = dict(getattr(win, "_clip_info", {}) or {})
        src = str(info.get("path", "") or "")
        start_s = float(info.get("start_s", 0.0) or 0.0)
    except Exception:  # noqa: BLE001
        src, start_s = "", 0.0
    if not src or not Path(src).is_file():
        raise ValueError("Clip source missing (re-open the clip)")
    try:
        env = dict(getattr(win, "_envelopes", {}) or {})
    except Exception:  # noqa: BLE001
        env = {}
    try:
        q = max(0, min(10, int(quality)))
    except (TypeError, ValueError):
        q = 8
    side = CLIP_SOURCE_SIDE if str(res or "proxy").lower() == "source" else CLIP_PROXY_SIDE
    plan = clip_full_length(src, start_s)
    stream = iter_dither_source(src, preset, plan["start_s"],
                                total_hint=plan["total_frames"],
                                proxy_side=side,
                                envelopes=env)
    from app.video_io import write_mp4_iter

    silent = out.parent / f"{out.stem}_silent.mp4"
    try:
        _wrote, n = write_mp4_iter(stream, silent, fps=fps, quality=q)
    except Exception:
        try:
            silent.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    track = str(track or "").strip()
    if track and Path(track).is_file():
        try:
            mux_soundtrack(silent, track, out)
        except Exception as mux_exc:  # noqa: BLE001
            _replace(silent, out)
            raise RuntimeError(
                f"soundtrack failed ({mux_exc}); exported silent"
            ) from mux_exc
        finally:
            try:
                silent.unlink(missing_ok=True)
            except OSError:
                pass
    else:
        _replace(silent, out)
    try:
        win._status(f"Clip full-length MP4: {out.name} ({n}f @{fps}fps, streaming)")
    except Exception:  # noqa: BLE001
        pass
    return out


def render_clip_export(win, kind: str, preset, span: list, fps: int,
                       out, track: str = "", res: str = "proxy",
                       quality: int = 8):
    """Render one clip export (no dialogs; raises on error). Returns the path.

    `out` is the exact destination; callers own the naming policy
    (panel: first-free `_free_path`; Export window: dialog base+rename).
    Envelopes come from the session (`win._envelopes`, drift+grain).
    `res`/`quality` only affect MP4: "source" re-decodes the trim window
    at native size (no proxy upscale); GIF/ZIP stay proxy by design.
    """
    from pathlib import Path

    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if not list(span or []):
        raise ValueError("Empty trim range.")
    try:
        env = dict(getattr(win, "_envelopes", {}) or {})
    except Exception:  # noqa: BLE001
        env = {}
    if kind == "gif":
        from app.clip import dither_clip
        from app.gif import save_gif

        return save_gif(dither_clip(list(span), preset, envelopes=env), out, fps=fps)
    if kind == "zip":
        from app.clip import dither_clip, save_clip_zip

        return save_clip_zip(dither_clip(list(span), preset, envelopes=env), out)
    if kind == "mp4":
        from app.clip import (CLIP_SOURCE_SIDE,
                              iter_dither_clip, iter_dither_trim_source,
                              mux_soundtrack, write_clip_mp4)

        try:
            q = max(0, min(10, int(quality)))
        except (TypeError, ValueError):
            q = 8
        silent = out.parent / f"{out.stem}_silent.mp4"
        try:
            if str(res or "proxy").lower() == "source":
                try:
                    info = dict(getattr(win, "_clip_info", {}) or {})
                    src = str(info.get("path", "") or "")
                    start_s = float(info.get("start_s", 0.0) or 0.0)
                except Exception:  # noqa: BLE001
                    src, start_s = "", 0.0
                try:
                    skip = int(win._clip_start)
                except Exception:  # noqa: BLE001
                    skip = 0
                if src and Path(src).is_file():
                    stream = iter_dither_trim_source(
                        src, preset, start_s, skip, len(list(span)),
                        CLIP_SOURCE_SIDE, 300, env)
                    write_clip_mp4(stream, silent, fps=fps, quality=q)
                else:
                    write_clip_mp4(iter_dither_clip(list(span), preset, envelopes=env),
                                   silent, fps=fps, quality=q)
            else:
                write_clip_mp4(iter_dither_clip(list(span), preset, envelopes=env),
                               silent, fps=fps, quality=q)
        except Exception:
            # No half-written MP4 left behind (ffmpeg failure).
            try:
                silent.unlink(missing_ok=True)
            except OSError:
                pass
            raise
        track = str(track or "").strip()
        if track and Path(track).is_file():
            try:
                mux_soundtrack(silent, track, out)
            except Exception as mux_exc:  # noqa: BLE001
                # Never lose the encoded video because the track
                # failed: fall back to the silent export.
                _replace(silent, out)
                raise RuntimeError(
                    f"soundtrack failed ({mux_exc}); exported silent"
                ) from mux_exc
            finally:
                try:
                    silent.unlink(missing_ok=True)
                except OSError:
                    pass
        else:
            _replace(silent, out)
        return out
    raise ValueError(f"Unknown clip export: {kind}")


def export_clip(win, kind: str, fps: int | None = None, track: str | None = None,
                base: str | None = None, out_dir=None):
    """Session-clip export: silent GIF, frame ZIP, MP4 (+track when set).

    Panel path (explicit args are for the Export window): dialogs here,
    render in `render_clip_export`. Batch stays stills-only: this path
    never touches batch_flow. Returns the written path (None on cancel).
    """
    from pathlib import Path

    from PySide6.QtWidgets import QMessageBox

    if not has_clip(win):
        QMessageBox.information(win, "TRAKKART", "Open a clip first.")
        return None
    span = trimmed(win)
    if not span:
        QMessageBox.information(win, "TRAKKART", "Empty trim range.")
        return None
    fps = _export_fps(win, fps)
    base = base or _clip_base(win)
    out_dir = Path(out_dir if out_dir is not None else getattr(win, "out_dir", "."))
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        preset = win.current_params()
    except Exception as e:  # noqa: BLE001
        QMessageBox.warning(win, "TRAKKART", f"Export error: {e}")
        return None
    if track is None:
        track = str(getattr(win, "_clip_audio", "") or "").strip()
    try:
        _busy(win, True, f"Exporting clip ({kind})... {len(span)}f @{fps}fps")
        try:
            out = _free_path(out_dir / clip_names(base)[kind])
            render_clip_export(win, kind, preset, span, fps, out, track)
        finally:
            _busy(win, False)
    except KeyError:
        QMessageBox.warning(win, "TRAKKART", f"Unknown clip export: {kind}")
        return None
    except Exception as e:  # noqa: BLE001
        try:
            from app.video_io import VideoBackendMissing

            if isinstance(e, VideoBackendMissing):
                QMessageBox.warning(win, "TRAKKART", str(e))
                return None
        except ImportError:
            pass
        QMessageBox.warning(win, "TRAKKART", f"Clip export error: {e}")
        return None
    try:
        win._status(f"Clip {kind} exported: {out.name} ({len(span)}f @{fps}fps)")
    except Exception:  # noqa: BLE001
        pass
    return out


__all__ = ["has_clip", "clip_fps", "motion_source", "set_motion_source",
           "trimmed", "open_dialog", "open_path", "close_clip",
           "set_range", "scrub", "show_frame", "playpause",
           "next_frame", "stop", "sync_info", "sync_ui",
           "dithered_frame", "note_preset_changed",
           "request_clip_frame", "strip_indices",
           "build_strip", "clear_strip", "highlight_strip",
           "pick_audio", "clear_audio", "clip_names", "render_clip_export",
           "render_clip_export_long", "export_clip"]
