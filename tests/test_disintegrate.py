"""Unit tests for particle disperse (Fase 1, solo dispersion)."""

from PIL import Image


def _img(size: int = 64) -> Image.Image:
    im = Image.new("RGB", (size, size))
    px = im.load()
    for y in range(size):
        for x in range(size):
            px[x, y] = ((x * 3) % 256, (y * 3) % 256, 128)
    return im


def test_amount_zero_is_identity():
    from app.disintegrate import dissolve_frames

    a = dissolve_frames(_img(), frames=4, amount=0.0)
    assert len(a) == 4
    flats = [tuple(f.get_flattened_data()) for f in a]
    assert len(set(flats)) == 1


def test_seed_deterministic_and_modes_differ():
    from app.disintegrate import dissolve_frames

    a = dissolve_frames(_img(), frames=4, seed=7, mode="wind")
    b = dissolve_frames(_img(), frames=4, seed=7, mode="wind")
    assert [tuple(f.get_flattened_data()) for f in a] == [tuple(f.get_flattened_data()) for f in b]
    c = dissolve_frames(_img(), frames=4, seed=7, mode="random")
    assert [tuple(f.get_flattened_data()) for f in a] != [tuple(f.get_flattened_data()) for f in c]


def test_loop_assembles_and_mid_disperses():
    from app.disintegrate import dither_bw, disperse_positions, points_from_dither, render_points

    d = dither_bw(_img(48))
    coords, h, w = points_from_dither(d)
    assert len(coords) > 0
    p0 = disperse_positions(coords, h, w, progress=0.0, seed=11)
    p1 = disperse_positions(coords, h, w, progress=1.0, seed=11)
    assert (p0 == p1).all()
    f0 = render_points(p0, h, w)
    assert list(f0.get_flattened_data()) == list(d.convert("RGB").get_flattened_data())
    pmid = disperse_positions(coords, h, w, progress=0.5, seed=11)
    assert not (pmid == p0).all()


def test_gif_dissolve_frames_loop_and_export(tmp_path):
    from app.gif import gif_dissolve_frames, save_gif

    f = gif_dissolve_frames(_img(), frames=4, max_side=64)
    assert len(f) == 4
    assert len({tuple(x.get_flattened_data()) for x in f}) > 1
    out = save_gif(f, tmp_path / "d.gif", fps=8)
    assert out.exists()
    f_pp = gif_dissolve_frames(_img(), frames=4, max_side=64, pingpong=True)
    assert len(f_pp) == 6


def test_gif_dissolve_uses_dissolve_preset():
    from app.gif import gif_dissolve_frames
    from app.presets import Preset

    base = dict(name="t", method="bayer8", palette="BW", gif_size=64)
    wind = gif_dissolve_frames(_img(), Preset(**base, dissolve_mode="wind"), frames=4)
    rnd = gif_dissolve_frames(_img(), Preset(**base, dissolve_mode="random"), frames=4)
    assert [tuple(f.get_flattened_data()) for f in wind] != [tuple(f.get_flattened_data()) for f in rnd]


def test_morph_swaps_images():
    from app.disintegrate import dither_bw, morph_frames

    a = _img(48)
    b = Image.new("RGB", (48, 48), (10, 200, 90))
    frames = morph_frames(a, b, frames=6, max_side=64)
    assert len(frames) == 6
    first = tuple(frames[0].get_flattened_data())
    last = tuple(frames[-1].get_flattened_data())
    assert first == tuple(dither_bw(a).convert("RGB").get_flattened_data())
    assert first != last
    again = morph_frames(a, b, frames=6, max_side=64)
    assert [tuple(f.get_flattened_data()) for f in frames] == [tuple(f.get_flattened_data()) for f in again]


def test_gif_morph_frames_and_pingpong(tmp_path):
    from app.gif import gif_morph_frames, save_gif

    a, b = _img(), Image.new("RGB", (64, 64), (200, 40, 90))
    f = gif_morph_frames(a, b, frames=4, max_side=64)
    assert len(f) == 4
    assert len({tuple(x.get_flattened_data()) for x in f}) > 1
    assert save_gif(f, tmp_path / "m.gif", fps=8).exists()
    assert len(gif_morph_frames(a, b, frames=4, max_side=64, pingpong=True)) == 6


def test_morph_chain_up_to_six():
    from app.disintegrate import MAX_MORPH_IMAGES, morph_chain_frames

    assert MAX_MORPH_IMAGES == 6
    a = _img(48)
    b = Image.new("RGB", (48, 48), (10, 200, 90))
    c = Image.new("RGB", (48, 48), (200, 200, 10))
    f = morph_chain_frames([a, b, c], frames=6, max_side=64)
    assert len(f) == 6
    assert tuple(f[0].get_flattened_data()) != tuple(f[-1].get_flattened_data())
    again = morph_chain_frames([a, b, c], frames=6, max_side=64)
    assert [tuple(x.get_flattened_data()) for x in f] == [tuple(x.get_flattened_data()) for x in again]
    many = [a, b, c, a, b, c, a, b]
    assert len(morph_chain_frames(many, frames=8, max_side=64)) == 8
    import pytest

    with pytest.raises(ValueError):
        morph_chain_frames([a], frames=4, max_side=64)


def test_gif_morph_accepts_list():
    from app.gif import gif_morph_frames

    a = _img()
    b = Image.new("RGB", (64, 64), (10, 200, 90))
    c = Image.new("RGB", (64, 64), (200, 200, 10))
    f = gif_morph_frames(a, [b, c], frames=6, max_side=64)
    assert len(f) == 6
    assert len({tuple(x.get_flattened_data()) for x in f}) > 2


def test_gif_frames_dispatches_dissolve_and_morph():
    from app.gif import gif_frames
    from app.presets import Preset

    p = Preset(name="t", method="bayer8", palette="BW", gif_size=64, dissolve_hold=0.0,
               dissolve_length=0.0, dissolve_loop=False)
    d = gif_frames(_img(), p, frames=3, mode="dissolve")
    assert len(d) == 3
    assert len({tuple(x.get_flattened_data()) for x in d}) > 1
    b = Image.new("RGB", (64, 64), (10, 200, 90))
    m = gif_frames(_img(), p, frames=4, mode="morph", img_b=b)
    assert len(m) == 4
    assert tuple(m[0].get_flattened_data()) != tuple(m[-1].get_flattened_data())


def test_morph_joints_meet_assembled():
    from app.disintegrate import dither_bw, morph_chain_frames

    a, b = _img(48), Image.new("RGB", (48, 48), (10, 200, 90))
    f = morph_chain_frames([a, b], frames=8, max_side=64)
    assert len(f) == 8
    # last transition frame is the assembled end image (no pop at the joint)
    assert (tuple(f[-1].get_flattened_data())
            == tuple(dither_bw(b.resize((48, 48))).convert("RGB").get_flattened_data()))


def test_holds_freeze_assembled_ends():
    from app.disintegrate import dither_bw, dissolve_frames, morph_chain_frames
    from app.gif import gif_dissolve_frames, gif_morph_frames
    from app.presets import Preset

    a = _img(48)
    still = dither_bw(a).convert("RGB")
    f = dissolve_frames(a, frames=4, max_side=64, hold_start=2, hold_end=3)
    assert len(f) == 9
    assert tuple(f[0].get_flattened_data()) == tuple(still.get_flattened_data())
    assert tuple(f[-1].get_flattened_data()) == tuple(still.get_flattened_data())
    b = Image.new("RGB", (48, 48), (10, 200, 90))
    m = morph_chain_frames([a, b], frames=4, max_side=64, hold_start=2, hold_end=2)
    assert len(m) == 8
    p = Preset(name="t", method="bayer8", palette="BW", gif_size=64,
               dissolve_hold=1.0, gif_fps=8, dissolve_length=0.0)
    g = gif_dissolve_frames(_img(), p, frames=4)
    assert len(g) == 4 + 16  # 1s + 1s holds at 8fps, no pad without Length
    assert tuple(g[0].get_flattened_data()) == tuple(g[-1].get_flattened_data())
    h = gif_morph_frames(_img(), b, p, frames=4)
    assert len(h) == 4 + 16  # single pair: floor is segs*2 = 2
    q = Preset(name="t", method="bayer8", palette="BW", gif_size=64, dissolve_hold=0.0,
               dissolve_length=0.0)
    assert len(gif_dissolve_frames(_img(), q, frames=4)) == 4


def test_hold_freezes_every_chain_form():
    from app.disintegrate import dither_bw, morph_chain_frames

    a, b, c = _img(48), Image.new("RGB", (48, 48), (10, 200, 90)), Image.new("RGB", (48, 48), (200, 200, 10))
    db = dither_bw(b).convert("RGB")
    flat_b = tuple(db.get_flattened_data())
    f = morph_chain_frames([a, b, c], frames=8, max_side=64,
                           hold_start=1, hold_end=1, hold_joint=2)
    # 8 trans + 1 + 2 + 1 holds = 12; B assembled appears 4x in a row.
    assert len(f) == 12
    runs = sum(1 for x in f if tuple(x.get_flattened_data()) == flat_b)
    assert runs == 1 + 2 + 1


def test_hold_adds_time_no_pad():
    # Hold-manda: Length is derived, never padded. Hold adds still frames.
    from app.gif import gif_dissolve_frames, gif_morph_frames
    from app.presets import Preset

    p = Preset(name="t", method="bayer8", palette="BW", gif_size=64,
               dissolve_hold=1.0, gif_fps=8, dissolve_length=5.0)
    g = gif_dissolve_frames(_img(), p, frames=4)
    assert len(g) == 20  # 4 trans + 8 + 8 holds; Length ignored, not 40
    assert tuple(g[0].get_flattened_data()) == tuple(g[-1].get_flattened_data())
    b = Image.new("RGB", (64, 64), (10, 200, 90))
    m = gif_morph_frames(_img(), b, p, frames=4)
    assert len(m) == 20
    # Absurd holds are trimmed at the 256 cap (transitions win).
    big = Preset(name="t", method="bayer8", palette="BW", gif_size=64,
                 dissolve_hold=3.0, gif_fps=60, dissolve_length=32.0)
    assert len(gif_dissolve_frames(_img(), big, frames=64)) == 256


def test_hold_slider_is_alive():
    # Hilo (1): Hold 0.0/1.0/3.0 rendered identical clips under a sacred
    # Length. Now every tick adds still frames.
    from app.gif import gif_dissolve_frames
    from app.presets import Preset

    totals = []
    for hold in (0.0, 1.0, 3.0):
        p = Preset(name="t", method="bayer8", palette="BW", gif_size=64,
                   dissolve_hold=hold, gif_fps=8, dissolve_length=5.0)
        totals.append(len(gif_dissolve_frames(_img(), p, frames=4)))
    assert totals == [4, 20, 52]


def test_morph_chain_odd_canvas_uneven_pixel():
    # Regression: 546px wide canvas with pixel_size=4 (546 % 4 != 0) used
    # to raise a bare AssertionError (surfaced as empty "Video error:").
    from app.disintegrate import morph_chain_frames
    from app.gif import gif_frames
    from app.presets import Preset

    a = Image.new("RGB", (546, 720), (90, 60, 140))
    b = Image.new("RGB", (300, 900), (200, 40, 90))
    frames = morph_chain_frames([a, b], method="bayer4", pixel_size=4,
                                frames=6, max_side=720)
    assert len(frames) == 6
    p = Preset(name="t", method="bayer4", palette="BW", pixel_size=4, gif_size=720,
               dissolve_hold=0.0, dissolve_length=0.0)
    assert len(gif_frames(a, p, frames=4, mode="morph", max_side=720, img_b=[b])) == 4


def test_morph_cover_fit_no_stretch():
    from app.disintegrate import morph_chain_frames

    a = Image.new("RGB", (64, 64), (10, 10, 10))
    b = Image.new("RGB", (128, 64), (200, 40, 40))
    px = b.load()
    for y in range(64):
        for x in range(64):
            px[x, y] = (10, 10, 200)  # left half blue, right half red-ish
    f = morph_chain_frames([a, b], frames=4, max_side=64,
                           crops=[{}, {"fx": 50.0, "fy": 50.0, "zoom": 1.0}])
    assert len(f) == 4
    assert f[0].size == (64, 64)
    # Center cover of the 128-wide B keeps both colors (no stretch smear).
    mid = morph_chain_frames([a, b], frames=8, max_side=64,
                             crops=[{}, {"fx": 0.0, "fy": 50.0, "zoom": 1.0}])
    assert tuple(mid[-1].get_flattened_data()) != tuple(f[-1].get_flattened_data())


def test_morph_a_uses_canvas_framing():
    from app.disintegrate import dissolve_frames
    from app.gif import gif_dissolve_frames
    from app.presets import Preset

    wide = Image.new("RGB", (128, 64), (90, 60, 140))
    p = Preset(name="t", method="bayer8", palette="BW", gif_size=64,
               ratio="1:1", crop_mode="cover", dissolve_hold=0.0)
    f = gif_dissolve_frames(wide, p, frames=2)
    assert f[0].size == (64, 64)  # canvas 1:1, not raw 128x64 stretched
    raw = dissolve_frames(wide, frames=2, max_side=64)
    assert raw[0].size == (64, 32)  # raw fit keeps aspect
    assert tuple(f[0].get_flattened_data()) != tuple(raw[0].convert("RGB").get_flattened_data())


def test_hold_caps_gif_streams_mp4():
    from app.gif import (MAX_MP4_FRAMES, MAX_TOTAL_FRAMES, iter_dissolve_frames,
                         plan_dissolve)
    from app.presets import Preset

    p = Preset(name="t", method="bayer8", palette="BW", gif_size=64,
               dissolve_hold=3.0, gif_fps=60, dissolve_length=60.0)
    gif_plan = plan_dissolve(64, 1, 60, 3.0, 60.0)
    assert gif_plan["total"] == MAX_TOTAL_FRAMES
    assert gif_plan["capped"] is True
    # dissolve_length is ignored: explicit target behaves like None.
    assert plan_dissolve(64, 1, 60, 3.0, None) == gif_plan
    mp4_plan = plan_dissolve(64, 1, 60, 3.0, None, cap=MAX_MP4_FRAMES)
    assert mp4_plan["total"] == 64 + 360
    assert mp4_plan["capped"] is False
    # Streaming yields the full hold-heavy clip without the list (O(1) RAM).
    n = sum(1 for _ in iter_dissolve_frames(_img(), p, frames=64, cap=MAX_MP4_FRAMES))
    assert n == 424


def test_hold_for_target_solves_bpm_grid():
    # R3: target = bars*240/bpm lands on Hold; caps and overshoots report fits.
    from app.gif import hold_for_target

    hold, actual, fits = hold_for_target(64, 1, 30, 7.5)
    assert (round(hold, 2), round(actual, 2), fits) == (2.7, 7.53, True)
    hold, actual, fits = hold_for_target(64, 1, 30, 60.0)
    assert hold == 3.0 and fits is False  # Hold clamps: add Frames/chain
    hold, actual, fits = hold_for_target(64, 1, 30, 0.5)
    assert hold == 0.0 and fits is False  # transitions alone overshoot
    hold, actual, fits = hold_for_target(6, 1, 24, 4.0)
    assert abs(actual - 4.0) < 0.01 and fits is True


def test_morph_hold_shared_across_forms():
    from app.gif import gif_morph_frames, plan_dissolve
    from app.presets import Preset

    a = Image.new("RGB", (64, 64), (200, 40, 40))
    b = Image.new("RGB", (64, 64), (40, 200, 40))
    c = Image.new("RGB", (64, 64), (40, 40, 200))
    p = Preset(name="t", method="bayer8", palette="BW", gif_size=64,
               dissolve_hold=1.0, gif_fps=24, dissolve_length=5.0,
               dissolve_loop=False)
    plan = plan_dissolve(6, 2, 24, 1.0, 5.0)
    assert plan["total"] == 78  # 6 trans + 24 x 3 holds; Length ignored
    assert max(plan["holds"]) - min(plan["holds"]) <= 1
    assert sum(plan["holds"]) + plan["n_trans"] == plan["total"]
    frames = gif_morph_frames(a, [b, c], p, frames=6)
    assert len(frames) == plan["total"]
    # Every form reads assembled: the opening run is all-A, the closing
    # run is all-C, each at least its equal share (no form starved by
    # the old end-only pad). Solid colors can dither alike, so compare
    # against the engine's own assembled stills instead of A-vs-C.
    from app.disintegrate import dither_bw

    stills = [tuple(dither_bw(
        im, method=p.method, threshold=p.threshold,
        pixel_size=p.pixel_size).convert("RGB").get_flattened_data())
        for im in (a, b, c)]
    flats = [tuple(f.get_flattened_data()) for f in frames]
    assert flats[:plan["holds"][0]] == [stills[0]] * plan["holds"][0]
    assert flats[-plan["holds"][-1]:] == [stills[2]] * plan["holds"][-1]
    assert flats.count(stills[1]) >= plan["holds"][1]
    assert abs(flats.count(stills[0]) - flats.count(stills[2])) <= 2 + plan["n_trans"]


def test_morph_loop_closes_last_to_first():
    from app.gif import gif_morph_frames, plan_dissolve
    from app.disintegrate import dither_bw
    from app.presets import Preset

    a = _img(64)  # gradient reads distinct from the flat forms
    b = Image.new("RGB", (64, 64), (40, 200, 40))
    c = Image.new("RGB", (64, 64), (40, 40, 200))
    p = Preset(name="t", method="bayer8", palette="BW", gif_size=64,
               dissolve_hold=1.0, gif_fps=24, dissolve_length=5.0,
               dissolve_loop=True)
    plan = plan_dissolve(9, 2, 24, 1.0, 5.0, loop=True)
    assert plan["total"] == 81  # 9 trans + 24 x 3 holds; Length ignored
    assert len(plan["holds"]) == 4  # A-open, B, C, A-close
    assert plan["holds"][0] + plan["holds"][-1] == plan["holds"][1]
    assert sum(plan["holds"]) + plan["n_trans"] == plan["total"]
    frames = gif_morph_frames(a, [b, c], p, frames=9)
    assert len(frames) == plan["total"]
    stills = [tuple(dither_bw(
        im, method=p.method, threshold=p.threshold,
        pixel_size=p.pixel_size).convert("RGB").get_flattened_data())
        for im in (a, b, c)]
    flats = [tuple(f.get_flattened_data()) for f in frames]
    # Closed loop opens AND closes on A (no hard cut back to start).
    assert flats[:plan["holds"][0]] == [stills[0]] * plan["holds"][0]
    assert flats[-plan["holds"][-1]:] == [stills[0]] * plan["holds"][-1]
    # 3 legs x 3 frames: middle frames actually disperse (visible morph).
    assert len(set(flats)) > 3


def _coords48():
    from app.disintegrate import dither_bw, points_from_dither

    coords, h, w = points_from_dither(dither_bw(_img(48)))
    assert len(coords) > 0
    return coords, h, w


def test_f1_modes_deterministic_and_alive():
    from app.disintegrate import DISINTEGRATE_MODES, disperse_positions

    assert len(DISINTEGRATE_MODES) == 11
    coords, h, w = _coords48()
    still = coords.astype("float32")
    for mode in DISINTEGRATE_MODES:
        a = disperse_positions(coords, h, w, progress=0.3, seed=5, mode=mode)
        b = disperse_positions(coords, h, w, progress=0.3, seed=5, mode=mode)
        assert (a == b).all(), mode
        if mode != "blocks":
            assert not (a == still).all(), mode  # blocks pops, it never drifts


def test_f1_loop_perfect_every_axis():
    from app.disintegrate import (EASE_MODES, STAGGER_MODES, block_visible,
                                  disperse_positions)

    coords, h, w = _coords48()
    still = coords.astype("float32")
    for mode in ("wind", "burst", "suction", "vortex", "rain", "rise",
                 "wave", "ripple", "flow"):
        for st in STAGGER_MODES:
            for ez in EASE_MODES:
                a = disperse_positions(coords, h, w, progress=0.0, seed=5,
                                       mode=mode, stagger=st, ease=ez)
                b = disperse_positions(coords, h, w, progress=1.0, seed=5,
                                       mode=mode, stagger=st, ease=ez)
                assert (a == b).all(), (mode, st, ez)
                # Joint-pinned stagger: the loop joint is the still itself,
                # so holds never pop (this is what stagger is FOR).
                assert (a == still).all(), (mode, st, ez)
    for st in STAGGER_MODES:
        for ez in EASE_MODES:
            m0 = block_visible(coords, h, w, progress=0.0, stagger=st, ease=ez)
            m1 = block_visible(coords, h, w, progress=1.0, stagger=st, ease=ez)
            assert m0.all() and m1.all(), (st, ez)


def test_f1_legacy_byte_identical():
    from app.disintegrate import disperse_positions
    from app.gif import gif_dissolve_frames
    from app.presets import Preset

    coords, h, w = _coords48()
    old = disperse_positions(coords, h, w, progress=0.37, seed=99,
                             wind=(120.0, -40.0), mode="wind")
    new = disperse_positions(coords, h, w, progress=0.37, seed=99,
                             wind=(120.0, -40.0), mode="wind",
                             stagger="off", ease="sine", pixel_size=3)
    assert (old == new).all()
    base = dict(name="t", method="bayer8", palette="BW", gif_size=64,
                dissolve_hold=0.0, dissolve_length=0.0)
    a = gif_dissolve_frames(_img(), Preset(**base), frames=4)
    b = gif_dissolve_frames(_img(), Preset(**base, dissolve_mode="wind",
                                           dissolve_stagger="off",
                                           dissolve_ease="sine"), frames=4)
    assert [f.tobytes() for f in a] == [f.tobytes() for f in b]


def test_f1_ease_and_stagger_shape_motion():
    from app.disintegrate import disperse_positions, stagger_delays

    coords, h, w = _coords48()
    kw = dict(progress=0.3, seed=5, mode="burst")
    sine = disperse_positions(coords, h, w, ease="sine", **kw)
    cubic = disperse_positions(coords, h, w, ease="cubic", **kw)
    linear = disperse_positions(coords, h, w, ease="linear", **kw)
    assert not (sine == cubic).all()
    assert not (sine == linear).all()
    assert (stagger_delays(coords, h, w, "off") == 0).all()
    for st in ("rank", "radial", "scan", "sweep"):
        d = stagger_delays(coords, h, w, st)
        assert d.min() >= 0.0 and d.max() < 1.0 and d.max() > 0.0, st
        moved = disperse_positions(coords, h, w, stagger=st, **kw)
        assert not (moved == sine).all(), st


def test_f1_blocks_pop_schedule():
    import numpy as np

    from app.disintegrate import block_visible

    coords, h, w = _coords48()
    n = len(coords)
    m0 = block_visible(coords, h, w, progress=0.0)
    assert m0.all() and len(m0) == n
    assert block_visible(coords, h, w, progress=1.0).all()
    # Full rank coverage (one dot per bayer8 cell): the peak keeps the
    # densest cells (rank >= 0.85 -> ranks 55..63 = 9 of 64), never blank.
    grid = np.array([[(y, x) for x in range(8)] for y in range(8)]).reshape(-1, 2)
    mid = block_visible(grid, 8, 8, progress=0.5)
    assert int(mid.sum()) == 9
    assert block_visible(grid, 8, 8, progress=0.0).all()
    # Unknown names fall back to legacy behavior (wind/off/sine).
    from app.disintegrate import disperse_positions

    assert (disperse_positions(coords, h, w, progress=0.3, seed=5, mode="nope")
            == disperse_positions(coords, h, w, progress=0.3, seed=5, mode="wind")).all()
    assert (disperse_positions(coords, h, w, progress=0.3, seed=5, ease="nope")
            == disperse_positions(coords, h, w, progress=0.3, seed=5, ease="sine")).all()


def test_f1_preset_roundtrip_and_old_defaults():
    from app.presets import Preset, load_preset, save_preset

    import tempfile
    from pathlib import Path

    p = Preset(name="F1", dissolve_mode="vortex", dissolve_stagger="sweep",
               dissolve_ease="linear")
    p.validate()
    with tempfile.TemporaryDirectory() as d:
        back = load_preset(save_preset(p, Path(d)).stem, Path(d))
        assert (back.dissolve_mode, back.dissolve_stagger, back.dissolve_ease) == \
            ("vortex", "sweep", "linear")
    old = Preset.from_dict({"name": "old", "method": "bayer4"})
    assert (old.dissolve_mode, old.dissolve_stagger, old.dissolve_ease) == \
        ("wind", "off", "sine")
    import pytest

    with pytest.raises(ValueError):
        Preset(name="x", dissolve_mode="nope").validate()
    with pytest.raises(ValueError):
        Preset(name="x", dissolve_ease="springy").validate()
    Preset(name="x", dissolve_ease="elastic").validate()  # F2
    with pytest.raises(ValueError):
        Preset(name="x", dissolve_dotsize=9).validate()
    Preset(name="x", dissolve_dotsize=3).validate()  # F2


def test_f1_blocks_morph_ends_assembled():
    from app.disintegrate import dither_bw, morph_chain_frames

    a = _img(48)
    b = Image.new("RGB", (48, 48), (10, 200, 90))
    f = morph_chain_frames([a, b], frames=8, max_side=64, mode="blocks", loop=False)
    assert len(f) == 8
    stills = [tuple(dither_bw(im).convert("RGB").get_flattened_data()) for im in (a, b)]
    assert tuple(f[0].get_flattened_data()) == stills[0]
    assert tuple(f[-1].get_flattened_data()) == stills[1]
    assert len({tuple(x.get_flattened_data()) for x in f}) > 2


def test_f2_elastic_bounce_close_and_shape():
    import numpy as np

    from app.disintegrate import EASE_MODES, disperse_positions, ease_env

    assert set(EASE_MODES) == {"sine", "cubic", "linear", "elastic", "bounce"}
    coords, h, w = _coords48()
    for ez in ("elastic", "bounce"):
        a = disperse_positions(coords, h, w, progress=0.25, seed=5, mode="burst", ease=ez)
        b = disperse_positions(coords, h, w, progress=0.25, seed=5, mode="burst", ease=ez)
        assert (a == b).all(), ez
        s = disperse_positions(coords, h, w, progress=0.25, seed=5, mode="burst", ease="sine")
        assert not (a == s).all(), ez
    v = ease_env(np.linspace(0.0, 1.0, 1001), "elastic")
    assert float(v.max()) <= 1.0 and abs(float(v[0])) < 1e-12 and abs(float(v[-1])) < 1e-12
    v = ease_env(np.linspace(0.0, 1.0, 1001), "bounce")
    assert float(v.max()) <= 1.0 and abs(float(v[0])) < 1e-12 and abs(float(v[-1])) < 1e-12


def test_f2_dotsize_swell_and_joints():
    import numpy as np

    from app.disintegrate import dot_sizes, frame_dot_sizes, render_points
    from app.gif import gif_dissolve_frames
    from app.presets import Preset

    assert dot_sizes([0.0, 0.5, 1.0], 1) is None
    assert list(dot_sizes([0.0, 0.5, 1.0], 3)) == [1, 2, 3]
    # Isolated dot renders kxk blacks.
    one = render_points(np.array([[10.0, 10.0]]), 32, 32, np.array([3]))
    assert int((np.asarray(one.convert("L")) == 0).sum()) == 9
    base = dict(name="t", method="bayer8", palette="BW", gif_size=64,
                dissolve_hold=0.0, dissolve_length=0.0)
    a = gif_dissolve_frames(_img(), Preset(**base), frames=4)
    b = gif_dissolve_frames(_img(), Preset(**base, dissolve_dotsize=3), frames=4)
    assert a[0].tobytes() == b[0].tobytes()  # joints land back at 1px
    assert a[2].tobytes() != b[2].tobytes()  # mid swells
    coords, h, w = _coords48()
    assert frame_dot_sizes(coords, h, w, progress=0.3, dotsize=1) is None


def test_f2_preset_pack():
    import tempfile
    from pathlib import Path

    from app.presets import ensure_bundled, load_preset

    with tempfile.TemporaryDirectory() as d:
        ensure_bundled(Path(d))
        ember = load_preset("EMBER_RISE", Path(d))
        ember.validate()
        assert ember.dissolve_mode == "rise"
        drop = load_preset("GRAVITY_DROP", Path(d))
        drop.validate()
        assert drop.dissolve_mode == "rain"
        pour = load_preset("POUR_FAKE", Path(d))
        pour.validate()
        assert (pour.dissolve_mode, pour.dissolve_stagger) == ("flow", "rank")
        assert pour.dissolve_amount == 0.5


def _halves():
    from PIL import ImageDraw

    a = Image.new("RGB", (48, 48), (255, 255, 255))
    b = Image.new("RGB", (48, 48), (255, 255, 255))
    ImageDraw.Draw(a).rectangle([0, 0, 23, 47], fill=(0, 0, 0))
    ImageDraw.Draw(b).rectangle([24, 0, 47, 47], fill=(0, 0, 0))
    return a, b


def _meanx(im):
    import numpy as np

    g = np.asarray(im.convert("L"))
    ys, xs = np.nonzero(g < 128)
    return float(xs.mean()) if len(xs) else -1.0


def test_f3_match_travel_bijection_and_deterministic():
    import numpy as np

    from app.disintegrate import dither_bw, match_travel, points_from_dither

    a, b = _halves()
    ca, h, w = points_from_dither(dither_bw(a))
    cb, _, _ = points_from_dither(dither_bw(b))
    assert len(ca) > 0 and len(cb) > 0
    s, d = match_travel(ca, cb, h, w, seed=7)
    assert len(s) == len(d) == max(len(ca), len(cb))
    s2, d2 = match_travel(ca, cb, h, w, seed=7)
    assert (s == s2).all() and (d == d2).all()
    if len(ca) == len(cb):  # true bijection when counts match
        assert len({tuple(p) for p in np.asarray(d).tolist()}) == len(d)
    # Uneven counts pad instead of crashing (gradient vs flat).
    g = _img(48)
    cg, _, _ = points_from_dither(dither_bw(g))
    sp, dp = match_travel(cg, cb, h, w, seed=7)
    assert len(sp) == len(dp) == max(len(cg), len(cb))
    # Empty sets are a safe no-op (caller falls back to legacy).
    e, _ = match_travel(np.zeros((0, 2), dtype=np.int32), cb, h, w, seed=7)
    assert len(e) == 0


def test_f3_travel_endpoints_exact():
    import numpy as np

    from app.disintegrate import dither_bw, match_travel, points_from_dither, travel_positions

    a, b = _halves()
    ca, h, w = points_from_dither(dither_bw(a))
    cb, _, _ = points_from_dither(dither_bw(b))
    s, d = match_travel(ca, cb, h, w, seed=7)
    p0 = travel_positions(s, d, h, w, progress=0.0, seed=7, travel=1.0)
    p1 = travel_positions(s, d, h, w, progress=1.0, seed=7, travel=1.0)
    assert (p0 == np.asarray(s, dtype=np.float32)).all()
    assert (p1 == np.asarray(d, dtype=np.float32)).all()


def test_f3_travel_pours_without_seam_pop():
    from app.disintegrate import dither_bw, morph_chain_frames

    a, b = _halves()
    kw = dict(frames=8, max_side=64, seed=11, wind=(0.0, 0.0),
              amount=0.5, loop=False)
    lt = morph_chain_frames([a, b], travel=1.0, **kw)
    l0 = morph_chain_frames([a, b], travel=0.0, **kw)
    assert len(lt) == len(l0) == 8
    still_a = dither_bw(a).convert("RGB")
    still_b = dither_bw(b).convert("RGB")
    assert lt[0].tobytes() == still_a.tobytes()  # opens on A
    assert lt[-1].tobytes() == still_b.tobytes()  # lands on B
    assert [f.tobytes() for f in l0] == [f.tobytes() for f in
                                         morph_chain_frames([a, b], **kw)]
    assert lt[4].tobytes() != l0[4].tobytes()  # mid-flight differs
    mx_t = [_meanx(f) for f in lt]
    mx_0 = [_meanx(f) for f in l0]
    assert mx_t[-1] > mx_t[0]  # pour travels left -> right
    assert (mx_0[4] - mx_0[3]) > (mx_t[4] - mx_t[3])  # no cloud seam jump
    # Strict 0=off still hard-cuts with travel on.
    hc = morph_chain_frames([a, b], travel=1.0, amount=0.0,
                            frames=8, max_side=64, seed=11, loop=False)
    assert hc[0].tobytes() == hc[3].tobytes() == still_a.tobytes()
    assert hc[4].tobytes() == hc[7].tobytes() == still_b.tobytes()


def test_f3_travel_preset_roundtrip_and_gif():
    import tempfile
    from pathlib import Path

    from app.gif import gif_morph_frames
    from app.presets import Preset, load_preset, save_preset

    p = Preset(name="T3", dissolve_travel=0.75)
    p.validate()
    with tempfile.TemporaryDirectory() as d:
        back = load_preset(save_preset(p, Path(d)).stem, Path(d))
        assert back.dissolve_travel == 0.75
    old = Preset.from_dict({"name": "old", "method": "bayer4"})
    assert old.dissolve_travel == 0.0
    import pytest

    with pytest.raises(ValueError):
        Preset(name="x", dissolve_travel=1.5).validate()
    Preset(name="x", dissolve_travel=1.0).validate()
    a, b = _halves()
    base = dict(name="t", method="bayer8", palette="BW", gif_size=64,
                dissolve_hold=0.0, dissolve_length=0.0)
    out = gif_morph_frames(a, b, Preset(**base, dissolve_travel=1.0),
                           frames=8, max_side=64)
    assert len(out) == 8
    again = gif_morph_frames(a, b, Preset(**base, dissolve_travel=1.0),
                             frames=8, max_side=64)
    assert [f.tobytes() for f in out] == [f.tobytes() for f in again]
    assert out[0].tobytes() != out[4].tobytes()


def _solid(color, size=48):
    return Image.new("RGB", (size, size), color)


def _has_color(im):
    import numpy as np

    arr = np.asarray(im.convert("RGB")).astype(int)
    return bool(((arr[:, :, 0] != arr[:, :, 1])
                 | (arr[:, :, 1] != arr[:, :, 2])).any())


def test_f4_tint_helpers():
    import numpy as np

    from app.disintegrate import sample_colors, tint_dots, tint_strength

    assert tint_strength(1.0, 0.0) == 0.0
    assert tint_strength(0.0, 0.7) == 0.0
    assert tint_strength(1.0, 0.5) == 0.5
    assert tint_dots(np.ones((3, 3)), 0.0) is None
    cols = tint_dots(np.full((2, 3), 200.0), 0.5)
    assert cols is not None and cols.dtype == np.uint8
    assert (cols == 100).all()
    arr = sample_colors(_solid((10, 20, 30), 8), 4, 4)
    assert arr.shape == (4, 4, 3) and (arr == (10, 20, 30)).all()


def test_f4_tint_dissolve_mid_colored_joints_bw():
    from app.disintegrate import dissolve_frames

    a = _solid((200, 50, 90))
    t = dissolve_frames(a, frames=8, max_side=64, seed=7, tint=1.0)
    u = dissolve_frames(a, frames=8, max_side=64, seed=7)
    assert len(t) == len(u) == 8
    assert t[0].tobytes() == u[0].tobytes()  # joints land black
    assert t[4].tobytes() != u[4].tobytes()  # mid-flight tinted
    assert _has_color(t[4])
    assert not _has_color(u[4])
    again = dissolve_frames(a, frames=8, max_side=64, seed=7, tint=1.0)
    assert [f.tobytes() for f in t] == [f.tobytes() for f in again]
    legacy = dissolve_frames(a, frames=8, max_side=64, seed=7, tint=0.0)
    assert [f.tobytes() for f in legacy] == [f.tobytes() for f in u]
    # Strict 0=off ignores tint (hard cut, no mid-flight to paint).
    hc = dissolve_frames(a, frames=8, max_side=64, seed=7, tint=1.0, amount=0.0)
    assert len({f.tobytes() for f in hc}) == 1


def test_f4_tint_morph_travel_lerps_color():
    from app.disintegrate import dither_bw, morph_chain_frames

    a = _solid((200, 40, 40))
    b = _solid((40, 180, 60))
    kw = dict(frames=8, max_side=64, seed=7, travel=1.0, loop=False)
    t = morph_chain_frames([a, b], tint=1.0, **kw)
    u = morph_chain_frames([a, b], **kw)
    assert t[0].tobytes() == dither_bw(a).convert("RGB").tobytes()
    assert t[-1].tobytes() == dither_bw(b).convert("RGB").tobytes()
    assert t[0].tobytes() == u[0].tobytes()
    assert t[-1].tobytes() == u[-1].tobytes()
    assert t[4].tobytes() != u[4].tobytes()
    assert _has_color(t[4])
    # Travel-off legs tint from their own form.
    s = morph_chain_frames([a, b], tint=1.0, travel=0.0, frames=8,
                           max_side=64, seed=7, loop=False)
    assert _has_color(s[2]) and s[0].tobytes() == u[0].tobytes()


def test_f4_tint_render_points_colors_and_sizes():
    import numpy as np

    from app.disintegrate import render_points

    pos = np.array([[5.0, 5.0], [10.0, 10.0], [20.0, 20.0]])
    cols = np.array([[200, 0, 0], [0, 200, 0], [0, 0, 200]], dtype=np.uint8)
    im = render_points(pos, 32, 32, None, cols)
    px = np.asarray(im)
    assert (px[5, 5] == (200, 0, 0)).all()
    assert (px[10, 10] == (0, 200, 0)).all()
    bw = render_points(pos, 32, 32)
    assert (np.asarray(bw)[5, 5] == (0, 0, 0)).all()
    fat = render_points(pos, 32, 32, np.array([2, 2, 2]), cols)
    assert (np.asarray(fat)[6, 6] == (200, 0, 0)).all()  # 2x2 block
    black = render_points(pos, 32, 32, None, np.zeros((3, 3), dtype=np.uint8))
    assert black.tobytes() == bw.tobytes()  # all-black == legacy path


def test_f4_tint_preset_roundtrip_and_gif():
    import tempfile
    from pathlib import Path

    import pytest

    from app.gif import gif_dissolve_frames, gif_morph_frames
    from app.presets import Preset, load_preset, save_preset

    p = Preset(name="T4", dissolve_tint=0.6)
    p.validate()
    with tempfile.TemporaryDirectory() as d:
        back = load_preset(save_preset(p, Path(d)).stem, Path(d))
        assert back.dissolve_tint == 0.6
    old = Preset.from_dict({"name": "old", "method": "bayer4"})
    assert old.dissolve_tint == 0.0
    with pytest.raises(ValueError):
        Preset(name="x", dissolve_tint=1.5).validate()
    Preset(name="x", dissolve_tint=1.0).validate()
    a = _solid((200, 50, 90))
    b = _solid((40, 180, 60))
    base = dict(name="t", method="bayer8", palette="BW", gif_size=64,
                dissolve_hold=0.0, dissolve_length=0.0)
    d = gif_dissolve_frames(a, Preset(**base, dissolve_tint=1.0),
                            frames=6, max_side=64)
    plain = gif_dissolve_frames(a, Preset(**base), frames=6, max_side=64)
    assert len(d) == len(plain) == 6
    assert d[0].tobytes() == plain[0].tobytes()
    assert d[2].tobytes() != plain[2].tobytes() and _has_color(d[2])
    m = gif_morph_frames(a, b, Preset(**base, dissolve_tint=1.0),
                         frames=8, max_side=64, loop=False)
    mp = gif_morph_frames(a, b, Preset(**base), frames=8, max_side=64,
                          loop=False)
    assert m[-1].tobytes() == mp[-1].tobytes()  # lands black
    assert m[4].tobytes() != mp[4].tobytes() and _has_color(m[4])
