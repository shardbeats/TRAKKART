"""Image ops + undo tests."""

from PIL import Image

from app.ops import ImageHistory, flip_h, flip_v, invert, rotate_left, rotate_right


def _img() -> Image.Image:
    im = Image.new("RGB", (40, 20))
    px = im.load()
    for y in range(20):
        for x in range(40):
            px[x, y] = (x * 6 % 256, y * 12 % 256, 100)
    return im


def test_rotate_swaps_dims():
    assert rotate_left(_img()).size == (20, 40)
    assert rotate_right(_img()).size == (20, 40)


def test_flip_mirrors():
    im = _img()
    assert flip_h(im).load()[0, 0] == im.load()[39, 0]
    assert flip_v(im).load()[0, 0] == im.load()[0, 19]


def test_invert():
    out = invert(Image.new("RGB", (4, 4), (10, 20, 30)))
    assert set(out.get_flattened_data()) == {(245, 235, 225)}


def test_history_undo_cap_clear():
    h = ImageHistory(limit=3)
    assert h.undo() is None
    base = _img()
    h.push(base)
    assert len(h) == 1
    h.push(flip_h(base))
    h.push(flip_v(base))
    h.push(invert(base))
    assert len(h) == 3  # cap
    back = h.undo()
    assert back is not None and back.size == (40, 20)
    h.clear()
    assert len(h) == 0 and h.undo() is None
