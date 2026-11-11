"""About dialog: version + MIT + offline note. No network, no links."""

from __future__ import annotations


def about_text() -> str:
    from app import __version__

    return (
        f"TRAKKART v{__version__}\n"
        "Offline cover art studio · ShardBeats TRAKK SUITE\n"
        "\n"
        "Dither still images · Animate them · Export the bundle.\n"
        "No accounts, no cloud.\n"
        "\n"
        "TRAKKART code: MIT (see LICENSE + THIRD-PARTY-NOTICES.md).\n"
        "Bundled FFmpeg: GPLv3 (licenses/GPL-3.0.txt)."
    )


def show_about(win) -> None:
    from PySide6.QtWidgets import QMessageBox

    QMessageBox.about(win, "About TRAKKART", about_text())


def show_manual(win) -> None:
    """Open the bundled MANUAL.md (F1). Falls back to a warning if missing."""
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QDesktopServices
    from PySide6.QtWidgets import QMessageBox

    from app.paths import bundle_path

    manual = bundle_path("MANUAL.md")
    if manual.is_file():
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(manual)))
        win._status(f"Manual: {manual}")
    else:
        QMessageBox.information(win, "TRAKKART", "MANUAL.md not found next to the app.")
        win._status("Manual not found")


def show_logs(win) -> None:
    """Reveal the data folder (prefs, db, trakkart.log) in the file manager."""
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QDesktopServices

    from app.log import log_path

    try:
        folder = log_path().parent
        folder.mkdir(parents=True, exist_ok=True)
    except Exception:  # noqa: BLE001
        win._status("Logs unavailable")
        return
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))
    win._status(f"Logs: {folder}")


__all__ = ["about_text", "show_about", "show_logs", "show_manual"]
