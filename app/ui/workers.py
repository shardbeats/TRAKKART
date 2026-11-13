"""Dedicated QThread workers — batch without freezing the UI."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal

from app.batch import batch_process
from app.presets import Preset
from app.ui.base_worker import WorkerBase


class BatchWorker(WorkerBase):
    """Run batch_process on a worker thread with progress."""

    progress = Signal(int, int, str)  # done, total, filename
    finished = Signal(list)           # results
    error = Signal(str)

    def __init__(
        self,
        input_dir: str | Path,
        out_dir: str | Path,
        preset: Preset,
        skip_existing: bool = True,
        store=None,
        jobs: int = 1,
        cancel: list | None = None,
        parent=None,
        seed_mode: str = "off",
    ) -> None:
        super().__init__(parent)
        self.input_dir = Path(input_dir)
        self.out_dir = Path(out_dir)
        self.preset = preset
        self.skip_existing = skip_existing
        self.store = store
        self.jobs = jobs
        self.cancel = cancel
        self.seed_mode = seed_mode

    def work(self) -> None:
        results = batch_process(
            self.input_dir,
            self.out_dir,
            self.preset,
            skip_existing=self.skip_existing,
            progress_cb=self.progress.emit,
            store=self.store,
            jobs=self.jobs,
            cancel=self.cancel,
            seed_mode=self.seed_mode,
        )
        self.finished.emit(results)

    def _report_error(self, exc: Exception) -> None:
        from app.log import report_error

        try:
            preset_name = str(getattr(self.preset, "name", "?"))
        except Exception:  # noqa: BLE001
            preset_name = "?"
        rid = report_error("batch", exc,
                           {"preset": preset_name,
                            "input": getattr(self.input_dir, "name", "?"),
                            "output": getattr(self.out_dir, "name", "?"),
                            "jobs": self.jobs})
        self.error.emit(f"[{rid}] {exc}")


class ExportWorker(WorkerBase):
    """Run export_full on a worker thread (no GUI freeze on GIF/MP4).

    Snapshots (src copy, preset, morph_src copies) are taken by the
    caller; the worker never touches live widgets. Emits paths dict
    on success (skipped included as empty paths + skipped flag).
    """

    finished_ok = Signal(object, object)  # paths dict, skipped flag
    error = Signal(str)

    def __init__(self, src, preset, out_dir, base: str = "trakkart",
                 store=None, preset_name: str = "", selection=None,
                 overwrite: str = "rename",
                 gif_frames: int = 6, gif_mode: str = "both",
                 gif_fps: int = 8, gif_size: int = 1200,
                 gif_pingpong: bool = False,
                 size: int = 3000, format: str = "png", quality: int = 90,
                 mp4: bool = False, mp4_fps: int = 8,
                 mp4_size: str = "1080p", mp4_encoder: str = "libx264",
                 webp: bool = False,
                 sep: bool = False, sp404: bool = False,
                 morph_src=None, parent=None) -> None:
        super().__init__(parent)
        self.src = src
        self.preset = preset
        self.out_dir = Path(out_dir)
        self.base = str(base)
        self.store = store
        self.preset_name = str(preset_name)
        self.selection = selection
        self.overwrite = str(overwrite)
        self.gif_frames = int(gif_frames)
        self.gif_mode = str(gif_mode)
        self.gif_fps = int(gif_fps)
        self.gif_size = int(gif_size)
        self.gif_pingpong = bool(gif_pingpong)
        self.size = int(size)
        self.format = str(format)
        self.quality = int(quality)
        self.mp4 = bool(mp4)
        self.mp4_fps = int(mp4_fps)
        self.mp4_size = str(mp4_size)
        self.mp4_encoder = str(mp4_encoder or "libx264")
        self.webp = bool(webp)
        self.sep = bool(sep)
        self.sp404 = bool(sp404)
        self.morph_src = morph_src

    def work(self) -> None:
        from app.services.export_service import export_full

        paths, skipped = export_full(
            self.src, self.preset, self.out_dir, base=self.base,
            store=self.store, preset_name=self.preset_name,
            selection=self.selection, overwrite=self.overwrite,
            gif_frames=self.gif_frames, gif_mode=self.gif_mode,
            gif_fps=self.gif_fps, gif_size=self.gif_size,
            gif_pingpong=self.gif_pingpong, size=self.size,
            format=self.format, quality=self.quality, mp4=self.mp4,
            mp4_fps=self.mp4_fps, mp4_size=self.mp4_size,
            mp4_codec=self.mp4_encoder,
            webp=self.webp, sep=self.sep, morph_src=self.morph_src,
            sp404=self.sp404,
        )
        self.finished_ok.emit(dict(paths), bool(skipped))

    def _report_error(self, exc: Exception) -> None:
        from app.log import report_error

        try:
            base = str(getattr(self, "base", "?"))
        except Exception:  # noqa: BLE001
            base = "?"
        rid = report_error("export", exc, {"base": base})
        self.error.emit(f"[{rid}] {exc}")
