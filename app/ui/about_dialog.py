"""About dialog: version + MIT + offline note. No network, no links."""

from __future__ import annotations


def about_text() -> str:
    from app import __version__

    return (
        f"TRAKKART v{__version__}\n"
        "Offline dither cover generator · ShardBeats TRAKK family\n"
        "\n"
        "100% original MIT code (clean-room, no third-party GPL).\n"
        "Portable and offline: settings live next to the app.\n"
        "\n"
        "Image → method + palette + pixel → preview → bundle."
    )


def show_about(win) -> None:
    from PySide6.QtWidgets import QMessageBox

    QMessageBox.about(win, "About TRAKKART", about_text())


__all__ = ["about_text", "show_about"]
