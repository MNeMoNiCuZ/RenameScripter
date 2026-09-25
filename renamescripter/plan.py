"""Turn a script's proposed names into a validated rename plan."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Sequence

_CASE_INSENSITIVE_FS = sys.platform in ("win32", "darwin")
_WINDOWS_INVALID = set('<>:"/\\|?*')
_WINDOWS_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
MAX_NAME_LENGTH = 255


class Status(str, Enum):
    UNCHANGED = "unchanged"
    OK = "ok"
    ERROR = "error"


@dataclass
class PlanItem:
    src: Path
    new_name: str | None
    status: Status = Status.UNCHANGED
    message: str = ""

    @property
    def dst(self) -> Path:
        return self.src.with_name(self.new_name) if self.new_name else self.src

    def to_dict(self) -> dict:
        return {"src": str(self.src), "dst": str(self.dst), "new_name": self.new_name, "status": self.status.value, "message": self.message}


@dataclass
class Plan:
    items: list[PlanItem] = field(default_factory=list)

    @property
    def changes(self) -> list[PlanItem]:
        return [i for i in self.items if i.status is Status.OK]

    @property
    def errors(self) -> list[PlanItem]:
        return [i for i in self.items if i.status is Status.ERROR]

    def summary(self) -> str:
        parts = [f"{len(self.items)} file(s)", f"{len(self.changes)} to rename"]
        if self.errors:
            parts.append(f"{len(self.errors)} with problems")
        return ", ".join(parts)


def _path_key(path: Path) -> str:
    key = os.path.normpath(str(path))
    return key.lower() if _CASE_INSENSITIVE_FS else key


def name_problem(name: str, windows_rules: bool = sys.platform == "win32") -> str | None:
    """Return why ``name`` is not a usable file name, or None if it is fine."""
    if not name.strip():
        return "New name is empty"
    if name in (".", ".."):
        return f"'{name}' is not a valid file name"
    if "/" in name or (os.sep != "/" and os.sep in name) or (windows_rules and "\\" in name):
        return "New name contains a path separator; scripts must return a file name, not a path"
    if "\0" in name:
        return "New name contains a NUL character"
    if len(name.encode("utf-8")) > MAX_NAME_LENGTH:
        return f"New name is longer than {MAX_NAME_LENGTH} bytes"
    if windows_rules:
        bad = sorted({c for c in name if c in _WINDOWS_INVALID or ord(c) < 32})
        if bad:
            return "New name contains characters not allowed on Windows: " + " ".join(repr(c) for c in bad)
        if name[-1] in " .":
            return "New name ends with a space or dot (not allowed on Windows)"
        if name.split(".")[0].upper() in _WINDOWS_RESERVED:
            return f"'{name.split('.')[0]}' is a reserved name on Windows"
    return None


def build_plan(files: Sequence[str | Path], new_names: Sequence[str | None]) -> Plan:
    """Validate proposed names: bad names, duplicate targets and clashes with existing files."""
    if len(files) != len(new_names):
        raise ValueError("files and new_names must have the same length")
    items: list[PlanItem] = []
    for f, new in zip(files, new_names):
        src = Path(f)
        item = PlanItem(src=src, new_name=new)
        if new is None or new == src.name:
            item.new_name = None
        elif not src.exists():
            item.status, item.message = Status.ERROR, "Source file no longer exists"
        elif problem := name_problem(new):
            item.status, item.message = Status.ERROR, problem
        else:
            item.status = Status.OK
        items.append(item)

    # Two sources renamed to the same target.
    targets: dict[str, list[PlanItem]] = {}
    for item in items:
        if item.status is Status.OK:
            targets.setdefault(_path_key(item.dst), []).append(item)
    for group in targets.values():
        if len(group) > 1:
            for item in group:
                item.status, item.message = Status.ERROR, f"{len(group)} files would get the name '{item.new_name}'"

    # Target already taken by a file that is not moving out of the way. Blocking one
    # rename can in turn block another, so repeat until nothing changes.
    changed = True
    while changed:
        changed = False
        moving_away = {_path_key(i.src) for i in items if i.status is Status.OK}
        staying = {_path_key(i.src) for i in items if i.status is not Status.OK}
        for item in items:
            if item.status is not Status.OK:
                continue
            key = _path_key(item.dst)
            if key == _path_key(item.src):
                continue  # case-only rename on a case-insensitive filesystem
            if key in staying or (key not in moving_away and os.path.lexists(item.dst)):
                item.status, item.message = Status.ERROR, f"'{item.new_name}' already exists in this folder"
                changed = True
    return Plan(items)
