"""First-run + Help tutorial dialog: 5 steps, no network, no assets."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)


class TutorialDialog(QDialog):
    def __init__(self, parent=None) -> None:
        from app.tutorial import STEPS

        super().__init__(parent)
        self.setWindowTitle("TRAKKART quick tour")
        self.setMinimumWidth(460)
        self._steps = list(STEPS)
        self._idx = 0

        col = QVBoxLayout(self)
        self.lbl_title = QLabel()
        self.lbl_title.setObjectName("titleLabel")
        self.lbl_title.setWordWrap(True)
        col.addWidget(self.lbl_title)
        self.lbl_body = QLabel()
        self.lbl_body.setWordWrap(True)
        col.addWidget(self.lbl_body, 1)
        self.lbl_pos = QLabel()
        self.lbl_pos.setObjectName("subtitleLabel")
        col.addWidget(self.lbl_pos)

        bar = QHBoxLayout()
        self.btn_back = QPushButton("◀ Back")
        self.btn_back.clicked.connect(self._back)
        bar.addWidget(self.btn_back)
        bar.addStretch()
        self.btn_skip = QPushButton("Skip")
        self.btn_skip.clicked.connect(self.reject)
        bar.addWidget(self.btn_skip)
        self.btn_next = QPushButton("Next ▶")
        self.btn_next.setObjectName("exportBtn")
        self.btn_next.clicked.connect(self._next)
        bar.addWidget(self.btn_next)
        col.addLayout(bar)
        self._sync()

    def _sync(self) -> None:
        title, body = self._steps[self._idx]
        self.lbl_title.setText(f"{self._idx + 1}. {title}")
        self.lbl_body.setText(body)
        self.lbl_pos.setText(f"{self._idx + 1}/{len(self._steps)}")
        self.btn_back.setEnabled(self._idx > 0)
        self.btn_next.setText("Done" if self._idx == len(self._steps) - 1 else "Next ▶")

    def _back(self) -> None:
        self._idx = max(0, self._idx - 1)
        self._sync()

    def _next(self) -> None:
        if self._idx >= len(self._steps) - 1:
            self.accept()
        else:
            self._idx += 1
            self._sync()


__all__ = ["TutorialDialog"]
