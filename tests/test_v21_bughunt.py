"""v2.1 bug-hunt pins: hard-crash guards + clip state hygiene.

Every test here failed on the v2.0 tree (or pins a path that used to
abort the process without a traceback).
"""

import pytest
from PIL import Image


# ---------------------------------------------------------------------------
# QThread life-cycle: dropping a running QThread aborts the process
# (0xC0000409 / "QThread: Destroyed while thread is still running").
# ---------------------------------------------------------------------------
class _FakeWorker:
    def __init__(self, running=True):
        self.running = running
        self.deleted = False
        self.waited = []
        self.signals_blocked = False

    def isRunning(self):  # noqa: N802
        return self.running

    def deleteLater(self):  # noqa: N802
        self.deleted = True

    def blockSignals(self, on):  # noqa: N802
        self.signals_blocked = bool(on)

    def requestInterruption(self):  # noqa: N802
        pass

    def wait(self, ms=0):  # noqa: N802
        self.waited.append(ms)
        return not self.running


def test_retire_keeps_running_worker_alive(qt_app):
    from app.ui import thread_safe

    before = thread_safe.pending_count()
    w = _FakeWorker(running=True)
    thread_safe.retire(w)
    assert w.deleted is False
    assert thread_safe.pending_count() == before + 1
    # ...and releases it once Qt says the thread is done.
    w.running = False
    thread_safe.drop(w)
    assert w.deleted is True
    assert thread_safe.pending_count() == before


def test_retire_deletes_idle_worker(qt_app):
    from app.ui import thread_safe

    w = _FakeWorker(running=False)
    thread_safe.retire(w)
    assert w.deleted is True


def test_stop_orphans_uncooperative_worker(qt_app):
    from app.ui import thread_safe

    before = thread_safe.pending_count()
    w = _FakeWorker(running=True)
    assert thread_safe.stop(w, timeout_ms=10) is False
    assert w.waited == [10]
    assert w.signals_blocked is True
    assert w.deleted is False          # never destroy a live QThread
    assert thread_safe.pending_count() == before + 1
    w.running = False
    thread_safe.drop(w)


def test_preview_on_done_never_drops_live_worker(qt_app):
    from app.ui import preview_controller as pc
    from app.ui import thread_safe

    win = type("W", (), {})()
    win._preview_token = 3
    win._preview_pending = False
    win.src = None
    win.result = None
    fake = _FakeWorker(running=True)
    win._preview_worker = fake
    pc.on_done(win, None, None, 3)
    assert fake.deleted is False       # would abort the process otherwise
    assert win._preview_worker is None
    fake.running = False
    thread_safe.drop(fake)


def test_export_on_done_never_drops_live_worker(qt_app, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    from app.ui import export_flow, thread_safe

    monkeypatch.setattr(export_flow, "show_exported", lambda *a, **k: None)
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    fake = _FakeWorker(running=True)
    win = type("W", (), {"_export_worker": fake,
                         "_status": lambda *a, **k: None})()
    export_flow.on_export_done(win, {}, True, "b", ".")
    assert fake.deleted is False       # crash guard on the heaviest path
    assert win._export_worker is None
    fake.running = False
    thread_safe.drop(fake)


def test_export_on_error_never_drops_live_worker(qt_app):
    from app.ui import export_flow, thread_safe

    fake = _FakeWorker(running=True)
    seen = []
    win = type("W", (), {"_export_worker": fake,
                         "_report_error": lambda *a, **k: seen.append(a)})()
    export_flow.on_export_error(win, "boom")
    assert fake.deleted is False and win._export_worker is None
    assert seen
    fake.running = False
    thread_safe.drop(fake)


def test_watch_stop_never_drops_live_worker(qt_app):
    from app.ui import thread_safe, watch_flow

    fake = _FakeWorker(running=True)
    win = type("W", (), {
        "_watch_worker": fake, "_watch_cancel": [False], "_watch_src": None,
        "_watch_dst": None, "_watch_preset": "", "_watch_busy": True,
        "_watch_pending": False, "_status": lambda *a, **k: None,
    })()
    watch_flow.watch_stop(win, quiet=True)
    assert fake.deleted is False       # a running cycle must stay referenced
    assert win._watch_worker is None
    fake.running = False
    thread_safe.drop(fake)


def test_pip_done_never_drops_live_worker(qt_app):
    from app.ui import thread_safe
    from app.ui.settings_dialog import SettingsDialog

    fake = _FakeWorker(running=True)
    note = type("L", (), {"setText": lambda self, s: None})()
    stub = type("S", (), {
        "_refresh_extras": lambda *a, **k: None, "lbl_extra_note": note,
        "_pip_worker": fake,
    })()
    SettingsDialog._on_extra_done(stub, "video", True, "")
    assert fake.deleted is False
    assert stub._pip_worker is None
    fake.running = False
    thread_safe.drop(fake)


# ---------------------------------------------------------------------------
# clip state hygiene
# ---------------------------------------------------------------------------
def _anim(path, colors, size=(32, 24)):
    frames = [Image.new("RGB", size, c) for c in colors]
    frames[0].save(str(path), save_all=True, append_images=frames[1:],
                   duration=100, loop=0)
    return path


def _wav(path, secs=1.0, rate=8000):
    import math
    import struct
    import wave

    n = int(secs * rate)
    with wave.open(str(path), "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        for i in range(n):
            v = int(12000 * math.sin(2 * math.pi * 440 * i / rate))
            w.writeframes(struct.pack("<h", v))
    return path


def test_new_project_drops_session_clip(window, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    from app.ui import clip_controller as cc

    monkeypatch.setattr(QMessageBox, "question",
                        lambda *a, **k: QMessageBox.StandardButton.Ok)
    gif = _anim(window.out_dir.parent / "a.gif", [(200, 0, 0)] * 3)
    assert cc.open_path(window, gif)
    assert window._clip_frames
    window.new_project()
    assert window._clip_frames == []
    assert window._clip_dither_cache == {}
    assert window.btn_clip_play.isEnabled() is False


def test_new_project_retires_inflight_preview(window, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    from app.ui import thread_safe

    monkeypatch.setattr(QMessageBox, "question",
                        lambda *a, **k: QMessageBox.StandardButton.Ok)
    fake = _FakeWorker(running=True)
    window._preview_worker = fake
    window._preview_token = 7
    window._preview_pending = True
    window.new_project()
    assert fake.deleted is False       # crash guard
    assert window._preview_worker is None
    assert window._preview_pending is False
    assert window._preview_token > 7
    fake.running = False
    thread_safe.drop(fake)


def test_new_project_discards_late_video_result(window, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    monkeypatch.setattr(QMessageBox, "question",
                        lambda *a, **k: QMessageBox.StandardButton.Ok)
    token = window._video_token
    window.new_project()
    assert window._video_token > token


def test_reopen_clip_drops_stale_dither_cache(window):
    """Frame 0 of clip B must never reuse clip A's cached bitmap."""
    from app.clip import dither_clip
    from app.ui import clip_controller as cc

    base = window.out_dir.parent
    a = _anim(base / "red.gif", [(255, 0, 0)] * 3)
    b = _anim(base / "blue.gif", [(0, 0, 255)] * 3)
    assert cc.open_path(window, a)
    cc.scrub(window, 0)
    first_a = cc.dithered_frame(window, 0)

    assert cc.open_path(window, b)
    cc.scrub(window, 0)
    first_b = cc.dithered_frame(window, 0)

    expected_b = dither_clip([window._clip_frames[0]], window.current_params())[0]
    assert first_b.tobytes() == expected_b.tobytes()
    assert first_b.tobytes() != first_a.tobytes()


def test_close_clip_frees_frames_and_cache(window):
    from app.ui import clip_controller as cc

    gif = _anim(window.out_dir.parent / "c.gif", [(0, 120, 0)] * 4)
    assert cc.open_path(window, gif)
    cc.scrub(window, 0)  # async: request launched, pixels land later
    assert cc.request_clip_frame(window, 0) in ("hit", "launched", "coalesced")
    cc.dithered_frame(window, 0)  # sync fill (same pixels as the worker)
    assert window._clip_dither_cache
    cc.close_clip(window)
    assert window._clip_frames == []
    assert window._clip_dither_cache == {}
    assert window._clip_info == {}


# ---------------------------------------------------------------------------
# import/export edge cases
# ---------------------------------------------------------------------------
def test_mp4_unknown_nframes_still_flags_truncation(monkeypatch):
    """imageio reports nframes=inf for long MP4s; the cap notice must survive."""
    import numpy as np

    from app import clip as _clip

    class FakeReader:
        def __init__(self, n, nframes):
            self.n = n
            self.meta = {"fps": 30, "nframes": nframes}

        def get_meta_data(self):
            return dict(self.meta)

        def __iter__(self):
            for _ in range(self.n):
                yield np.zeros((16, 16, 3), dtype=np.uint8)

        def close(self):
            pass

    import imageio.v2 as iio2

    monkeypatch.setattr(iio2, "get_reader",
                        lambda *a, **k: FakeReader(500, float("inf")))
    frames, fps, truncated, _s, _d = _clip._read_mp4("x.mp4", 120, 64)
    assert len(frames) == 120 and fps == 30
    assert truncated is True

    monkeypatch.setattr(iio2, "get_reader",
                        lambda *a, **k: FakeReader(4, 4))
    frames, _fps, truncated, _s, _d = _clip._read_mp4("x.mp4", 120, 64)
    assert len(frames) == 4 and truncated is False


def test_mp4_proxy_scaled_by_ffmpeg(monkeypatch):
    """The 720p proxy must be produced by ffmpeg (-s/size), not Python resize."""
    import numpy as np

    from app import clip as _clip

    seen = {}

    class FakeReader:
        def __init__(self, size=None):
            self.size = size
            seen["size"] = size

        def get_meta_data(self):
            return {"fps": 30, "nframes": 50, "size": (1920, 1080)}

        def __iter__(self):
            w, h = self.size or (1920, 1080)
            for _ in range(50):
                yield np.zeros((h, w, 3), dtype=np.uint8)

        def close(self):
            pass

    import imageio.v2 as iio2

    monkeypatch.setattr(iio2, "get_reader",
                        lambda *a, **k: FakeReader(k.get("size")))
    frames, fps, truncated, _s, _d = _clip._read_mp4("x.mp4", 10, 720)
    assert seen["size"] == (720, 405)
    assert frames[0].size == (720, 405)
    assert (len(frames), fps, truncated) == (10, 30, True)


def test_proxy_dims_portrait_and_small():
    from app.clip import _proxy_dims

    assert _proxy_dims(1920, 1080, 720) == (720, 405)
    assert _proxy_dims(1080, 1920, 720) == (405, 720)
    assert _proxy_dims(40, 30, 720) == (40, 30)
    assert _proxy_dims(0, 0, 720) == (0, 0)


def test_has_video_requires_ffmpeg_binary(monkeypatch):
    import imageio_ffmpeg

    from app import video_io

    def boom():
        raise RuntimeError("no ffmpeg binary")

    monkeypatch.setattr(imageio_ffmpeg, "get_ffmpeg_exe", boom)
    assert video_io.has_video() is False


def test_mux_short_track_never_cuts_video(tmp_path):
    pytest.importorskip("imageio_ffmpeg")
    from app.clip import mux_soundtrack, write_clip_mp4
    from app.video_io import has_video

    if not has_video():
        pytest.skip("no video backend")
    frames = [Image.new("RGB", (64, 48), (i * 30, 20, 20)) for i in range(20)]
    silent = write_clip_mp4(frames, tmp_path / "clip.mp4", fps=10)  # 2.0s
    track = _wav(tmp_path / "short.wav", secs=0.4)
    keep = tmp_path / "out.part.mp4"  # old scratch name: must survive
    keep.write_bytes(b"user file")
    out = mux_soundtrack(silent, track, tmp_path / "out.mp4")
    assert keep.read_bytes() == b"user file"

    from app.clip import clip_duration
    import imageio.v2 as iio2

    with iio2.get_reader(str(out)) as r:
        dur = float(r.get_meta_data().get("duration", 0.0))
    assert dur == pytest.approx(clip_duration(20, 10), abs=0.25)


def test_mux_failure_leaves_no_partial_file(tmp_path):
    pytest.importorskip("imageio_ffmpeg")
    from app.clip import mux_soundtrack, write_clip_mp4
    from app.video_io import has_video

    if not has_video():
        pytest.skip("no video backend")
    frames = [Image.new("RGB", (64, 48), (10, 20, 30)) for _ in range(4)]
    silent = write_clip_mp4(frames, tmp_path / "clip.mp4", fps=10)
    bogus = tmp_path / "not_audio.mp3"
    bogus.write_bytes(b"this is not audio")
    out = tmp_path / "muxed.mp4"
    with pytest.raises(RuntimeError):
        mux_soundtrack(silent, bogus, out)
    assert not out.exists()
    assert not list(tmp_path.glob("*.part*"))


def test_trimmed_empty_when_range_inverted(window):
    from app.ui import clip_controller as cc

    gif = _anim(window.out_dir.parent / "t.gif", [(9, 9, 9)] * 5)
    assert cc.open_path(window, gif)
    window.spn_clip_end.setValue(1)
    window.spn_clip_start.setValue(3)   # forced end == start
    assert len(cc.trimmed(window)) == 1


# ---------------------------------------------------------------------------
# adversarial input (import must fail clean, never leave half state)
# ---------------------------------------------------------------------------
def test_import_single_frame_and_zero_cap(tmp_path):
    from app.clip import import_clip

    gif = _anim(tmp_path / "one.gif", [(4, 5, 6)])
    frames, info = import_clip(gif)
    assert len(frames) == 1 and info["truncated"] is False
    frames, info = import_clip(gif, max_frames=0)   # clamp, never crash
    assert len(frames) == 1 and info["frames"] == 1


def test_import_corrupt_mp4_raises_clean(tmp_path):
    from app.clip import import_clip
    from app.video_io import has_video

    if not has_video():
        pytest.skip("no video backend")
    bad = tmp_path / "bad.mp4"
    bad.write_bytes(b"\x00" * 512)
    with pytest.raises(Exception):
        import_clip(bad)


def test_open_path_failure_keeps_previous_clip(window):
    from app.ui import clip_controller as cc

    gif = _anim(window.out_dir.parent / "ok.gif", [(1, 2, 3)] * 3)
    assert cc.open_path(window, gif)
    before = list(window._clip_frames)
    bad = window.out_dir.parent / "broken.webp"
    bad.write_bytes(b"not an image")
    assert cc.open_path(window, bad) is False
    assert window._clip_frames == before   # no half-loaded state


def test_helpers_clamp_and_bounds():
    from PIL import Image as Img

    from app.clip import _clamp_fps, _fit_proxy, clip_duration

    assert _clamp_fps(None) == 24
    assert _clamp_fps("x") == 24
    assert _clamp_fps(0) == 2
    assert _clamp_fps(999) == 60
    assert _fit_proxy(Img.new("RGB", (40, 30)), 720).size == (40, 30)
    assert max(_fit_proxy(Img.new("RGB", (3000, 500)), 720).size) == 720
    assert clip_duration(0, 0) == 0.0
    assert clip_duration(24, 24) == 1.0


def test_zip_frames_are_rgb(tmp_path):
    import io
    import zipfile

    from app.clip import save_clip_zip

    frames = [Image.new("RGBA", (8, 8), (1, 2, 3, 128))]
    out = save_clip_zip(frames, tmp_path / "rgba.zip")
    with zipfile.ZipFile(out) as zf:
        img = Image.open(io.BytesIO(zf.read("frame_0001.png")))
        assert img.mode == "RGB"


def test_clip_export_never_overwrites(tmp_path, monkeypatch):
    """Repeat exports follow the stills rule: rename (base_2), never clobber."""
    from PySide6.QtWidgets import QMessageBox

    from app.presets import Preset
    from app.ui import clip_controller as cc

    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)

    class _Spn:
        def __init__(self, v):
            self._v = v

        def value(self):
            return self._v

    win = type("W", (), {})()
    win._clip_frames = [Image.new("RGB", (32, 24), (5, i * 40, 5)) for i in range(3)]
    win._clip_info = {"path": "x.mp4", "fps": 10, "frames": 3}
    win._clip_start, win._clip_end = 0, 2
    win._clip_audio = ""
    win.out_dir = tmp_path
    win.spn_clip_start = _Spn(0)
    win.spn_clip_end = _Spn(2)
    win.spn_clip_fps = _Spn(10)
    win.current_params = lambda: Preset(name="t", method="bayer4", palette="BW")
    win._status = lambda *_a, **_k: None

    cc.export_clip(win, "gif")
    cc.export_clip(win, "gif")
    assert (tmp_path / "x_clip.gif").is_file()
    assert (tmp_path / "x_clip_2.gif").is_file()


def test_clip_export_cleans_failed_mp4(tmp_path, monkeypatch):
    """A failed encode leaves no partial *_silent.mp4 next to the exports."""
    from PySide6.QtWidgets import QMessageBox

    from app import clip as _clip
    from app.presets import Preset
    from app.ui import clip_controller as cc

    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)

    def broken(frames, out, fps=24):
        from pathlib import Path

        Path(out).write_bytes(b"partial")
        raise RuntimeError("encoder died")

    monkeypatch.setattr(_clip, "write_clip_mp4", broken)

    class _Spn:
        def __init__(self, v):
            self._v = v

        def value(self):
            return self._v

    win = type("W", (), {})()
    win._clip_frames = [Image.new("RGB", (16, 16), (1, 2, 3))] * 2
    win._clip_info = {"path": "x.mp4", "fps": 10, "frames": 2}
    win._clip_start, win._clip_end = 0, 1
    win._clip_audio = ""
    win.out_dir = tmp_path
    win.spn_clip_start = _Spn(0)
    win.spn_clip_end = _Spn(1)
    win.spn_clip_fps = _Spn(10)
    win.current_params = lambda: Preset(name="t", method="bayer4", palette="BW")
    win._status = lambda *_a, **_k: None

    cc.export_clip(win, "mp4")
    assert not list(tmp_path.glob("*_silent.mp4"))
    assert not list(tmp_path.glob("*.part*"))


def test_clip_export_keeps_silent_when_mux_fails(tmp_path, monkeypatch):
    """A broken soundtrack must not delete the video that was already encoded."""
    pytest.importorskip("imageio_ffmpeg")
    from PySide6.QtWidgets import QMessageBox

    from app.video_io import has_video

    if not has_video():
        pytest.skip("no video backend")
    from app.presets import Preset
    from app.ui import clip_controller as cc

    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)

    track = tmp_path / "track.wav"
    track.write_bytes(b"RIFF0000WAVEnot-really-audio")

    class _Spn:
        def __init__(self, v):
            self._v = v

        def value(self):
            return self._v

    win = type("W", (), {})()
    win._clip_frames = [Image.new("RGB", (32, 24), (5, i, 5)) for i in range(4)]
    win._clip_info = {"path": "x.mp4", "fps": 10, "frames": 4}
    win._clip_start, win._clip_end = 0, 3
    win._clip_audio = str(track)
    win._clip_dither_cache = {}
    win.out_dir = tmp_path
    win.spn_clip_start = _Spn(0)
    win.spn_clip_end = _Spn(3)
    win.spn_clip_fps = _Spn(10)
    win.current_params = lambda: Preset(name="t", method="bayer4", palette="BW")
    win._status = lambda *_a, **_k: None

    cc.export_clip(win, "mp4")
    assert (tmp_path / "x_clip.mp4").is_file()   # silent fallback survives
    assert not list(tmp_path.glob("*.part*"))
