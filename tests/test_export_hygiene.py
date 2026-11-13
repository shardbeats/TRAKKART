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


def test_resolve_encoder_defaults_and_fallback():
    from app.video_io import resolve_encoder, reset_encoder_cache

    reset_encoder_cache()
    try:
        from app.video_io import available_encoders

        avail = available_encoders()
        assert "libx264" in avail
        assert resolve_encoder("libx264") == "libx264"
        assert resolve_encoder("nope") == "libx264"
        assert resolve_encoder(None) == "libx264"  # historic default: software
        assert resolve_encoder("") == "libx264"
        auto = resolve_encoder("auto")
        assert auto in avail
    finally:
        reset_encoder_cache()


def test_write_mp4_codec_param(tmp_path):
    from app.video_io import has_video, write_mp4, write_mp4_iter

    if not has_video():
        import pytest
        pytest.skip("video backend missing")
    frames = [_img((i * 20 % 256, 0, 0)) for i in range(4)]
    out = write_mp4(frames, tmp_path / "a.mp4", fps=8, codec="libx264")
    assert out.is_file() and out.stat().st_size > 0
    out2, n = write_mp4_iter(iter(frames), tmp_path / "b.mp4", fps=8,
                             codec="libx264")
    assert n == 4 and out2.is_file()

    # Hardware hiccup (incl. silent 0-byte files on tiny frames) retries
    # in software instead of shipping an empty MP4.
    from app.video_io import HW_ENCODERS, available_encoders

    hw = [e for e in HW_ENCODERS if e in available_encoders()]
    if hw:
        tiny = write_mp4(frames, tmp_path / "hw.mp4", fps=8, codec=hw[0])
        assert tiny.stat().st_size > 1000


def test_prefs_encoder_roundtrip_and_normalize(tmp_path):
    from app.export_prefs import ExportPrefs, load_prefs, normalize_prefs, save_prefs

    p = ExportPrefs(mp4_encoder="auto")
    normalize_prefs(p)
    assert p.mp4_encoder == "auto"
    save_prefs(p, tmp_path / "p.json")
    assert load_prefs(tmp_path / "p.json").mp4_encoder == "auto"
    bad = ExportPrefs(mp4_encoder="x265")
    normalize_prefs(bad)
    assert bad.mp4_encoder == "libx264"
    legacy = load_prefs(tmp_path / "nope.json")
    assert legacy.mp4_encoder == "libx264"


def test_export_service_accepts_codec(tmp_path):
    from app.presets import Preset
    from app.services.export_service import export_full
    from app.video_io import has_video

    if not has_video():
        import pytest
        pytest.skip("video backend missing")
    preset = Preset(name="t")
    paths, _skipped = export_full(
        _img(), preset, tmp_path, base="c",
        mp4=True, mp4_fps=8, mp4_size="720p", mp4_codec="libx264",
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
