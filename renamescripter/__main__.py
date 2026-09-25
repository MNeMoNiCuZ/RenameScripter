"""Entry point: ``python -m renamescripter [command | files...]``.

With a CLI command (list/preview/apply/check) or ``-h``/``--version`` the
command-line interface runs; otherwise the GUI opens, preloaded with any
file/folder paths given (so the app works with "Send To" and drag-onto-exe).
"""

from __future__ import annotations

import sys

CLI_WORDS = {"list", "preview", "apply", "check", "-h", "--help", "--version"}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    rest = argv[2:] if argv[:1] == ["--scripts-dir"] else argv
    if rest and rest[0] in CLI_WORDS:
        from .cli import main as cli_main

        return cli_main(argv)

    from .gui.app import run

    scripts_dir = argv[1] if argv[:1] == ["--scripts-dir"] and len(argv) > 1 else None
    return run(rest, scripts_dir=scripts_dir)


if __name__ == "__main__":
    sys.exit(main())
