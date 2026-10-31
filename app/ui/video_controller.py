"""Video-mode controller: animated full-canvas preview + playback.

State (`_video_on/_playing/_frames/_idx/_worker/_token`) and the widgets
stay on MainWindow; this module holds the behavior. The window keeps the
same `window._on_video_*` / `window._show_video_frame` API by delegation.

Perf note: changing FPS only retimes the player (no re-render). A full
re-render at canvas size costs seconds, so `fps_changed` must never
schedule one.
"""

from __future__ import annotations


# Preview-only resolution (video-proxy style): long side per tier.
# Export ALWAYS renders the full document, whatever the preview uses.
PROXY_SIDES = {"Draft 720p": 720, "HD 1080p": 1080}


def proxy_size(win) -> int:
    """Long side for preview (0 = full doc). Never affects export."""
    try:
        return int(PROXY_SIDES.get(str(win.cmb_video_proxy.currentText()), 0) or 0)
    except Exception:  # noqa: BLE001
        return 0


def preview_size(win) -> int:
    side = proxy_size(win)
    if side > 0:
        return side
    return int(win._gif_anim_size())


def spec(win) -> dict:
    return {"size": preview_size(win), "mode": win._gif_anim_mode(),
            "frames": win._gif_anim_frames(), "fps": win._gif_anim_fps(),
            "pingpong": win._gif_anim_pingpong()}


def proxy_changed(win) -> None:
    """Switching proxy re-renders (cheap in Draft/HD)."""
    win._schedule_refresh()


def _morph_imgs(win) -> list | None:
    """Chain entries (with per-image crop) for morph preview (None = dissolve)."""
    try:
        from app.ui import params_controller as _par

        chain = _par.morph_chain_data(win)
        if chain:
            return chain
        single = getattr(win, "morph_src", None)
        return [single] if single is not None else None
    except Exception:  # noqa: BLE001
        return None


def toggle(win) -> None:
    win._video_on = bool(win.chk_video.isChecked())
    win._video_bar_widget.setVisible(win._video_on)
    if win._video_on:
        win._video_playing = True
        try:
            win.btn_video_play.setText("⏸ Pause")
        except Exception:  # noqa: BLE001
            pass
    else:
        win._video_timer.stop()
    win.refresh()


def fps_changed(win) -> None:
    """FPS only retimes the player: no re-render (canvas renders are costly)."""
    try:
        fps = win._anim_combo_int(win.cmb_video_fps, 8, 2, 60)
        win._video_timer.setInterval(max(1, 1000 // fps))
    except Exception:  # noqa: BLE001
        pass
    sync_duration_ui(win)
    # NOTE: intentionally no _schedule_refresh() here (was a full re-render
    # of N canvas-size frames on every fps tick).


def duration_seconds(win) -> float:
    """Current loop length = frames / fps (derived, never stored)."""
    try:
        frames = win._anim_combo_int(win.cmb_video_frames, 6, 2, 64)
        fps = win._anim_combo_int(win.cmb_video_fps, 8, 2, 60)
        return frames / max(1, fps)
    except Exception:  # noqa: BLE001
        return 0.0


def _dissolve_hold_frames(win, fps: int) -> tuple[int, int]:
    """End holds from the MORPH Hold slider (0 if mode is not particle)."""
    try:
        mode = str(win.cmb_video_mode.currentText())
    except Exception:  # noqa: BLE001
        return 0, 0
    if mode not in ("dissolve", "morph"):
        return 0, 0
    try:
        hold_s = max(0.0, min(3.0, float(win.sld_dissolve_hold.value()) / 10.0))
    except Exception:  # noqa: BLE001
        return 0, 0
    total = int(round(hold_s * max(1, int(fps))))
    hs = total // 2
    return hs, total - hs


def effective_frames(win) -> int:
    """Playback length accounting ping-pong expansion (6 -> 10) + holds."""
    try:
        n = int(win._anim_combo_int(win.cmb_video_frames, 6, 2, 64))
        pp = bool(win.chk_video_pingpong.isChecked())
        fps = int(win._anim_combo_int(win.cmb_video_fps, 8, 2, 60))
    except Exception:  # noqa: BLE001
        return 6
    hs, he = _dissolve_hold_frames(win, fps)
    room = 64 - n
    if hs + he > room and room >= 0:
        hs = min(hs, room // 2)
        he = min(he, room - hs)
    n += hs + he
    if pp and n > 2:
        return n + (n - 2)
    return n


def set_duration(win, seconds: float) -> None:
    """Length edit -> frames (fps stays): seconds * fps, clamped 2-64."""
    try:
        from app.gif import GIF_MAX_FRAMES, GIF_MIN_FRAMES
    except Exception:  # noqa: BLE001
        return
    try:
        fps = win._anim_combo_int(win.cmb_video_fps, 8, 2, 60)
        want = int(round(float(seconds) * max(1, fps)))
        want = max(GIF_MIN_FRAMES, min(GIF_MAX_FRAMES, want))
        win._set_anim_combo(win.cmb_video_frames, want)
    except Exception:  # noqa: BLE001
        pass


def duration_changed(win) -> None:
    """Length spin edited: push to frames and re-render (frame count changed)."""
    try:
        set_duration(win, float(win.spn_duration.value()))
    except Exception:  # noqa: BLE001
        pass
    sync_duration_ui(win)
    try:
        win._schedule_refresh()
    except Exception:  # noqa: BLE001
        pass


def sync_duration_ui(win) -> None:
    """Refresh length controls from frames / fps + weight hint."""
    try:
        secs = duration_seconds(win)
        n_eff = effective_frames(win)
        # Keep the spin in sync without signal loops.
        try:
            spn = win.spn_duration
            spn.blockSignals(True)
            if abs(float(spn.value()) - secs) > 0.05:
                spn.setValue(round(secs, 1))
        finally:
            try:
                win.spn_duration.blockSignals(False)
            except Exception:  # noqa: BLE001
                pass
        text = f"= {secs:.1f}s loop"
        try:
            fps = int(win._anim_combo_int(win.cmb_video_fps, 8, 2, 60))
            hs, he = _dissolve_hold_frames(win, fps)
            if hs + he > 0:
                hold_s = (hs + he) / max(1, fps)
                text += f" + {hold_s:.1f}s hold"
        except Exception:  # noqa: BLE001
            pass
        # Strict-mode hint: mix/glitch with every FX/DATAMOSH channel at 0
        # only does march+hue (no forced slices).
        try:
            mode = str(win.cmb_video_mode.currentText())
            if mode in ("glitch", "mix"):
                from app.ui import params_controller as _par

                cur = _par.build_params(win) if hasattr(_par, "build_params") else None

                def _val(name, default=0):
                    try:
                        if isinstance(cur, dict):
                            return cur.get(name, default)
                        return getattr(cur, name, default)
                    except Exception:  # noqa: BLE001
                        return default

                try:
                    bands = int(_val("glitch_slice_bands", 0) or 0)
                except (TypeError, ValueError):
                    bands = 0
                glitch_on = any([
                    float(_val("glitch_chroma", 0) or 0) > 0,
                    bands >= 2 and float(_val("glitch_slice_max", 0) or 0) > 0,
                    float(_val("wave", 0) or 0) > 0,
                    float(_val("mosh", 0.0) or 0.0) > 0,
                    float(_val("grain", 0.0) or 0.0) > 0,
                    float(_val("dust", 0.0) or 0.0) > 0,
                ])
                if not glitch_on:
                    text += " · mix sin FX/DATAMOSH: sube valores"
        except Exception:  # noqa: BLE001
            pass
        # Weight estimate at document size (export cost, not proxy).
        try:
            from app.gif import estimate_gif
            from app.ui import params_controller as _par

            w, h = _par.doc_dims(win)
            weight_mb = estimate_gif(n_eff, w, h) / 1_000_000.0
            if secs > 4.0 or weight_mb > 25.0:
                text += f" · ~{weight_mb:.0f}MB GIF est. · prefer MP4"
            elif weight_mb > 10.0:
                text += f" · ~{weight_mb:.0f}MB GIF est."
        except Exception:  # noqa: BLE001
            if secs > 4.0:
                text += " · prefer MP4"
        win.lbl_duration.setText(text)
    except Exception:  # noqa: BLE001
        pass


def playpause(win) -> None:
    win._video_playing = not win._video_playing
    try:
        win.btn_video_play.setText("⏸ Pause" if win._video_playing else "▶ Play")
    except Exception:  # noqa: BLE001
        pass
    if win._video_playing and win._video_frames and not win._video_timer.isActive():
        win._video_timer.start()


def scrub(win, v: int) -> None:
    if not win._video_on or not win._video_frames:
        return
    win._video_idx = max(0, min(len(win._video_frames) - 1, int(v)))
    show_frame(win)


def start_async(win) -> None:
    from app.ui.preview_worker import VideoWorker

    if win.src is None:
        return
    if win._video_worker is not None and win._video_worker.isRunning():
        return  # one in flight is enough; debounce will retry
    s = spec(win)
    win._video_token += 1
    win._video_timer.stop()
    win._status(f"Rendering video {s['frames']}f {s['mode']} @{s['size']}px…")
    win._video_worker = VideoWorker(
        win.src.copy(), win.current_params(), s["size"],
        s["frames"], s["mode"], s["pingpong"], win._video_token,
        morph_src=_morph_imgs(win), fps=int(s.get("fps", 8)),
    )
    win._video_worker.finished_ok.connect(win._on_video_done)
    win._video_worker.finished_err.connect(win._on_video_error)
    win._video_worker.start()


def on_done(win, frames: list, token: int) -> None:
    if token != win._video_token:
        return
    from app.gif import GIF_MAX_FPS, GIF_MIN_FPS

    win._video_frames = list(frames or [])
    win.result = win._video_frames[0] if win._video_frames else win.result
    s = spec(win)
    fps = max(GIF_MIN_FPS, min(GIF_MAX_FPS, int(s["fps"])))
    win._video_timer.setInterval(1000 // fps)
    win.sld_video.blockSignals(True)
    win.sld_video.setRange(0, max(0, len(win._video_frames) - 1))
    win.sld_video.setValue(0)
    win.sld_video.blockSignals(False)
    win._video_idx = 0
    show_frame(win)
    if win._video_playing and len(win._video_frames) > 1:
        win._video_timer.start()
    win._status(f"Video ready: {len(win._video_frames)}f "
                f"{s['mode']} @{win.result.width}x{win.result.height}")


def on_error(win, msg: str, token: int) -> None:
    if token != win._video_token:
        return
    win._status(f"Video error: {msg}")


def show_frame(win, force: bool = False) -> None:
    if not win._video_frames:
        return
    if win._comparing and not force:
        win._paint_compare_orig()
        return
    from app.ui.qt_image import pil_to_pixmap

    idx = max(0, min(len(win._video_frames) - 1, int(win._video_idx)))
    frame = win._video_frames[idx]
    zoomed = int(520 * win.zoom)
    win.lbl_res.setPixmap(pil_to_pixmap(frame, max_side=zoomed))
    win.lbl_res_title.setText(f"VIDEO · {frame.width}x{frame.height} · f{idx + 1}/{len(win._video_frames)}")
    win.lbl_video_pos.setText(f"{idx + 1}/{len(win._video_frames)}")
    if win.sld_video.value() != idx:
        win.sld_video.blockSignals(True)
        win.sld_video.setValue(idx)
        win.sld_video.blockSignals(False)


def next_frame(win) -> None:
    if not win._video_on or not win._video_playing or not win._video_frames:
        return
    win._video_idx = (win._video_idx + 1) % len(win._video_frames)
    show_frame(win)
