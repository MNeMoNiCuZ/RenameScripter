"""Collecting files to rename from dropped/selected paths."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Iterable


def natural_key(text: str) -> list:
    """Sort key so that 'file2' comes before 'file10'."""
    return [int(t) if t.isdigit() else t.casefold() for t in re.split(r"(\d+)", text)]


def expand_paths(items: Iterable[str | Path], include_subfolders: bool = True) -> list[Path]:
    """Expand files and folders into a flat list of files (folders are not renamed themselves)."""
    result: list[Path] = []
    for item in items:
        p = Path(item)
        if p.is_file():
            result.append(p.absolute())
        elif p.is_dir():
            if include_subfolders:
                found = []
                for root, dirs, names in os.walk(p):
                    dirs.sort(key=natural_key)
                    found.extend(Path(root, n) for n in sorted(names, key=natural_key))
            else:
                found = sorted((c for c in p.iterdir() if c.is_file()), key=lambda c: natural_key(c.name))
            result.extend(f.absolute() for f in found)
    return result


def merge_unique(existing: list[Path], new: Iterable[Path]) -> tuple[list[Path], int]:
    """Append paths not already present; returns the merged list and how many were added."""
    seen = {os.path.normcase(str(p)) for p in existing}
    merged = list(existing)
    for p in new:
        key = os.path.normcase(str(p))
        if key not in seen:
            seen.add(key)
            merged.append(p)
    return merged, len(merged) - len(existing)
