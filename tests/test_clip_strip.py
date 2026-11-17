"""Pins for the clip filmstrip (P2): pure layout + UI wiring.

No threads asserted here: clicks launch the real preview worker (tiny
test GIFs, joined at teardown), while scrub/slider/highlight stay sync.
"""

from __future__ import annotations


def test_strip_indices_layout():
    from app.ui.clip_controller import STRIP_MAX_THUMBS, strip_indices

    assert strip_indices(0) == []
    assert strip_indices(-4) == []
    assert strip_indices(5) == [0, 1, 2, 3, 4]
    assert strip_indices(10) == list(range(10))
    idx = strip_indices(120)
    assert len(idx) == STRIP_MAX_THUMBS
    assert idx[0] == 0 and idx[-1] == 119
    assert idx == sorted(set(idx))


def _open_clip(window, n=6):
    from PIL import Image as Img

    from app.ui import clip_controller as cc

    gif = window.out_dir.parent / "strip.gif"
    frames = [Img.new("RGB", (48, 48), (i * 40 % 256, 30, 90)) for i in range(n)]
    frames[0].save(str(gif), save_all=True, append_images=frames[1:],
                   duration=100, loop=0)
    assert cc.open_path(window, gif) is True


def test_strip_builds_and_click_scrubs(window):
    from app.ui import clip_controller as cc

    _open_clip(window, n=6)
    btns = list(getattr(window, "_clip_thumb_btns", []) or [])
    assert [j for _, j in btns] == [0, 1, 2, 3, 4, 5]
    btns[4][0].click()
    assert int(window.sld_clip.value()) == 4
    assert window.lbl_clip_pos.text() == "5/6"
    cc.close_clip(window)
    assert list(getattr(window, "_clip_thumb_btns", []) or []) == []


def test_motion_envelope_rests_on_clip(window):
    from app.ui import clip_controller as cc

    assert window.cmb_env_motion_amount.isEnabled() is True
    _open_clip(window)
    assert cc.motion_source(window) == "clip"
    assert window.cmb_env_motion_amount.isEnabled() is False
    assert "still-motion only" in window.cmb_env_motion_amount.toolTip()
    cc.close_clip(window)
    assert cc.motion_source(window) == "still"
    assert window.cmb_env_motion_amount.isEnabled() is True


def test_open_path_resets_stale_start_instead_of_warning(window, monkeypatch):
    # Stale "start at" from a longer clip: load from 0 + reset spinner,
    # no modal (owner nov-2026).
    from PIL import Image as Img
    from PySide6.QtWidgets import QMessageBox

    from app.ui import clip_controller as cc

    gif = window.out_dir.parent / "short.gif"
    frames = [Img.new("RGB", (48, 48), (i * 40 % 256, 30, 90)) for i in range(4)]
    frames[0].save(str(gif), save_all=True, append_images=frames[1:],
                   duration=250, loop=0)  # 4f @4fps = 1.0s of footage
    window.spn_clip_start_s.setValue(220.0)

    def _no_warning(*a, **k):
        raise AssertionError("no warning dialog expected")

    monkeypatch.setattr(QMessageBox, "warning", _no_warning)
    assert cc.open_path(window, gif) is True
    assert float(window.spn_clip_start_s.value()) == 0.0
    assert len(window._clip_frames) == 4
    assert "reset to 0" in window.lbl_status.text()
    cc.close_clip(window)
