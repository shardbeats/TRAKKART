"""TRAKKART image ops: rotate/flip/invert + undo history (cap 20)."""

from __future__ import annotations

from PIL import Image


def rotate_left(img: Image.Image) -> Image.Image:
    return img.transpose(Image.Transpose.ROTATE_90)


def rotate_right(img: Image.Image) -> Image.Image:
    return img.transpose(Image.Transpose.ROTATE_270)


def flip_h(img: Image.Image) -> Image.Image:
    return img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)


def flip_v(img: Image.Image) -> Image.Image:
    return img.transpose(Image.Transpose.FLIP_TOP_BOTTOM)


def invert(img: Image.Image) -> Image.Image:
    from PIL import ImageOps

    return ImageOps.invert(img.convert("RGB"))


class ImageHistory:
    """Undo/redo stacks, cap 20 each. `push` starts a new branch (clears redo)."""

    def __init__(self, limit: int = 20) -> None:
        self.limit = max(1, int(limit))
        self._stack: list[Image.Image] = []
        self._redo: list[Image.Image] = []

    def push(self, img: Image.Image) -> None:
        self._stack.append(img.copy())
        if len(self._stack) > self.limit:
            self._stack.pop(0)
        self._redo.clear()

    def undo(self, current: Image.Image | None = None) -> Image.Image | None:
        """Pop one undo step; stash `current` on the redo stack when given."""
        if not self._stack:
            return None
        if current is not None:
            self._redo.append(current.copy())
            if len(self._redo) > self.limit:
                self._redo.pop(0)
        return self._stack.pop()

    def redo(self, current: Image.Image | None = None) -> Image.Image | None:
        """Pop one redo step; stash `current` back on the undo stack."""
        if not self._redo:
            return None
        if current is not None:
            self._stack.append(current.copy())
            if len(self._stack) > self.limit:
                self._stack.pop(0)
        return self._redo.pop()

    def clear(self) -> None:
        self._stack.clear()
        self._redo.clear()

    def __len__(self) -> int:
        return len(self._stack)

    @property
    def can_undo(self) -> bool:
        return bool(self._stack)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)
