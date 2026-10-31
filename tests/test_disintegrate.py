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
