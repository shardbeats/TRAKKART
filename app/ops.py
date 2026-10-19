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
    """State stack for undo, cap 20."""

    def __init__(self, limit: int = 20) -> None:
        self.limit = max(1, int(limit))
        self._stack: list[Image.Image] = []

    def push(self, img: Image.Image) -> None:
        self._stack.append(img.copy())
        if len(self._stack) > self.limit:
            self._stack.pop(0)

    def undo(self) -> Image.Image | None:
        if not self._stack:
            return None
        return self._stack.pop()

    def clear(self) -> None:
        self._stack.clear()

    def __len__(self) -> int:
        return len(self._stack)
