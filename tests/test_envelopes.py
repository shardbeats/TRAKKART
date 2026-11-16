"""Pins for candidate #3 Fase A: envelope engine (pure, deterministic)."""

from __future__ import annotations


def test_flat_and_off():
    from app.envelopes import eval_envelope, normalize_envelope

    assert normalize_envelope(None, "grain") is None
    assert normalize_envelope({"kind": "off"}, "grain") is None
    assert normalize_envelope("junk", "grain") is None
    assert normalize_envelope({"kind": "flat"}, "nope") is None
    spec = normalize_envelope({"kind": "flat", "value": 40}, "grain")
    assert eval_envelope(spec, 0.0, 0.0, "grain") == 40.0
    assert eval_envelope(spec, 1.0, 0.0, "grain") == 40.0
    assert eval_envelope(None, 0.5, 7.0, "grain") == 7.0


def test_ramp_endpoints_and_clamp():
    from app.envelopes import eval_envelope, normalize_envelope

    spec = normalize_envelope({"kind": "ramp", "v0": 0, "v1": 100}, "grain")
    assert eval_envelope(spec, 0.0, 0.0, "grain") == 0.0
    assert eval_envelope(spec, 1.0, 0.0, "grain") == 100.0
    assert eval_envelope(spec, 0.5, 0.0, "grain") == 50.0
    big = normalize_envelope({"kind": "ramp", "v0": -50, "v1": 9999}, "grain")
    assert eval_envelope(big, 0.0, 0.0, "grain") == 0.0
    assert eval_envelope(big, 1.0, 0.0, "grain") == 100.0


def test_lfo_loop_perfect_and_deterministic():
    from app.envelopes import eval_envelope, normalize_envelope

    spec = normalize_envelope({"kind": "lfo", "base": 50, "amp": 20, "loops": 2}, "grain")
    a = eval_envelope(spec, 0.0, 0.0, "grain")
    b = eval_envelope(spec, 1.0, 0.0, "grain")
    assert a == b == 50.0
    mid = eval_envelope(spec, 0.125, 0.0, "grain")
    assert mid == 70.0
    again = eval_envelope(spec, 0.125, 0.0, "grain")
    assert again == mid


def test_keys_interp():
    from app.envelopes import eval_envelope, normalize_envelope

    spec = normalize_envelope({"kind": "keys", "points": [[0, 0], [1, 100]]}, "grain")
    assert eval_envelope(spec, 0.25, 0.0, "grain") == 25.0
    assert eval_envelope(spec, 0.0, 99.0, "grain") == 0.0
    assert normalize_envelope({"kind": "keys", "points": []}, "grain") is None


def test_frame_values_and_signature():
    from app.envelopes import envelopes_signature, frame_values

    fb = {"motion_amount": 1.0, "drift_amount": 10.0, "grain": 5.0}
    flat = frame_values({}, 0.5, fb)
    assert flat == fb
    env = {"grain": {"kind": "ramp", "v0": 0, "v1": 10.0}}
    assert frame_values(env, 0.5, fb)["grain"] == 5.0
    assert frame_values(env, 0.5, fb)["motion_amount"] == 1.0
    assert envelopes_signature({}) == "off"
    assert envelopes_signature(None) == "off"
    s1 = envelopes_signature(env)
    s2 = envelopes_signature({"grain": {"kind": "ramp", "v0": 0, "v1": 10}})
    assert s1 == s2
    assert envelopes_signature({"grain": {"kind": "flat", "value": 1}}) != s1


def test_motion_range_clamps():
    from app.envelopes import eval_envelope, normalize_envelope

    spec = normalize_envelope({"kind": "flat", "value": 99}, "motion_amount")
    assert eval_envelope(spec, 0.0, 1.0, "motion_amount") == 3.0


def _preset():
    from app.presets import Preset

    return Preset(method="bayer4", palette="SLIME", pixel_size=1, threshold=128,
                  grain=40.0, drift_pattern="lines", drift_amount=60.0)


def test_empty_envelopes_byte_identical():
    from PIL import Image

    from app.gif import gif_frames

    img = Image.new("RGB", (48, 48), (120, 40, 200))
    a = gif_frames(img, _preset(), frames=4, mode="both", max_side=48)
    b = gif_frames(img, _preset(), frames=4, mode="both", max_side=48, envelopes={})
    assert [f.tobytes() for f in a] == [f.tobytes() for f in b]


def test_ramp_envelope_moves_pixels():
    from PIL import Image

    from app.gif import gif_frames

    img = Image.new("RGB", (48, 48), (120, 40, 200))
    flat = gif_frames(img, _preset(), frames=4, mode="both", max_side=48)
    env = {"grain": {"kind": "ramp", "v0": 0, "v1": 100.0}}
    curved = gif_frames(img, _preset(), frames=4, mode="both", max_side=48, envelopes=env)
    assert [f.tobytes() for f in flat] != [f.tobytes() for f in curved]


def test_clip_envelopes_change_pixels():
    from PIL import Image

    from app.clip import dither_clip

    frames = [Image.new("RGB", (48, 48), (30, 200, 90)) for _ in range(4)]
    flat = dither_clip(frames, _preset())
    env = {"grain": {"kind": "ramp", "v0": 0, "v1": 100.0}}
    curved = dither_clip(frames, _preset(), envelopes=env)
    assert [f.tobytes() for f in flat] != [f.tobytes() for f in curved]
    again = dither_clip(frames, _preset(), envelopes=env)
    assert [f.tobytes() for f in curved] == [f.tobytes() for f in again]


def test_envelope_widgets_session_only(window):
    from app.ui import envelope_controller as _env

    for param in ("motion_amount", "drift_amount", "grain"):
        assert getattr(window, f"cmb_env_{param}").currentText() == "Off"
    assert _env.read_envelopes(window) == {}
    window.cmb_env_grain.setCurrentText("Ramp")
    window.spn_env_grain_a.setValue(0.0)
    window.spn_env_grain_b.setValue(100.0)
    env = _env.read_envelopes(window)
    assert env["grain"]["kind"] == "ramp"
    assert dict(getattr(window, "_envelopes", {})) == env
    # Session-only: preset meta never carries envelopes.
    assert "envelopes" not in window.current_params().meta()
    _env.clear_envelopes(window)
    assert _env.read_envelopes(window) == {}
