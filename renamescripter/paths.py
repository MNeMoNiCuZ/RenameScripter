"""Filesystem locations used by the app (source checkout and frozen builds)."""

from __future__ import annotations

import sys
from pathlib import Path


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def app_dir() -> Path:
    """Folder that holds ``Scripts/`` and ``Settings/``.

    For a PyInstaller build this is the folder containing the executable (the
    Scripts folder is shipped next to it, not baked in). From source it is the
    repository root.
    """
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def scripts_dir() -> Path:
    return app_dir() / "Scripts"


def settings_dir() -> Path:
    return app_dir() / "Settings"


def resource_path(relative: str) -> Path:
    """Locate a bundled read-only resource (e.g. the icon)."""
    bundle = getattr(sys, "_MEIPASS", None)
    if bundle:
        candidate = Path(bundle) / relative
        if candidate.exists():
            return candidate
    return app_dir() / relative
