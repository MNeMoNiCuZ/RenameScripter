"""Command-line interface: list scripts, preview or apply a rename, and self-check scripts.

Examples::

    python -m renamescripter list
    python -m renamescripter preview "Search And Replace" -p search=" " -p replace=_ ./photos
    python -m renamescripter apply Inverter ./photos --yes
    python -m renamescripter check            # validate every script in Scripts/
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Sequence

from . import __version__, paths
from .files import expand_paths
from .plan import Status, build_plan
from .renamer import History, RenameError, apply_ops, ops_from_plan
from .scripts import RenameScript, ScriptError, find_script, load_scripts

COMMANDS = ("list", "preview", "apply", "check")

# Files used by `check` to exercise each script.
SAMPLE_FILES = (
    "My Holiday Photo 01.jpg",
    "report_final v2.docx",
    "notes.txt",
    "Archive.2023.tar.gz",
    "README",
    ".hidden",
    "Café naïve – ünïcode.txt",
    "Sub Folder/Track 07 - Song Name.mp3",
    "Sub Folder/image (3).png",
)


def _out(text: str = "") -> None:
    print(text, flush=True)


def _parse_param_args(pairs: Sequence[str]) -> dict[str, str]:
    values = {}
    for pair in pairs:
        if "=" not in pair:
            raise ScriptError(f"--param expects KEY=VALUE, got '{pair}'")
        key, value = pair.split("=", 1)
        values[key.strip()] = value
    return values


def _get_script(scripts: list[RenameScript], name: str) -> RenameScript:
    script = find_script(scripts, name)
    if script is None:
        available = ", ".join(s.key for s in scripts)
        raise ScriptError(f"No script named '{name}'. Available: {available}")
    if not script.ok:
        raise ScriptError(f"Script '{script.name}' cannot be used:\n{script.error}")
    return script


def cmd_list(args: argparse.Namespace, scripts: list[RenameScript]) -> int:
    if args.json:
        _out(json.dumps([
            {
                "key": s.key, "name": s.name, "file": str(s.path), "ok": s.ok, "error": s.error,
                "description": s.description, "interactive": s.uses_tkinter,
                "params": [
                    {"key": p.key, "type": p.type, "label": p.label, "default": p.default, "choices": p.choices, "help": p.help}
                    for p in s.params
                ],
            }
            for s in scripts
        ], indent=2))
        return 0
    for s in scripts:
        flag = "ERROR" if not s.ok else "     "
        _out(f"{flag} {s.name}" + (f"  [{s.key}.py]" if s.key != s.name else ""))
        if s.description:
            _out(f"        {s.description.splitlines()[0]}")
        for p in s.params:
            extra = f" choices={p.choices}" if p.choices else ""
            _out(f"        -p {p.key}=<{p.type}>  default={p.default!r}{extra}")
        if s.error:
            _out("        " + s.error.strip().splitlines()[-1])
    return 0 if all(s.ok for s in scripts) else 1


def _make_plan(args: argparse.Namespace, scripts: list[RenameScript]):
    script = _get_script(scripts, args.script)
    files = expand_paths(args.paths, include_subfolders=not args.no_subfolders)
    if not files:
        raise ScriptError("No files found in the given paths")
    names = script.run(files, _parse_param_args(args.param), strict=True)
    return script, build_plan(files, names)


def _print_plan(plan, as_json: bool) -> None:
    if as_json:
        _out(json.dumps({"summary": plan.summary(), "items": [i.to_dict() for i in plan.items]}, indent=2))
        return
    width = max((len(i.src.name) for i in plan.items), default=0)
    for i in plan.items:
        if i.status is Status.UNCHANGED:
            _out(f"  = {i.src.name}")
        elif i.status is Status.OK:
            _out(f"  ~ {i.src.name:<{width}}  ->  {i.new_name}")
        else:
            _out(f"  ! {i.src.name:<{width}}  ->  {i.new_name}   [{i.message}]")
    _out(plan.summary())


def cmd_preview(args: argparse.Namespace, scripts: list[RenameScript]) -> int:
    _, plan = _make_plan(args, scripts)
    _print_plan(plan, args.json)
    return 1 if plan.errors else 0


def cmd_apply(args: argparse.Namespace, scripts: list[RenameScript]) -> int:
    _, plan = _make_plan(args, scripts)
    _print_plan(plan, args.json)
    if plan.errors and not args.skip_errors:
        _out("Nothing renamed: fix the problems above or pass --skip-errors.")
        return 1
    if not plan.changes:
        _out("Nothing to rename.")
        return 0
    if not args.yes:
        if not sys.stdin or not sys.stdin.isatty():
            _out("Refusing to rename without confirmation; pass --yes.")
            return 1
        if input(f"Rename {len(plan.changes)} file(s)? [y/N] ").strip().lower() not in ("y", "yes"):
            _out("Cancelled.")
            return 1
    apply_ops(ops_from_plan(plan))
    _out(f"Renamed {len(plan.changes)} file(s).")
    return 0


def check_script(script: RenameScript) -> list[str]:
    """Run a script against sample files in a temp folder, apply and undo. Returns problems."""
    if not script.ok:
        return [script.error or "not loadable"]
    problems: list[str] = []
    with tempfile.TemporaryDirectory(prefix="renamescripter-check-") as tmp:
        root = Path(tmp) / "Sample Folder"
        for rel in SAMPLE_FILES:
            f = root / rel
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(rel, encoding="utf-8")
        files = expand_paths([root])
        try:
            names = script.run(files, script.defaults())
            again = script.run(files, script.defaults())
        except ScriptError as exc:
            return [str(exc)]
        if names != again:
            problems.append("warning: output differs between two runs with the same input (preview won't match rename)")
        plan = build_plan(files, names)
        for item in plan.errors:
            problems.append(f"warning: {item.src.name} -> {item.new_name}: {item.message}")
        history = History()
        try:
            history.apply(ops_from_plan(plan))
            for item in plan.changes:
                if not item.dst.exists():
                    problems.append(f"{item.dst.name} missing after rename")
            history.undo()
        except RenameError as exc:
            problems.append(str(exc))
        restored = sorted(str(p.relative_to(root)) for p in expand_paths([root]))
        if restored != sorted(str(Path(r)) for r in SAMPLE_FILES):
            problems.append("files were not restored correctly by undo")
    return problems


def cmd_check(args: argparse.Namespace, scripts: list[RenameScript]) -> int:
    if args.names:
        selected = []
        for n in args.names:
            s = find_script(scripts, n)
            if s is None:
                raise ScriptError(f"No script named '{n}'. Available: {', '.join(x.key for x in scripts)}")
            selected.append(s)
        scripts = selected
    failed = 0
    for s in scripts:
        if s.uses_tkinter and not args.interactive:
            _out(f"SKIP  {s.name}: uses tkinter dialogs (legacy); convert it to PARAMS or pass --interactive")
            continue
        problems = check_script(s)
        errors = [p for p in problems if not p.startswith("warning:")]
        status = "FAIL" if errors else ("WARN" if problems else "OK  ")
        failed += bool(errors)
        _out(f"{status}  {s.name}")
        for p in problems:
            _out("      " + p.replace("\n", "\n      "))
    _out(f"\n{len(scripts)} script(s) checked, {failed} failed.")
    return 1 if failed else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="renamescripter", description="Batch rename files with Python scripts. Run without a command to open the GUI.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--scripts-dir", type=Path, default=None, help="folder containing rename scripts (default: ./Scripts next to the app)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("list", help="list available scripts and their parameters")
    p.add_argument("--json", action="store_true", help="machine-readable output")

    for name, help_text in (("preview", "show what a script would rename (dry run)"), ("apply", "rename files using a script")):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("script", help="script file name (without .py) or display name")
        p.add_argument("paths", nargs="+", help="files and/or folders")
        p.add_argument("-p", "--param", action="append", default=[], metavar="KEY=VALUE", help="script parameter (repeatable)")
        p.add_argument("--no-subfolders", action="store_true", help="do not recurse into subfolders of given folders")
        p.add_argument("--json", action="store_true", help="machine-readable output")
        if name == "apply":
            p.add_argument("-y", "--yes", action="store_true", help="do not ask for confirmation")
            p.add_argument("--skip-errors", action="store_true", help="rename the valid files even if some have problems")

    p = sub.add_parser("check", help="load every script and test it against sample files (apply + undo in a temp folder)")
    p.add_argument("names", nargs="*", help="only check these scripts")
    p.add_argument("--interactive", action="store_true", help="also run legacy scripts that open tkinter dialogs")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    scripts_dir = args.scripts_dir or paths.scripts_dir()
    scripts = load_scripts(scripts_dir)
    if not scripts and args.command != "list":
        print(f"No scripts found in {scripts_dir}", file=sys.stderr)
        return 2
    handler = {"list": cmd_list, "preview": cmd_preview, "apply": cmd_apply, "check": cmd_check}[args.command]
    try:
        return handler(args, scripts)
    except (ScriptError, RenameError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
