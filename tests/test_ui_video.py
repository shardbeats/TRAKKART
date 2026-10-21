"""Video controller + workers: playback state without real threads."""

from PIL import Image


def _img(size=32):
    im = Image.new("RGB", (size, size))
    px = im.load()
    for y in range(size):
        for x in range(size):
            px[x, y] = ((x * 7) % 256, (y * 11) % 256, 140)
    return im


def _frames(n=3, size=32):
    return [_img(size) for _ in range(n)]


def test_video_spec_and_proxy(window):
    from app.ui import video_controller as vc

    assert vc.proxy_size(window) == 720  # Draft 720p default
    assert vc.preview_size(window) == 720
    s = vc.spec(window)
    assert set(s) == {"size", "mode", "frames", "fps", "pingpong"}
    window.cmb_video_proxy.setCurrentText("Full (doc)")
    assert vc.proxy_size(window) == 0
    # Full doc falls back to the gif anim size (canvas long side).
    assert vc.preview_size(window) == window._gif_anim_size()


def test_video_toggle_playpause_scrub(window):
    from app.ui import video_controller as vc

    window.src = _img()
    window.chk_video.setChecked(True)
    vc.toggle(window)
    assert window._video_on is True
    assert not window._video_bar_widget.isHidden()
    vc.playpause(window)
    assert window._video_playing is False
    assert "Play" in window.btn_video_play.text()
    vc.playpause(window)
    assert window._video_playing is True
    window._video_frames = _frames()
    window._video_idx = 0
    vc.show_frame(window)
    assert window.lbl_video_pos.text() == "1/3"
    vc.scrub(window, 2)
    assert window._video_idx == 2
    assert window.lbl_video_pos.text() == "3/3"
    vc.next_frame(window)  # wraps to 0
    assert window._video_idx == 0
    vc.scrub(window, 99)  # clamps, no crash
    assert window._video_idx == 2
    window.chk_video.setChecked(False)
    vc.toggle(window)
    assert window._video_on is False


def test_video_fps_changed_only_retimes(window):
    from app.ui import video_controller as vc

    window.cmb_video_fps.setCurrentText("30")
    vc.fps_changed(window)
    assert window._video_timer.interval() == 1000 // 30


def test_video_on_done_and_error(window):
    from app.ui import video_controller as vc

    window._video_token = 4
    vc.on_done(window, _frames(), 999)  # stale token: ignored
    assert window._video_frames == []
    vc.on_done(window, _frames(), 4)
    assert len(window._video_frames) == 3
    assert window.result is not None
    assert window.sld_video.maximum() == 2
    assert "VIDEO" in window.lbl_res_title.text()
    vc.on_error(window, "boom", 999)  # stale: silent
    assert "boom" not in window.lbl_status.text()
    vc.on_error(window, "boom", 4)
    assert "boom" in window.lbl_status.text()


def test_video_start_async_and_pending(window, monkeypatch):
    from app.ui import preview_controller as pc
    from app.ui import preview_worker as pw
    from app.ui import video_controller as vc

    window.src = _img(48)
    window._video_on = True

    calls = {}

    class FakeSig:
        def __init__(self):
            self.slot = None

        def connect(self, slot):
            self.slot = slot

    class FakeWorker:
        finished_ok = FakeSig()
        finished_err = FakeSig()

        def __init__(self, *a, **k):
            calls["created"] = True
            self.finished_ok = FakeSig()
            self.finished_err = FakeSig()

        def isRunning(self):
            return calls.get("busy", False)

        def start(self):
            calls["started"] = True

    monkeypatch.setattr(pw, "VideoWorker", FakeWorker)
    calls["busy"] = True
    window._video_worker = FakeWorker()
    vc.start_async(window)  # worker busy -> returns, constructs nothing new
    assert calls == {"busy": True, "created": True}
    assert window.result is None  # nothing rendered yet
    calls.clear()
    window._video_worker = None
    vc.start_async(window)  # free -> constructs, connects, starts
    assert calls.get("created") is True and calls.get("started") is True

    # Still preview: async path with a busy worker marks pending.
    window._preview_worker = FakeWorker()
    calls["busy"] = True
    pc.start_async(window)
    assert window._preview_pending is True
    # ...and error with pending retries (fake still busy -> pending again, no loop).
    pc.on_error(window, "x", window._preview_token)
    assert window._preview_pending is True


def test_video_worker_work_direct():
    from app.presets import Preset
    from app.ui.preview_worker import VideoWorker

    got = []
    w = VideoWorker(_img(48), Preset(name="t", method="bayer4"), 64, 2, "mix", False, 7)
    w.finished_ok.connect(lambda frames, token: got.append((frames, token)))
    w.work()
    assert len(got) == 1
    frames, token = got[0]
    assert token == 7 and len(frames) == 2
    assert all(f.size[0] <= 64 and f.size[1] <= 64 for f in frames)


def test_preview_worker_work_and_params():
    from app.presets import Preset
    from app.ui.preview_worker import PreviewWorker, preview_params

    small, pixel = preview_params(_img(600), {"pixel_size": 4}, max_side=640)
    assert max(small.size) <= 640 and pixel >= 1
    got = []
    preset = Preset(name="t", method="bayer4", palette="SLIME", pixel_size=1)
    w = PreviewWorker(_img(48), preset.to_render_kwargs(), 3)
    w.finished_ok.connect(lambda qimg, pil, token: got.append((pil, token)))
    w.finished_err.connect(lambda msg, token: got.append(("err", msg)))
    w.work()
    assert len(got) == 1 and got[0][1] == 3
    assert got[0][0].size == (48, 48)


def test_preview_controller_branches(window):
    from app.ui import preview_controller as pc

    window.src = _img(32)
    pc.render_still(window)  # small -> sync path
    assert window.result is not None
    # Compare mode shows ORIGINAL.
    window._comparing = True
    pc.show(window, window.src, window.result)
    assert "ORIGINAL" in window.lbl_res_title.text()
    window._comparing = False
    pc.show(window, window.src, window.result)
    assert "DITHER" in window.lbl_res_title.text()
    # Done with stale token / pending / error paths.
    pc.on_done(window, None, None, window._preview_token + 1)
    from app.ui.qt_image import pil_to_qimage

    pc.on_done(window, pil_to_qimage(window.result), window.result.copy(),
               window._preview_token)
    assert window.lbl_status.text() == "Preview ready"
    window._preview_pending = True
    pc.on_error(window, "e", window._preview_token)  # pending -> retries, no crash
    pc.on_error(window, "e2", window._preview_token + 5)  # stale token: silent


def test_duration_label_follows_frames_and_fps(window):
    from app.ui import video_controller as vc

    assert vc.duration_seconds(window) >= 0.0
    window.cmb_video_frames.setCurrentText("8")
    window.cmb_video_fps.setCurrentText("24")
    assert window.lbl_duration.text() == "= 0.3s loop"
    window.cmb_video_fps.setCurrentText("12")
    assert window.cmb_video_frames.currentText() == "8"
    assert window.lbl_duration.text() == "= 0.7s loop"


def test_anim_combo_inserts_sorted_without_dupes(window):
    from app.ui.params_binding import set_anim_combo

    items = [window.cmb_video_fps.itemText(i) for i in range(window.cmb_video_fps.count())]
    assert items[0] == "8"  # preset default is a first-class entry, not a stray
    set_anim_combo(window.cmb_video_fps, 25)
    items = [window.cmb_video_fps.itemText(i) for i in range(window.cmb_video_fps.count())]
    assert items == sorted(items, key=int) and items.count("25") == 1
    set_anim_combo(window.cmb_video_fps, 25)
    items = [window.cmb_video_fps.itemText(i) for i in range(window.cmb_video_fps.count())]
    assert items.count("25") == 1


def test_preset_apply_syncs_duration(window):
    window._apply_preset("SLIME_FS")
    frames = window._anim_combo_int(window.cmb_video_frames, 6, 2, 24)
    fps = window._anim_combo_int(window.cmb_video_fps, 8, 2, 60)
    assert window.lbl_duration.text() == f"= {frames / max(1, fps):.1f}s loop"
