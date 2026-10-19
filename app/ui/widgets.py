"""Custom TRAKKART widgets (MIT): slider with value and double-click reset."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QSlider


class ValueSlider(QSlider):
    """Horizontal QSlider that returns to its default value on double-click."""

    def __init__(self, orientation=Qt.Horizontal, parent=None) -> None:
        super().__init__(orientation, parent)
        self._default = 0

    def setDefault(self, value: int) -> None:  # noqa: N802
        self._default = int(value)
        if self.sliderPosition() == 0 and self.value() == 0:
            pass

    def defaultValue(self) -> int:  # noqa: N802
        return self._default

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        self.setValue(self._default)
        super().mouseDoubleClickEvent(event)
