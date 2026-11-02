#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TRAKKART entry point."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import __version__


def install_crash_hook(log_path):
    """Uncaught exceptions -> error report + friendly dialog (or stderr headless)."""
    import logging
    import traceback

    def _hook(exc_type, exc, tb):
        try:
            from app.log import friendly_message, report_error

            rid = report_error("crash", exc if isinstance(exc, BaseException) else RuntimeError(str(exc)))
            hint = friendly_message(exc)
        except Exception:  # noqa: BLE001
            rid, hint = "?", str(exc)
            try:
                logging.getLogger("trakkart").error(
                    "Uncaught:\n%s", "".join(traceback.format_exception(exc_type, exc, tb)))
            except Exception:  # noqa: BLE001
                pass
        try:
            from PySide6.QtWidgets import QApplication, QMessageBox

            if QApplication.instance() is not None:
                QMessageBox.critical(
                    None, "TRAKKART",
                    f"{hint}\n\nDetails: {exc}\n[{rid}] logged. See:\n{log_path}")
                return
        except Exception:  # noqa: BLE001
            pass
        print(f"TRAKKART crashed [{rid}] (details logged): {exc}\nSee: {log_path}")

    sys.excepthook = _hook
    return _hook


def main() -> int:
    if "--cli" in sys.argv[1:]:
        # Headless: never import Qt on this path (fast, display-free).
        from app.cli import run_cli

        return run_cli([a for a in sys.argv[1:] if a != "--cli"])
    from PySide6.QtWidgets import QApplication

    from app.ui.main_window import MainWindow
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
