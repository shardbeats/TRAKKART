"""Custom TRAKKART widgets (MIT): slider with value and double-click reset."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QSlider


def set_warning(widget, on: bool) -> None:
    """Amber flag via a dynamic property (QSS: QLabel[warning=\"true\"])."""
    if bool(widget.property("warning")) == bool(on):
        return
    widget.setProperty("warning", bool(on))
    try:
        widget.style().unpolish(widget)
        widget.style().polish(widget)
    except Exception:  # noqa: BLE001
        pass


class ClickableLabel(QLabel):
    """QLabel that reports left clicks (zoom badge: Fit <-> 100%)."""

    def __init__(self, text: str = "", parent=None) -> None:
        super().__init__(text, parent)
        self.setCursor(Qt.PointingHandCursor)
        self._on_click = None

    def onClick(self, callback) -> None:  # noqa: N802
        """Register the left-click callback (keeps the widget API tiny)."""
        self._on_click = callback

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton and self._on_click is not None:
            self._on_click()
        super().mouseReleaseEvent(event)


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
