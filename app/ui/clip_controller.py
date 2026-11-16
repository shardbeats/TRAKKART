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

    _busy(win, True, "Importing clip...")
    try:
        frames, info = import_clip(Path(path))
    except VideoBackendMissing as e:
        QMessageBox.warning(win, "TRAKKART", str(e))
        return False
    except Exception as e:  # noqa: BLE001
        QMessageBox.warning(win, "TRAKKART", f"Could not open clip:\n{e}")
        return False
    finally:
        _busy(win, False)
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
    try:
        win.txt_clip_audio.setText("")
        win.spn_clip_fps.setValue(max(2, min(60, int(info.get("fps", 24)))))
    except Exception:  # noqa: BLE001
        pass
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
    win._clip_audio = ""
    try:
        win.txt_clip_audio.setText("")
        cache = getattr(win, "_clip_dither_cache", None)
        if isinstance(cache, dict):
            cache.clear()
    except Exception:  # noqa: BLE001
        pass
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
        from app.clip import clip_duration

        info = dict(getattr(win, "_clip_info", {}) or {})
        n = len(getattr(win, "_clip_frames", []) or [])
        s = int(win.spn_clip_start.value())
        e = int(win.spn_clip_end.value())
        fps = _export_fps(win)
        name = __import__("pathlib").Path(str(info.get("path", "clip"))).name
        trunc = " · capped at 120f" if info.get("truncated") else ""
        span = max(0, e - s + 1)
        win.lbl_clip_info.setText(
            f"{name} · {n}f @{info.get('fps', 24)}fps · trim {s}-{e}"
            f" (= {clip_duration(span, fps):.1f}s @ {fps}fps){trunc} · 720p proxy")
    except Exception:  # noqa: BLE001
        pass


def sync_ui(win) -> None:
    on = has_clip(win)
    n = len(getattr(win, "_clip_frames", []) or [])
    for attr in ("btn_clip_close", "spn_clip_start", "spn_clip_end", "sld_clip",
                 "chk_clip_dither", "txt_clip_audio", "btn_clip_audio",
                 "btn_clip_audio_clear", "spn_clip_fps", "btn_clip_gif",
                 "btn_clip_zip", "btn_clip_mp4"):
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


def _export_fps(win) -> int:
    try:
        return max(2, min(60, int(win.spn_clip_fps.value())))
    except Exception:  # noqa: BLE001
        pass
    try:
        return max(2, min(60, int(dict(getattr(win, "_clip_info", {}) or {}).get("fps", 24))))
    except Exception:  # noqa: BLE001
        return 24


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


def export_clip(win, kind: str) -> None:
    """Session-clip export: silent GIF, frame ZIP, MP4 (+track when set).

    Batch stays stills-only: this path never touches batch_flow.
    """
    from pathlib import Path

    from PySide6.QtWidgets import QMessageBox

    if not has_clip(win):
        QMessageBox.information(win, "TRAKKART", "Open a clip first.")
        return
    span = trimmed(win)
    if not span:
        QMessageBox.information(win, "TRAKKART", "Empty trim range.")
        return
    fps = _export_fps(win)
    base = _clip_base(win)
    out_dir = Path(getattr(win, "out_dir", "."))
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        preset = win.current_params()
    except Exception as e:  # noqa: BLE001
        QMessageBox.warning(win, "TRAKKART", f"Export error: {e}")
        return
    try:
        from app.clip import dither_clip, iter_dither_clip

        _busy(win, True, f"Exporting clip ({kind})... {len(span)}f @{fps}fps")
        try:
            if kind == "gif":
                from app.gif import save_gif

                out = _free_path(out_dir / f"{base}_clip.gif")
                save_gif(dither_clip(span, preset), out, fps=fps)
            elif kind == "zip":
                from app.clip import save_clip_zip

                out = _free_path(out_dir / f"{base}_frames.zip")
                save_clip_zip(dither_clip(span, preset), out)
            elif kind == "mp4":
                from app.clip import mux_soundtrack, write_clip_mp4

                out = _free_path(out_dir / f"{base}_clip.mp4")
                silent = out_dir / f"{out.stem}_silent.mp4"
                try:
                    write_clip_mp4(iter_dither_clip(span, preset), silent, fps=fps)
                except Exception:
                    # No half-written MP4 left behind (ffmpeg failure).
                    try:
                        silent.unlink(missing_ok=True)
                    except OSError:
                        pass
                    raise
                track = str(getattr(win, "_clip_audio", "") or "").strip()
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
            else:
                QMessageBox.warning(win, "TRAKKART", f"Unknown clip export: {kind}")
                return
        finally:
            _busy(win, False)
    except Exception as e:  # noqa: BLE001
        try:
            from app.video_io import VideoBackendMissing

            if isinstance(e, VideoBackendMissing):
                QMessageBox.warning(win, "TRAKKART", str(e))
                return
        except ImportError:
            pass
        QMessageBox.warning(win, "TRAKKART", f"Clip export error: {e}")
        return
    try:
        win._status(f"Clip {kind} exported: {out.name} ({len(span)}f @{fps}fps)")
    except Exception:  # noqa: BLE001
        pass


__all__ = ["has_clip", "trimmed", "open_dialog", "open_path", "close_clip",
           "set_range", "scrub", "show_frame", "sync_info", "sync_ui",
           "dithered_frame", "toggle_dither", "note_preset_changed",
           "pick_audio", "clear_audio", "export_clip"]
