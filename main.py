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


def main() -> int:
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
