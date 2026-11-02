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
