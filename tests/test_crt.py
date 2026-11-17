"""Pins for v2.x #5: temporal CRT/VHS motion modes (GIF mode "crt").

Scanline roll + tracking wobble + chroma bleed over time, reusing the
march/hue engine: march crawls on ordered methods (frozen on ED like
phase), each temporal channel only runs on its FX value (strict 0=off).
Everything deterministic and loop-perfect (progress 1 == progress 0).
"""

from __future__ import annotations

from PIL import Image


def _img(w: int = 96, h: int = 96):
    im = Image.new("RGB", (w, h))
    px = im.load()
    for y in range(h):
        for x in range(w):
            px[x, y] = ((x * 5) % 256, (y * 5) % 256, ((x + y) * 3) % 256)
    return im


def _flat(frames):
    return [tuple(f.get_flattened_data()) for f in frames]


def _crt_base(**kw):
    from app.presets import Preset

    base = dict(name="c", method="bayer8", palette="SLIME", scanlines=4,
                glitch_chroma=4, glitch_slice_bands=4, glitch_slice_max=12)
    base.update(kw)
    return Preset(**base)


def test_crt_deterministic_and_moving():
    from app.gif import gif_frames

    im = _img()
    a = _flat(gif_frames(im, _crt_base(), frames=6, mode="crt"))
    b = _flat(gif_frames(im, _crt_base(), frames=6, mode="crt"))
    assert a == b
    assert len(set(a)) > 1


def test_crt_ed_clean_static_but_fx_moves():
    from app.gif import gif_frames

    im = _img()
    clean = _flat(gif_frames(
        im, _crt_base(method="floyd", scanlines=0, glitch_chroma=0,
                      glitch_slice_bands=0, glitch_slice_max=0),
        frames=4, mode="crt"))
    assert len(set(clean)) == 1  # march frozen on ED, no FX -> honest still
    fx = _flat(gif_frames(im, _crt_base(method="floyd"), frames=4, mode="crt"))
    assert len(set(fx)) > 1  # roll/tracking/bleed move on every method


def test_crt_no_forced_wobble_matches_phase():
    from app.gif import gif_frames

    im = _img()
    preset = _crt_base(scanlines=0, glitch_chroma=0, glitch_slice_bands=0,
                       glitch_slice_max=0)
    crt = _flat(gif_frames(im, preset, frames=4, mode="crt"))
    phase = _flat(gif_frames(im, preset, frames=4, mode="phase"))
    assert crt == phase  # FX at 0: march only, nothing forced


def test_crt_motion_zero_freezes():
    from app.gif import gif_frames

    im = _img()
    still = _flat(gif_frames(im, _crt_base(motion_amount=0.0),
                             frames=4, mode="crt"))
    assert len(set(still)) == 1


def test_scanlines_roll_loops_and_matches_static():
    from app.fx import apply_scanlines, scanlines_roll

    im = _img()
    assert (list(scanlines_roll(im, 4, 0.0).get_flattened_data())
            == list(apply_scanlines(im, 4).get_flattened_data()))
    assert (list(scanlines_roll(im, 4, 1.0).get_flattened_data())
            == list(scanlines_roll(im, 4, 0.0).get_flattened_data()))
    mid = list(scanlines_roll(im, 4, 0.5).get_flattened_data())
    assert mid != list(apply_scanlines(im, 4).get_flattened_data())
    assert scanlines_roll(im, 0, 0.5) is im
    assert scanlines_roll(im, 1, 0.5) is im


def test_tracking_wobble_loops_and_off():
    from app.glitch import tracking_wobble

    im = _img()
    assert (list(tracking_wobble(im, 8, 1.0).get_flattened_data())
            == list(tracking_wobble(im, 8, 0.0).get_flattened_data()))
    assert (list(tracking_wobble(im, 8, 0.25).get_flattened_data())
            != list(im.get_flattened_data()))
    assert tracking_wobble(im, 0, 0.5) is im
    assert tracking_wobble(im, -3, 0.5) is im


def test_crt_mode_registered():
    from app.gif import GIF_MODES, mode_desc, mode_label

    assert "crt" in GIF_MODES
    assert mode_label("crt") == "CRT drift"
    assert "frozen on error-diffusion" in mode_desc("crt")
