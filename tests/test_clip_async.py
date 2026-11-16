"""Pins for async clip preview (P0): worker pixels, tokens, coalescing.

No real threads here: ClipFrameWorker is faked (signals fired by hand),
so the state machine is deterministic. Thread-safety itself is covered
by closeEvent joining _clip_worker like every other worker.
"""

from __future__ import annotations


class _Sig:
    def __init__(self):
        self.cbs = []

    def connect(self, fn):
        self.cbs.append(fn)

    def fire(self, *a):
        for fn in list(self.cbs):
            fn(*a)


class _FakeWorker:
    launched = []

    def __init__(self, frame, preset, index, n, key, token,
                 envelopes=None, dpi=300, parent=None):
        self.captured = {"index": int(index), "n": int(n), "key": key,
                         "token": int(token), "envelopes": dict(envelopes or {})}
        self.finished_ok = _Sig()
        self.finished_err = _Sig()
        self._running = True
        _FakeWorker.launched.append(self)

    def isRunning(self):
        return self._running

    def start(self):
        pass

    def finish(self, image):
        self._running = False
        self.finished_ok.fire(image, self.captured["index"],
                              self.captured["key"], self.captured["token"])


def _fake_env(monkeypatch):
    from app.ui import clip_controller as cc

    _FakeWorker.launched.clear()
    retired = []
    monkeypatch.setattr("app.ui.preview_worker.ClipFrameWorker", _FakeWorker)
    import app.ui.thread_safe as _ts

    monkeypatch.setattr(_ts, "retire", lambda w: retired.append(w))
    return cc, retired


def _open_clip(window):
    from PIL import Image as Img

    from app.ui import clip_controller as cc

    gif = window.out_dir.parent / "async.gif"
    frames = [Img.new("RGB", (48, 48), (i * 40 % 256, 30, 90)) for i in range(6)]
    frames[0].save(str(gif), save_all=True, append_images=frames[1:],
                   duration=100, loop=0)
    assert cc.open_path(window, gif) is True
    return gif


def test_worker_pixels_match_sync(window, monkeypatch):
    from app.ui.preview_worker import render_clip_frame

    _open_clip(window)
    preset = window.current_params()
    frame = window._clip_frames[2]
    assert (render_clip_frame(frame, preset, 2, 6).tobytes()
            == render_clip_frame(frame, preset, 2, 6).tobytes())
    env = {"grain": {"kind": "ramp", "v0": 0, "v1": 100.0}}
    a = render_clip_frame(frame, preset, 0, 6, env)
    b = render_clip_frame(frame, preset, 5, 6, env)
    assert a.tobytes() != b.tobytes()  # progress actually moves


def test_recipe_key_includes_envelopes(window):
    from app.ui import clip_controller as cc

    _open_clip(window)
    flat = cc._recipe_key(window)
    window._envelopes = {"grain": {"kind": "ramp", "v0": 0, "v1": 100.0}}
    assert cc._recipe_key(window) != flat


def test_preview_applies_envelopes(window):
    from app.ui import clip_controller as cc

    _open_clip(window)
    flat = cc.dithered_frame(window, 5)
    window._clip_dither_cache.clear()
    window._envelopes = {"grain": {"kind": "ramp", "v0": 0, "v1": 100.0}}
    curved = cc.dithered_frame(window, 5)
    assert curved.tobytes() != flat.tobytes()


def test_request_coalesces_and_drains(window, monkeypatch):
    from app.ui.preview_worker import render_clip_frame

    cc, _retired = _fake_env(monkeypatch)
    _open_clip(window)
    # open_path stops (token bump) then scrubs 0 -> fake#1 in flight.
    t0 = int(window._clip_token)
    assert len(_FakeWorker.launched) == 1
    assert _FakeWorker.launched[0].captured["token"] == t0
    # Rapid scrub: no new thread, pending just moves.
    assert cc.scrub(window, 2) is None
    assert window._clip_pending == 2
    assert cc.scrub(window, 5) is None
    assert len(_FakeWorker.launched) == 1
    assert window._clip_pending == 5
    # Slider follows now (async contract), canvas waits for pixels.
    assert int(window.sld_clip.value()) == 5
    # fake#1 lands: stale index -> cached, not painted; pending drains.
    img0 = render_clip_frame(window._clip_frames[0], window.current_params(),
                             0, 6, window._envelopes)
    _FakeWorker.launched[0].finish(img0)
    assert len(_FakeWorker.launched) == 2  # pending 5 launched (token t0+1)
    assert _FakeWorker.launched[1].captured["token"] == t0 + 1
    assert window.sld_clip.value() == 5
    # fake#2 lands on the wanted index -> painted.
    img5 = render_clip_frame(window._clip_frames[5], window.current_params(),
                             5, 6, window._envelopes)
    _FakeWorker.launched[1].finish(img5)
    assert window.lbl_res.pixmap() is not None
    assert window._clip_pending is None


def test_stale_token_never_paints(window, monkeypatch):
    from PIL import Image as Img

    from app.ui import clip_controller as cc

    painted = []
    monkeypatch.setattr(cc, "_paint_clip_frame",
                        lambda w, image, idx: painted.append(int(idx)))
    _fake_env(monkeypatch)
    _open_clip(window)
    w0 = _FakeWorker.launched[0]
    cc.request_clip_frame(window, 4)  # coalesced behind fake#0
    cc.stop(window)  # pause/close bumps the token
    w0.finish(Img.new("RGB", (48, 48), (9, 9, 9)))
    assert painted == []
    assert 4 not in (window._clip_dither_cache or {})
