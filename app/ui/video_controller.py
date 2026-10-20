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
# Export SIEMPRE sale al documento completo, elija lo que elija el preview.
PROXY_SIDES = {"Draft 720p": 720, "HD 1080p": 1080}


def proxy_size(win) -> int:
    """Long side para el preview (0 = doc completo). Nunca afecta al export."""
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
    """Cambiar de proxy re-renderiza (barato en Draft/HD)."""
    win._schedule_refresh()


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
    # NOTE: intentionally no _schedule_refresh() here (was a full re-render
    # of N canvas-size frames on every fps tick).


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
        return  # uno en vuelo basta; el debounce reintentará
    s = spec(win)
    win._video_token += 1
    win._video_timer.stop()
    win._status(f"Rendering video {s['frames']}f {s['mode']} @{s['size']}px…")
    win._video_worker = VideoWorker(
        win.src.copy(), win.current_params(), s["size"],
        s["frames"], s["mode"], s["pingpong"], win._video_token,
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
