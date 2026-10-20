"""Clip browser: pick the poster frame of an imported clip.

Small and modal: slider scrubs the (capped, proxy-size) clip frames,
the label shows f i/N + dims. Use frame -> dialog returns the index;
Clear clip -> caller drops win.clip_frames entirely.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
)


class ClipBrowserDialog(QDialog):
    """Returns (action, index): action in {"use", "clear", ""}."""

    def __init__(self, frames, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Clip frames")
        self.setMinimumWidth(420)
        self.frames = list(frames or [])
        self.action = ""
        self.index = 0

        col = QVBoxLayout(self)
        self.lbl = QLabel()
        self.lbl.setAlignment(Qt.AlignCenter)
        col.addWidget(self.lbl)
        self.sld = QSlider(Qt.Horizontal)
        self.sld.setRange(0, max(0, len(self.frames) - 1))
        self.sld.setValue(0)
        self.sld.valueChanged.connect(self._sync)
        col.addWidget(self.sld)

        bar = QHBoxLayout()
        self.btn_use = QPushButton("Use frame")
        self.btn_use.setObjectName("exportBtn")
        self.btn_use.clicked.connect(self._use)
        bar.addWidget(self.btn_use)
        self.btn_clear = QPushButton("Clear clip")
        self.btn_clear.setToolTip("Drop the clip, back to still image")
        self.btn_clear.clicked.connect(self._clear)
        bar.addWidget(self.btn_clear)
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        bar.addWidget(self.btn_cancel)
        col.addLayout(bar)
        self._sync(0)

    def _sync(self, v: int) -> None:
        self.index = max(0, min(len(self.frames) - 1, int(v)))
        if self.frames:
            f = self.frames[self.index]
            self.lbl.setText(f"f{self.index + 1}/{len(self.frames)} · {f.width}x{f.height}")
        else:
            self.lbl.setText("no frames")

    def _use(self) -> None:
        self.action = "use"
        self.accept()

    def _clear(self) -> None:
        self.action = "clear"
        self.accept()


__all__ = ["ClipBrowserDialog"]
