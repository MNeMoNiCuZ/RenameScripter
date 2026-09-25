See [AGENTS.md](AGENTS.md) for how to write rename scripts, test them with the CLI, and work on the app.

Quick reference:
- New script: copy `Scripts/_Template.py` to `Scripts/<Name>.py`; `rename(files, **params)` returns one new file *name* per path.
- Verify: `python -m renamescripter check "<Name>"` and `python -m pytest -q`.
- Build: `python build.py`.
