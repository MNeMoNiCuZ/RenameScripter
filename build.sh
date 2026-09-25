#!/usr/bin/env sh
# Build a standalone RenameScripter app into dist/RenameScripter (see: python3 build.py --help)
cd "$(dirname "$0")" || exit 1
[ -f venv/bin/activate ] && . venv/bin/activate
exec python3 build.py "$@"
