#!/usr/bin/env sh
# Launch RenameScripter (uses ./venv if present). Extra arguments are passed through.
cd "$(dirname "$0")" || exit 1
[ -f venv/bin/activate ] && . venv/bin/activate
exec python3 RenameScripter.py "$@"
