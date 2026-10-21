#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TRAKKART entry point."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication

from app import __version__
from app.ui.main_window import MainWindow


def install_crash_hook(log_path):
    """Uncaught exceptions -> log file + friendly dialog (or stderr headless)."""
    import logging
    import traceback

    def _hook(exc_type, exc, tb):
        try:
            logging.getLogger("trakkart").error(
                "Uncaught:\n%s", "".join(traceback.format_exception(exc_type, exc, tb)))
        except Exception:  # noqa: BLE001
            pass
        try:
            from PySide6.QtWidgets import QMessageBox

            if QApplication.instance() is not None:
                QMessageBox.critical(
                    None, "TRAKKART",
                    f"Something broke (details logged):\n{exc}\n\nSee:\n{log_path}")
                return
        except Exception:  # noqa: BLE001
            pass
        print(f"TRAKKART crashed (details logged): {exc}\nSee: {log_path}")

    sys.excepthook = _hook
    return _hook


def main() -> int:
    from app.log import setup_logging

    log_file = setup_logging()
    install_crash_hook(log_file)
    import logging

    logging.getLogger("trakkart").info("TRAKKART v%s starting", __version__)
    app = QApplication(sys.argv)
    app.setApplicationName("TRAKKART")
    app.setOrganizationName("ShardBeats")
    app.setApplicationVersion(__version__)
    w = MainWindow()
    w.show()
    return app.exec()


if __name__ == "__main__":
    import multiprocessing

    multiprocessing.freeze_support()
    raise SystemExit(main())
