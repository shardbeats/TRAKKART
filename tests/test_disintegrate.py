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

    p = Preset(name="t", method="bayer8", palette="BW", gif_size=64)
    d = gif_frames(_img(), p, frames=3, mode="dissolve")
    assert len(d) == 3
    assert len({tuple(x.get_flattened_data()) for x in d}) > 1
    b = Image.new("RGB", (64, 64), (10, 200, 90))
    m = gif_frames(_img(), p, frames=4, mode="morph", img_b=b)
    assert len(m) == 4
    assert tuple(m[0].get_flattened_data()) != tuple(m[-1].get_flattened_data())
