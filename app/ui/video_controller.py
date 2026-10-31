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
    """FPS retimes the player; particle modes also re-render (pad depends on fps)."""
    try:
        fps = win._anim_combo_int(win.cmb_video_fps, 8, 2, 60)
        win._video_timer.setInterval(max(1, 1000 // fps))
    except Exception:  # noqa: BLE001
        pass
    try:
        mode = str(win.cmb_video_mode.currentText())
    except Exception:  # noqa: BLE001
        mode = ""
    if mode in ("dissolve", "morph"):
        # Holds/pads are baked per fps: re-render to keep the sacred total.
        try:
            win._schedule_refresh()
            return
        except Exception:  # noqa: BLE001
            pass
    sync_duration_ui(win)
    # NOTE: non-particle modes intentionally skip re-render here (was a full
    # re-render of N canvas-size frames on every fps tick).


def duration_seconds(win) -> float:
    """Sacred total clip length (Length spin, seconds)."""
    try:
        return max(0.5, min(60.0, float(win.spn_duration.value())))
    except Exception:  # noqa: BLE001
        return 5.0


def planned_total(win) -> dict:
    """Mirror of gif.plan_dissolve for honest UI (no render).

    Returns dict(n_trans, hs, he, pad, total, capped, actual_s, target_s,
    fps, segs, particle). Non-particle modes report plain frames/fps.
    """
    from app.gif import plan_dissolve

    try:
        mode = str(win.cmb_video_mode.currentText())
    except Exception:  # noqa: BLE001
        mode = "both"
    try:
        n_req = int(win._anim_combo_int(win.cmb_video_frames, 6, 2, 64))
        fps = max(1, int(win._anim_combo_int(win.cmb_video_fps, 8, 2, 60)))
        hold = max(0.0, min(3.0, float(win.sld_dissolve_hold.value()) / 10.0))
        target = max(0.5, min(60.0, float(win.spn_duration.value())))
    except Exception:  # noqa: BLE001
        return {"n_trans": 6, "hs": 0, "he": 0, "pad": 0, "total": 6,
                "capped": False, "actual_s": 1.0, "target_s": 5.0,
                "fps": 8, "segs": 1, "particle": False}
    if mode not in ("dissolve", "morph"):
        return {"n_trans": n_req, "hs": 0, "he": 0, "pad": 0, "total": n_req,
                "capped": False, "actual_s": n_req / fps,
                "target_s": n_req / fps, "fps": fps, "segs": 1, "particle": False}
    try:
        from app.ui import params_controller as _par

        segs = max(1, len(_par.morph_chain_data(win))) if mode == "morph" else 1
    except Exception:  # noqa: BLE001
        segs = 1
    plan = plan_dissolve(n_req, segs, fps, hold, target)
    plan.update({"target_s": target, "fps": fps, "segs": segs, "particle": True})
    return plan


def duration_changed(win) -> None:
    """Length spin edited: target total changed, just re-render."""
    sync_duration_ui(win)
    try:
        win._schedule_refresh()
    except Exception:  # noqa: BLE001
        pass


def sync_duration_ui(win) -> None:
    """Refresh the duration label: sacred target vs actual built total."""
    try:
        plan = planned_total(win)
        n_eff = plan["total"]
        pp = bool(win.chk_video_pingpong.isChecked())
        if pp and n_eff > 2:
            n_eff = n_eff + (n_eff - 2)
        fps = plan["fps"]
        if plan["particle"]:
            actual = n_eff / max(1, fps)
            target = plan["target_s"]
            if abs(actual - target) < 0.05 and not plan["capped"]:
                text = f"= {actual:.1f}s total"
            elif plan["capped"]:
                text = f"= {actual:.1f}s total (target {target:.1f}s — capped)"
            else:
                text = f"= {actual:.1f}s total (target {target:.1f}s — content overflows, raise Length)"
            if plan["hs"] + plan["he"] > 0:
                text += f" · {(plan['hs'] + plan['he']) / max(1, fps):.1f}s hold"
        else:
            secs = plan["actual_s"]
            text = f"= {secs:.1f}s loop"
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
        if plan.get("particle"):
            try:
                per_seg = plan["n_trans"] / max(1, plan["segs"])
                if per_seg < 8 or per_seg / max(1, plan["fps"]) < 0.8:
                    text += (f" · {per_seg:.0f}f/{per_seg / max(1, plan['fps']):.1f}s per form"
                             " — raise Length for slower morphs")
            except Exception:  # noqa: BLE001
                pass
        # Weight estimate at document size (export cost, not proxy).
        try:
            from app.gif import estimate_gif
            from app.ui import params_controller as _par

            w, h = _par.doc_dims(win)
            weight_mb = estimate_gif(n_eff, w, h) / 1_000_000.0
            if plan.get("actual_s", 0) > 4.0 or weight_mb > 25.0:
                text += f" · ~{weight_mb:.0f}MB GIF est. · prefer MP4"
            elif weight_mb > 10.0:
                text += f" · ~{weight_mb:.0f}MB GIF est."
        except Exception:  # noqa: BLE001
            if plan.get("actual_s", 0) > 4.0:
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
