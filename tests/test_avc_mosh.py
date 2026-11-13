"""Phase A (v1.7): true-AVC engine frame-level tests (offline, no ffmpeg)."""

from PIL import Image

from app.avc_mosh import (
    AVC_MODES,
    apply_avc_mosh,
    avc_mosh_frames,
    plan_cuts,
)


def _clip(n=12, color=(255, 0, 0)):
    return [Image.new("RGB", (16, 16), color) for _ in range(n)]


def _varied(n=12):
    return [Image.new("RGB", (16, 16), (i * 20 % 256, 0, 0)) for i in range(n)]


def test_bleed_zero_is_passthrough():
    clip = _varied()
    out = apply_avc_mosh(clip, bleed=0, mode="bleed", seed=7, n_segs=3)
    assert out == clip  # same objects, untouched
    assert list(avc_mosh_frames(iter(clip), bleed=0)) == clip


def test_plan_cuts_deterministic_and_shaped():
    assert plan_cuts(12, 1, 7) == []
    c1 = plan_cuts(12, 3, seed=42)
    assert c1 == plan_cuts(12, 3, seed=42)
    assert len(c1) == 2 and all(1 <= c < 12 for c in c1)
    assert c1 == sorted(c1)


def test_bleed_changes_cut_window_only():
    clip = _varied()
    out = apply_avc_mosh(clip, bleed=3, mode="bleed", seed=42, n_segs=3)
    assert len(out) == len(clip)  # bleed never changes the count
    cuts = plan_cuts(len(clip), 3, seed=42)
    assert cuts
    assert out[0].tobytes() == clip[0].tobytes()  # pre-cut frames intact
    assert any(out[c].tobytes() != clip[c].tobytes() for c in cuts)
    # determinism: same seed replays
    out2 = apply_avc_mosh(clip, bleed=3, mode="bleed", seed=42, n_segs=3)
    assert [f.tobytes() for f in out] == [f.tobytes() for f in out2]


def test_hold_repeats_cut_frame():
    clip = _varied()
    b = 2
    out = apply_avc_mosh(clip, bleed=b, mode="hold", seed=42, n_segs=3)
    cuts = plan_cuts(len(clip), 3, seed=42)
    assert len(out) == len(clip) + b * len(cuts)
    for idx, c in enumerate(cuts):
        pos = c + b * idx  # repeats shift everything after each cut
        for r in out[pos:pos + b]:
            assert r.tobytes() == clip[c - 1].tobytes()
        assert out[pos + b].tobytes() == clip[c].tobytes()  # cut frame follows


def test_smear_same_count_deterministic():
    clip = _varied()
    out = apply_avc_mosh(clip, bleed=10, mode="smear", seed=9, n_segs=2)
    assert len(out) == len(clip)
    out2 = apply_avc_mosh(clip, bleed=10, mode="smear", seed=9, n_segs=2)
    assert [f.tobytes() for f in out] == [f.tobytes() for f in out2]


def test_unknown_mode_falls_back_to_bleed():
    clip = _varied()
    a = apply_avc_mosh(clip, bleed=3, mode="nope", seed=42, n_segs=3)
    b = apply_avc_mosh(clip, bleed=3, mode="bleed", seed=42, n_segs=3)
    assert [f.tobytes() for f in a] == [f.tobytes() for f in b]
    assert set(AVC_MODES) == {"bleed", "smear", "hold"}


def test_preset_roundtrip():
    from app.presets import Preset

    p = Preset(name="x", avc_bleed=12, avc_mode="hold")
    p.validate()
    q = Preset.from_dict(p.to_dict())
    assert (q.avc_bleed, q.avc_mode) == (12, "hold")
    legacy = Preset.from_dict({"method": "bayer4"})
    assert (legacy.avc_bleed, legacy.avc_mode) == (0, "bleed")


def test_metadata_roundtrip_keeps_avc():
    from app.presets import Preset, preset_from_metadata

    p = Preset(name="x", avc_bleed=12, avc_mode="smear")
    back = preset_from_metadata({"params": p.meta()})
    assert (back.avc_bleed, back.avc_mode) == (12, "smear")
