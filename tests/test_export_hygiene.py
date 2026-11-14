"""Phase C (v1.7): export hygiene tests (fingerprint guard + encoder select)."""

from PIL import Image

from app.anim.fingerprint import clip_fingerprint


def _img(color=(10, 20, 30)):
    return Image.new("RGB", (64, 64), color)


def test_fingerprint_stable_and_sensitive():
    meta = {"method": "bayer8", "dissolve": {"seed": 1}}
    chain = [{"img": _img(), "repeat": 1}]
    spec = {"mode": "morph", "frames": 8, "fps": 24}
    a = clip_fingerprint(_img(), meta, chain, spec)
    assert clip_fingerprint(_img(), meta, chain, spec) == a
    # any input change flips it: src, preset, chain repeat, spec
    assert clip_fingerprint(_img((99, 0, 0)), meta, chain, spec) != a
    assert clip_fingerprint(_img(), {"method": "floyd"}, chain, spec) != a
    chain2 = [{"img": _img(), "repeat": 2}]
    assert clip_fingerprint(_img(), meta, chain2, spec) != a
    assert clip_fingerprint(_img(), meta, chain, {**spec, "fps": 30}) != a


def test_video_io_is_libx264_only():
    import inspect

    from app import video_io

    # Single software encoder by design: no hardware probing surface.
    assert not hasattr(video_io, "available_encoders")
    assert not hasattr(video_io, "resolve_encoder")
    assert not hasattr(video_io, "reset_encoder_cache")
    assert not hasattr(video_io, "HW_ENCODERS")
    assert "codec" not in inspect.signature(video_io.write_mp4).parameters
    assert "codec" not in inspect.signature(video_io.write_mp4_iter).parameters


def test_write_mp4_libx264(tmp_path):
    from app.video_io import has_video, write_mp4, write_mp4_iter

    if not has_video():
        import pytest
        pytest.skip("video backend missing")
    frames = [_img((i * 20 % 256, 0, 0)) for i in range(4)]
    out = write_mp4(frames, tmp_path / "a.mp4", fps=8)
    assert out.is_file() and out.stat().st_size > 0
    out2, n = write_mp4_iter(iter(frames), tmp_path / "b.mp4", fps=8)
    assert n == 4 and out2.is_file()


def test_prefs_ignores_legacy_encoder_field(tmp_path):
    import json

    from app.export_prefs import ExportPrefs, load_prefs, normalize_prefs, save_prefs

    # Old prefs JSON may still carry mp4_encoder: loads fine, field is gone.
    (tmp_path / "p.json").write_text(json.dumps({"mp4_encoder": "auto"}),
                                     encoding="utf-8")
    prefs = load_prefs(tmp_path / "p.json")
    assert not hasattr(prefs, "mp4_encoder")
    normalize_prefs(prefs)
    assert not hasattr(prefs, "mp4_encoder")
    save_prefs(ExportPrefs(), tmp_path / "q.json")
    assert "mp4_encoder" not in json.loads(
        (tmp_path / "q.json").read_text(encoding="utf-8"))
    legacy = load_prefs(tmp_path / "nope.json")
    assert not hasattr(legacy, "mp4_encoder")


def test_export_service_writes_mp4(tmp_path):
    from app.presets import Preset
    from app.services.export_service import export_full
    from app.video_io import has_video

    if not has_video():
        import pytest
        pytest.skip("video backend missing")
    preset = Preset(name="t")
    paths, _skipped = export_full(
        _img(), preset, tmp_path, base="c",
        mp4=True, mp4_fps=8, mp4_size="720p",
        gif_frames=4, gif_mode="both",
    )
    assert paths["video"].is_file()


def test_stale_badge_logic_without_qt():
    from app.ui import video_controller as vc

    class Win:
        pass

    w = Win()
    w._video_on = False
    w._video_frames = []
    w._video_fingerprint = ""
    # no badge widgets -> no crash
    vc.sync_stale_badge(w)
    # badge widgets but video off -> hidden, no crash

    class Lbl:
        def __init__(self):
            self.text = ""
            self.visible = True

        def setText(self, t):
            self.text = t

        def setVisible(self, v):
            self.visible = v

    w.lbl_stale, w.btn_rebuild = Lbl(), Lbl()
    vc.sync_stale_badge(w)
    assert w.lbl_stale.visible is False
