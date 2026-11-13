"""Phase B (v1.7): segment timeline tests (plan + engine + frames wiring)."""

from PIL import Image

from app.anim.plan import leg_transitions, plan_segments, segment_total


def _imgs(n=3):
    return [Image.new("RGB", (32, 32), (i * 60, 0, 0)) for i in range(n)]


def test_segments_windows_cover_transitions():
    legs = leg_transitions(8, 2)
    segs = plan_segments(8, 2)
    assert [s.frames for s in segs] == legs
    assert segs[0].start == 0 and segs[-1].end == sum(legs)
    assert all(s.repeat == 1 for s in segs)
    assert segment_total(segs) == sum(legs)


def test_segments_repeat_math_and_clamp():
    segs = plan_segments(8, 2, repeats=[2, 0])
    assert [s.repeat for s in segs] == [2, 1]  # 0 clamps to 1
    assert segment_total(segs) == segs[0].frames * 2 + segs[1].frames
    assert segs[0].name == "A->B"
    loop = plan_segments(8, 2, repeats=[3, 2], loop=True)
    assert [s.repeat for s in loop] == [3, 2]
    assert segment_total(loop) == sum(s.frames * s.repeat for s in loop)


def test_engine_repeats_replay_same_bytes():
    from app.particles.engine import morph_chain_frames

    imgs = _imgs(3)
    base = morph_chain_frames(imgs, method="bayer8", frames=8, seed=7)
    rep = morph_chain_frames(imgs, method="bayer8", frames=8, seed=7,
                             repeats=[2, 1])
    legs = leg_transitions(8, 2)
    assert len(rep) == legs[0] * 2 + legs[1]
    assert [f.tobytes() for f in rep[:legs[0]]] == [f.tobytes() for f in base[:legs[0]]]
    assert [f.tobytes() for f in rep[legs[0]:2 * legs[0]]] == [f.tobytes() for f in base[:legs[0]]]
    assert [f.tobytes() for f in rep[2 * legs[0]:]] == [f.tobytes() for f in base[legs[0]:]]


def test_engine_default_repeats_byte_identical():
    from app.particles.engine import morph_chain_frames

    imgs = _imgs(4)
    a = morph_chain_frames(imgs, method="bayer8", frames=9, seed=7, loop=True)
    b = morph_chain_frames(imgs, method="bayer8", frames=9, seed=7, loop=True,
                           repeats=[1, 1, 1])
    assert [f.tobytes() for f in a] == [f.tobytes() for f in b]


def test_frames_wire_entry_repeats():
    from app.anim.frames import gif_morph_frames, iter_morph_frames

    a = Image.new("RGB", (32, 32), (10, 0, 0))
    b = Image.new("RGB", (32, 32), (200, 0, 0))
    entries = [{"img": b, "fx": 50.0, "fy": 50.0, "zoom": 1.0, "repeat": 2}]
    plain = gif_morph_frames(a, [{"img": b}], frames=8, seed=7)
    doubled = gif_morph_frames(a, entries, frames=8, seed=7)
    legs = leg_transitions(8, 1)
    assert len(doubled) == len(plain) + legs[0]  # one extra leg replay
    streamed = list(iter_morph_frames(a, entries, frames=8, seed=7))
    assert len(streamed) == len(doubled)


def test_split_chain_repeat_clamp():
    from app.anim.frames import _split_chain

    imgs, _crops, reps = _split_chain([{"img": _imgs(1)[0], "repeat": 99}])
    assert reps == [8]  # clamped to max 8
    _i2, _c2, reps2 = _split_chain([{"img": None}])
    assert reps2 == []
