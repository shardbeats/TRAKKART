"""Custom palette editor — swatches, roles and real usage.

The panel used to say only "N colors": cryptic. Here each color is shown
(swatch + hex), has a luminance role (shadow/mid/light) and shows
its approximate usage % over the current canvas. The engine maps by closest
color, so the honest "role" is: luminance range + real weight.
"""

from __future__ import annotations

from PIL import Image
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

MAX_COLORS = 16
MIN_COLORS = 2


def rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02X}{:02X}{:02X}".format(*rgb)


def luminance(rgb: tuple[int, int, int]) -> float:
    r, g, b = rgb
    return 0.299 * r + 0.587 * g + 0.114 * b


def luminance_roles(colors: list[tuple[int, int, int]]) -> list[str]:
    """Role by luminance range: shadow … mid k … light."""
    n = len(colors)
    if n == 0:
        return []
    if n == 1:
        return ["single"]
    lum = [luminance(c) for c in colors]
    order = sorted(range(n), key=lambda i: lum[i])
    roles = [""] * n
    roles[order[0]] = "shadow"
    roles[order[-1]] = "light"
    for k, idx in enumerate(order[1:-1], start=1):
        roles[idx] = f"mid {k}"
    return roles


def palette_usage(img: Image.Image | None, palette: list[tuple[int, int, int]]) -> list[float]:
    """% of pixels that would fall on each color (nearest RGB, 160px preview).

    Cheap estimate to guide ("which part each color is for"),
    not the final render. No image or no palette returns zeros.
    """
    import numpy as np

    if img is None or not palette:
        return [0.0] * len(palette)
    small = img.convert("RGB")
    m = max(small.size)
    if m > 160:
        f = 160.0 / m
        small = small.resize((max(1, round(small.width * f)), max(1, round(small.height * f))), Image.BICUBIC)
    arr = np.asarray(small, dtype=np.float32).reshape(-1, 3)
    pal = np.asarray(palette, dtype=np.float32)
    dist = ((arr[:, None, :] - pal[None, :, :]) ** 2).sum(axis=-1)
    idx = dist.argmin(axis=1)
    counts = np.bincount(idx, minlength=len(pal)).astype(float)
    total = counts.sum()
    if total <= 0:
        return [0.0] * len(palette)
    return (counts / total * 100.0).tolist()


class ColorSwatch(QPushButton):
    """Square color button. Left click emits `picked(index`)."""

    picked = Signal(int)

    def __init__(self, rgb: tuple[int, int, int], index: int, size: int = 28, parent=None) -> None:
        super().__init__(parent)
        self._index = index
        self.setFixedSize(size, size)
        self.setCursor(Qt.PointingHandCursor)
        self.set_rgb(rgb)
        self.clicked.connect(lambda: self.picked.emit(self._index))

    def set_rgb(self, rgb: tuple[int, int, int]) -> None:
        self.setStyleSheet(
            f"background-color: {rgb_to_hex(rgb)}; border: 1px solid #666; border-radius: 3px;"
        )
        self.setToolTip(rgb_to_hex(rgb))


class CustomPaletteDialog(QDialog):
    """Custom palette editor: view, edit, reorder, sort by light.

    Works on a copy; `colors` only valid after Accept.
    `preview` is a small image already cropped to canvas (or None).
    """

    def __init__(
        self,
        colors: list[tuple[int, int, int]],
        preview: Image.Image | None = None,
        locks: list[bool] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Custom palette")
        self.setMinimumWidth(500)
        self.colors: list[tuple[int, int, int]] = [tuple(c) for c in colors]
        self.locks: list[bool] = list(locks) if locks else [False] * len(self.colors)
        if len(self.locks) != len(self.colors):
            self.locks = [False] * len(self.colors)
        self.preview = preview

        col = QVBoxLayout(self)
        hint = QLabel("Double-click a swatch to edit. Order only breaks ties (nearest color wins).")
        hint.setWordWrap(True)
        col.addWidget(hint)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumHeight(200)
        scroll.setMaximumHeight(420)
        host = QWidget()
        self.grid = QGridLayout(host)
        self.grid.setColumnStretch(1, 1)
        scroll.setWidget(host)
        col.addWidget(scroll, 1)

        self.lbl_count = QLabel()
        col.addWidget(self.lbl_count)

        bar = QHBoxLayout()
        self.btn_add = QPushButton("+ Add")
        self.btn_add.clicked.connect(self._add)
        bar.addWidget(self.btn_add)
        self.btn_sort = QPushButton("Sort by light")
        self.btn_sort.setToolTip("Dark → light by luminance")
        self.btn_sort.clicked.connect(self._sort)
        bar.addWidget(self.btn_sort)
        self.btn_shuffle = QPushButton("🔀 Shuffle")
        self.btn_shuffle.setToolTip("Shuffle unlocked only (🔒 stay)")
        self.btn_shuffle.clicked.connect(self._shuffle)
        bar.addWidget(self.btn_shuffle)
        bar.addStretch()
        self.btn_ok = QPushButton("Done")
        self.btn_ok.setObjectName("exportBtn")
        self.btn_ok.clicked.connect(self.accept)
        bar.addWidget(self.btn_ok)
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        bar.addWidget(self.btn_cancel)
        col.addLayout(bar)

        self._rebuild()

    # -- modelo --
    def _rebuild(self) -> None:
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        roles = luminance_roles(self.colors)
        usage = palette_usage(self.preview, self.colors)
        for i, rgb in enumerate(self.colors):
            sw = ColorSwatch(rgb, i, size=34)
            sw.setToolTip(f"{rgb_to_hex(rgb)} · {roles[i]} · ~{usage[i]:.0f}% — click to edit")
            sw.picked.connect(self._edit)
            self.grid.addWidget(sw, i, 0)
            hex_lbl = QLabel(rgb_to_hex(rgb))
            hex_lbl.setMinimumWidth(70)
            self.grid.addWidget(hex_lbl, i, 1)
            self.grid.addWidget(QLabel(roles[i]), i, 2)
            use_lbl = QLabel(f"~{usage[i]:.0f}%" if self.preview is not None else "—")
            use_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            use_lbl.setMinimumWidth(48)
            self.grid.addWidget(use_lbl, i, 3)
            btn_up = QPushButton("▲")
            btn_up.setFixedWidth(32)
            btn_up.setToolTip("Move up")
            btn_up.clicked.connect(lambda _=False, _i=i: self._move(_i, -1))
            self.grid.addWidget(btn_up, i, 4)
            btn_down = QPushButton("▼")
            btn_down.setFixedWidth(32)
            btn_down.setToolTip("Move down")
            btn_down.clicked.connect(lambda _=False, _i=i: self._move(_i, 1))
            self.grid.addWidget(btn_down, i, 5)
            btn_del = QPushButton("✕")
            btn_del.setFixedWidth(32)
            btn_del.setToolTip("Remove this color")
            btn_del.clicked.connect(lambda _=False, _i=i: self._remove(_i))
            self.grid.addWidget(btn_del, i, 6)
            btn_lock = QPushButton("🔒" if self.locks[i] else "🔓")
            btn_lock.setFixedWidth(36)
            btn_lock.setCheckable(True)
            btn_lock.setChecked(bool(self.locks[i]))
            btn_lock.setToolTip("Lock against shuffle")
            btn_lock.toggled.connect(lambda on, _i=i, _b=btn_lock: self._lock(_i, on, _b))
            self.grid.addWidget(btn_lock, i, 7)
        n = len(self.colors)
        if n < MIN_COLORS:
            state = f"need {MIN_COLORS}–{MAX_COLORS} (custom ignored, combo is used)"
        else:
            state = "custom active"
        self.lbl_count.setText(f"{n}/{MAX_COLORS} · {state}")
        self.btn_add.setEnabled(n < MAX_COLORS)

    # -- slots --
    def _edit(self, i: int) -> None:
        from PySide6.QtWidgets import QColorDialog

        from PySide6.QtGui import QColor

        cur = self.colors[i]
        color = QColorDialog.getColor(QColor(*cur), self, "Edit color")
        if not color.isValid():
            return
        rgb = (color.red(), color.green(), color.blue())
        if rgb in self.colors and rgb != cur:
            return  # do not duplicate silently: ignored like in the panel
        self.colors[i] = rgb
        self._rebuild()

    def _remove(self, i: int) -> None:
        del self.colors[i]
        del self.locks[i]
        self._rebuild()

    def _lock(self, i: int, on: bool, btn) -> None:
        self.locks[i] = bool(on)
        btn.setText("🔒" if on else "🔓")

    def _shuffle(self) -> None:
        import random

        free = [i for i, locked in enumerate(self.locks) if not locked]
        if len(free) < 2:
            return
        pool = [self.colors[i] for i in free]
        random.shuffle(pool)
        for i, c in zip(free, pool):
            self.colors[i] = c
        self._rebuild()

    def _move(self, i: int, delta: int) -> None:
        j = i + delta
        if 0 <= j < len(self.colors):
            self.colors[i], self.colors[j] = self.colors[j], self.colors[i]
            self._rebuild()

    def _sort(self) -> None:
        # Sort unlocked by light; locked ones stay in their row.
        free = [i for i, locked in enumerate(self.locks) if not locked]
        ordered = sorted((self.colors[i] for i in free), key=luminance)
        for i, c in zip(free, ordered):
            self.colors[i] = c
        self._rebuild()

    def _add(self) -> None:
        from PySide6.QtWidgets import QColorDialog

        if len(self.colors) >= MAX_COLORS:
            return
        color = QColorDialog.getColor(self, "Add color")
        if not color.isValid():
            return
        rgb = (color.red(), color.green(), color.blue())
        if rgb not in self.colors:
            self.colors.append(rgb)
            self.locks.append(False)
        self._rebuild()


__all__ = [
    "MAX_COLORS",
    "MIN_COLORS",
    "rgb_to_hex",
    "luminance",
    "luminance_roles",
    "palette_usage",
    "ColorSwatch",
    "CustomPaletteDialog",
]
