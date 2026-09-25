"""Build a standalone RenameScripter app with PyInstaller.

    python build.py                 # check scripts, run tests, build dist/RenameScripter/
    python build.py --onedir        # faster-starting folder build instead of a single exe
    python build.py --with-tkinter  # bundle tkinter for legacy scripts that open tk dialogs
    python build.py --skip-tests    # skip the test suite

Output (dist/RenameScripter/):
    RenameScripter(.exe)   the app
    Scripts/               editable rename scripts (NOT baked in - add your own here)
    Settings/              icon; settings.json is created on first run
    AGENTS.md, README.md
plus a zip of that folder in dist/.

User scripts are loaded at runtime, so they can only import modules that are
bundled into the executable. EXTRA_MODULES below lists the standard-library
modules bundled for them; add to it if your scripts need more.
"""

from __future__ import annotations

import argparse
import importlib.util
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
APP = "RenameScripter"

# Standard-library modules made available to user scripts in the frozen app.
EXTRA_MODULES = [
    "base64", "calendar", "collections", "csv", "dataclasses", "datetime", "difflib", "enum", "fnmatch",
    "functools", "glob", "hashlib", "itertools", "json", "locale", "math", "mimetypes", "operator", "os",
    "pathlib", "random", "re", "shlex", "shutil", "string", "struct", "textwrap", "time", "typing",
    "unicodedata", "uuid", "zlib", "zoneinfo",
]
# Large Qt modules the app does not use.
EXCLUDES = ["PySide6.QtNetwork", "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtPdf", "PySide6.QtWebEngineCore", "PySide6.Qt3DCore"]


def run(cmd: list[str]) -> None:
    print("\n>", " ".join(str(c) for c in cmd), flush=True)
    subprocess.check_call(cmd, cwd=ROOT)


def ensure(module: str, package: str) -> None:
    if importlib.util.find_spec(module) is None:
        print(f"{package} not found, installing...")
        run([sys.executable, "-m", "pip", "install", package])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--onedir", action="store_true", help="build a folder app instead of a single executable")
    parser.add_argument("--with-tkinter", action="store_true", help="bundle tkinter for legacy dialog-based scripts")
    parser.add_argument("--skip-tests", action="store_true", help="do not run pytest before building")
    parser.add_argument("--no-zip", action="store_true", help="do not create a zip of the output")
    args = parser.parse_args()

    from renamescripter import __version__

    ensure("PySide6", "PySide6-Essentials")
    ensure("PyInstaller", "pyinstaller")

    # 1. Validate every script in Scripts/ (fast, catches broken scripts before shipping).
    run([sys.executable, "-m", "renamescripter", "check"])
    if not args.skip_tests:
        ensure("pytest", "pytest")
        run([sys.executable, "-m", "pytest", "-q"])

    # 2. PyInstaller.
    build_dir, dist_root = ROOT / "build", ROOT / "dist"
    out = dist_root / APP
    shutil.rmtree(out, ignore_errors=True)
    work_dist = build_dir / "pyinstaller-dist"
    cmd = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed",
        "--name", APP,
        "--distpath", str(work_dist), "--workpath", str(build_dir / "work"), "--specpath", str(build_dir),
        "--add-data", f"{ROOT / 'Settings' / 'icon.ico'}{';' if sys.platform == 'win32' else ':'}Settings",
        "--onedir" if args.onedir else "--onefile",
    ]
    icon = ROOT / "Settings" / "icon.ico"
    if sys.platform in ("win32", "darwin") and icon.exists():
        cmd += ["--icon", str(icon)]
    for mod in EXTRA_MODULES:
        cmd += ["--hidden-import", mod]
    for mod in EXCLUDES:
        cmd += ["--exclude-module", mod]
    if args.with_tkinter:
        cmd += ["--hidden-import", "tkinter", "--hidden-import", "tkinter.simpledialog", "--hidden-import", "tkinter.messagebox"]
    else:
        cmd += ["--exclude-module", "tkinter"]
    cmd.append(str(ROOT / "RenameScripter.py"))
    run(cmd)

    # 3. Assemble the distributable folder.
    out.mkdir(parents=True)
    built = work_dist / APP
    if args.onedir:
        shutil.copytree(built, out, dirs_exist_ok=True)
    else:
        exe = next(p for p in work_dist.iterdir() if p.name in (APP, f"{APP}.exe", f"{APP}.app"))
        (shutil.copytree if exe.is_dir() else shutil.copy2)(exe, out / exe.name)
    shutil.copytree(ROOT / "Scripts", out / "Scripts", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    (out / "Settings").mkdir(exist_ok=True)
    shutil.copy2(icon, out / "Settings" / "icon.ico")
    for doc in ("AGENTS.md", "README.md", "LICENSE"):
        if (ROOT / doc).exists():
            shutil.copy2(ROOT / doc, out / doc)

    if not args.no_zip:
        system = {"win32": "windows", "darwin": "macos"}.get(sys.platform, sys.platform)
        archive = shutil.make_archive(str(dist_root / f"{APP}-{__version__}-{system}-{platform.machine().lower()}"), "zip", dist_root, APP)
        print(f"\nZip: {archive}")
    print(f"\nDone. App folder: {out}\nKeep the Scripts folder next to the executable.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
