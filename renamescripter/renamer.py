"""Apply rename operations safely, with rollback and undo history."""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from .plan import Plan, _path_key


@dataclass(frozen=True)
class RenameOp:
    src: Path
    dst: Path

    def reversed(self) -> "RenameOp":
        return RenameOp(self.dst, self.src)


class RenameError(Exception):
    """Renaming failed. Everything that had been renamed was rolled back."""


def ops_from_plan(plan: Plan) -> list[RenameOp]:
    return [RenameOp(i.src, i.dst) for i in plan.changes]


def _move(src: Path, dst: Path) -> None:
    # os.rename silently replaces an existing file on POSIX; never allow that.
    if _path_key(src) != _path_key(dst) and os.path.lexists(dst):
        raise FileExistsError(f"'{dst}' already exists")
    os.rename(src, dst)


def apply_ops(ops: Sequence[RenameOp]) -> list[RenameOp]:
    """Rename all files or none.

    Files are first moved to unique temporary names and then to their final
    names, so swaps (a->b, b->a), chains and case-only renames all work. If
    any step fails, completed steps are reverted and RenameError is raised.
    """
    ops = list(ops)
    tag = uuid.uuid4().hex[:8]
    staged: list[tuple[RenameOp, Path]] = []
    finished: list[tuple[RenameOp, Path]] = []
    try:
        for n, op in enumerate(ops):
            tmp = op.src.with_name(f".rs-{tag}-{n}-{op.src.name}")
            _move(op.src, tmp)
            staged.append((op, tmp))
        for op, tmp in staged:
            _move(tmp, op.dst)
            finished.append((op, tmp))
    except OSError as exc:
        problems = []
        done = {id(op) for op, _ in finished}
        for op, _ in reversed(finished):
            try:
                os.rename(op.dst, op.src)
            except OSError as undo_exc:
                problems.append(f"{op.dst} -> {op.src}: {undo_exc}")
        for op, tmp in reversed(staged):
            if id(op) in done:
                continue
            try:
                os.rename(tmp, op.src)
            except OSError as undo_exc:
                problems.append(f"{tmp} -> {op.src}: {undo_exc}")
        msg = f"Renaming failed, no files were changed: {exc}"
        if problems:
            msg = f"Renaming failed ({exc}) and some files could not be restored:\n" + "\n".join(problems)
        raise RenameError(msg) from exc
    return ops


class History:
    """Undo stack of applied rename batches."""

    def __init__(self, limit: int = 50) -> None:
        self._stack: list[list[RenameOp]] = []
        self.limit = limit

    def __len__(self) -> int:
        return len(self._stack)

    def apply(self, ops: Iterable[RenameOp]) -> list[RenameOp]:
        done = apply_ops(list(ops))
        if done:
            self._stack.append(done)
            del self._stack[: -self.limit]
        return done

    def undo(self) -> list[RenameOp]:
        """Revert the most recent batch; returns the reverse operations performed."""
        if not self._stack:
            return []
        batch = self._stack[-1]
        reverse = [op.reversed() for op in reversed(batch)]
        apply_ops(reverse)
        self._stack.pop()
        return reverse
