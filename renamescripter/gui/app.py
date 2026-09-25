"""Create the QApplication and show the main window."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from .. import APP_NAME, __version__, paths
from ..settings import Settings
from .main_window import MainWindow


def run(argv: list[str] | None = None, scripts_dir: str | Path | None = None) -> int:
    """Start the GUI. ``argv`` may contain files/folders to preload."""
    argv = list(argv or [])
    app = QApplication.instance() or QApplication([sys.argv[0], *[a for a in argv if a.startswith("-")]])
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.setStyle("Fusion")  # consistent modern look; follows the system light/dark scheme

    window = MainWindow(Settings(), Path(scripts_dir) if scripts_dir else paths.scripts_dir(), [a for a in argv if not a.startswith("-")])
    window.show()
    return app.exec()
