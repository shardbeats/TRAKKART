"""Shared dialog widgets: one implementation for every dialog.

Export / Batch / Settings all needed the same rows (format+quality,
jobs, folder browse, gif-spec normalize + summary). Duplicated 2-4x
before; now built here so a range/tooltip/mode change happens once.
Pure Qt builders + pure normalize/summary helpers (testable headless
except the widget builders, which need a QApplication).
"""

from __future__ import annotations


def normalize_gif_spec(frames=6, mode: str = "both", fps: int = 8,
                       pingpong: bool = False) -> dict:
    """Clamped gif spec dict (dialogs must never feed the engine garbage)."""
    from app.gif import GIF_MODES

    try:
        n_frames = max(2, min(256, int(frames)))
    except (TypeError, ValueError):
        n_frames = 6
    try:
        n_fps = max(2, min(60, int(fps)))
    except (TypeError, ValueError):
        n_fps = 8
    return {
        "frames": n_frames,
        "mode": mode if mode in GIF_MODES else "both",
        "fps": n_fps,
        "pingpong": bool(pingpong),
    }


def gif_summary(spec: dict, suffix: str = "") -> str:
    """One-line spec text shared by the export/batch gif labels."""
    g = dict(spec or {})
    try:
        frames = max(2, min(256, int(g.get("frames", 6))))
        fps = max(2, min(60, int(g.get("fps", 8))))
        secs = frames / max(1, fps)
    except (TypeError, ValueError):
        frames, fps, secs = 6, 8, 0.75
    text = (f"{g.get('frames', 6)}f · {g.get('mode', 'both')} · "
            f"{g.get('fps', 8)}fps · {secs:.1f}s"
            f"{' · ping-pong' if g.get('pingpong') else ''}")
    if secs > 4.0:
        text += " · long - prefer MP4"
    return f"{text} · {suffix}" if suffix else text


def build_format_quality(current_format: str = "png", quality: int = 90):
    """(Format combo, Quality spin) with shared ranges/defaults."""
    from PySide6.QtWidgets import QComboBox, QSpinBox

    from app.exporter import EXPORT_FORMATS

    cmb = QComboBox()
    cmb.addItems(list(EXPORT_FORMATS))
    cmb.setCurrentText(current_format if current_format in EXPORT_FORMATS else "png")
    spn = QSpinBox()
    spn.setRange(1, 100)
    try:
        spn.setValue(max(1, min(100, int(quality))))
    except (TypeError, ValueError):
        spn.setValue(90)
    spn.setSuffix("%")
    return cmb, spn


def build_jobs_spin(jobs: int = 1):
    """Batch jobs spin (1-8) with the shared tooltip."""
    from PySide6.QtWidgets import QSpinBox

    spn = QSpinBox()
    spn.setRange(1, 8)
    try:
        spn.setValue(max(1, min(8, int(jobs))))
    except (TypeError, ValueError):
        spn.setValue(1)
    spn.setToolTip("1 = sequential (safe). >1 = multiprocessing.")
    return spn


def build_folder_row(caption: str, initial: str = "", parent=None, on_browse=None,
                     editable: bool = False):
    """(row layout, edit, browse button) for folder pickers.

    Readonly by default (Browse-only, no invalid typed paths); pass
    `editable=True` to keep manual typing. Pass `on_browse` to override
    the default chooser. Callers connect `edit.textChanged` for validation.
    """
    from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton

    row = QHBoxLayout()
    row.addWidget(QLabel(caption))
    edit = QLineEdit(str(initial or ""), parent)
    edit.setReadOnly(not editable)
    edit.setPlaceholderText("Choose folder…")
    row.addWidget(edit, 1)
    btn = QPushButton("Browse...")
    if on_browse is not None:
        btn.clicked.connect(on_browse)
    else:
        def _browse() -> None:
            from pathlib import Path

            start = edit.text().strip() or str(Path.home())
            title = f"Choose {caption.rstrip(':').strip().lower() or 'folder'}"
            d = QFileDialog.getExistingDirectory(parent, title, start)
            if d:
                edit.setText(d)

        btn.clicked.connect(_browse)
    row.addWidget(btn)
    return row, edit, btn


__all__ = ["build_folder_row", "build_format_quality", "build_jobs_spin",
           "gif_summary", "normalize_gif_spec"]
