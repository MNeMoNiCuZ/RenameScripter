"""Persistent user settings stored as JSON in ``Settings/settings.json``."""

from __future__ import annotations

import configparser
import json
from pathlib import Path
from typing import Any

from . import paths

DEFAULTS: dict[str, Any] = {
    "live_preview": True,
    "confirm_rename": True,
    "remember_last_script": True,
    "remember_params": True,
    "include_subfolders": True,
    "last_script": "",
    "params": {},  # script key -> {param: value}
    "geometry": "",
    "splitter": "",
}


class Settings:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or paths.settings_dir() / "settings.json"
        self.data: dict[str, Any] = dict(DEFAULTS)
        self.load()

    def load(self) -> None:
        try:
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                self.data.update(loaded)
        except FileNotFoundError:
            self._migrate_ini(self.path.parent / "config.ini")
        except (OSError, ValueError):
            pass  # corrupt or unreadable: fall back to defaults

    def _migrate_ini(self, ini: Path) -> None:
        """Import settings from the 1.x ``config.ini`` if present."""
        if not ini.exists():
            return
        cfg = configparser.ConfigParser()
        try:
            cfg.read(ini, encoding="utf-8")
        except configparser.Error:
            return
        s = cfg["Settings"] if cfg.has_section("Settings") else {}
        mapping = {"auto_preview": "live_preview", "ask_confirmation": "confirm_rename", "remember_last_script": "remember_last_script"}
        for old, new in mapping.items():
            if old in s:
                try:
                    self.data[new] = cfg.getboolean("Settings", old)
                except ValueError:
                    pass
        if s.get("last_selected_script"):
            self.data["last_script"] = s["last_selected_script"]

    def save(self) -> bool:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self.data, indent=2, sort_keys=True), encoding="utf-8")
            return True
        except OSError:
            return False  # e.g. installed to a read-only location

    def __getitem__(self, key: str) -> Any:
        return self.data.get(key, DEFAULTS.get(key))

    def __setitem__(self, key: str, value: Any) -> None:
        self.data[key] = value
