# AGENTS.md — working on RenameScripter

This file is for AI coding agents (and humans) who either **write rename scripts**
(the most common task) or **change the app itself**. Read the section you need.

---

## 1. What this project is

A desktop app (Python 3.10+, Qt 6 via PySide6) that batch-renames files. Each
renaming rule is a small Python file in `Scripts/`. The app lists the scripts,
shows each script's options as input fields, previews the new names live, checks
them for problems, and then renames. All renaming is done by the app. Scripts
only work out the new names.

```
RenameScripter.py        launcher (GUI, or CLI when given a command)
renamescripter/          application package
  scripts.py             script loading, PARAMS parsing, result normalization  <- the script contract
  plan.py                validation: bad names, duplicate targets, existing files
  renamer.py             two-phase all-or-nothing rename + undo history
  files.py               expanding dropped folders, natural sort
  settings.py            Settings/settings.json (migrates old config.ini)
  cli.py                 list / preview / apply / check commands
  gui/                   Qt window, file table model, parameter form
Scripts/                 rename scripts (shipped next to the exe, not baked in)
  _Template.py           copy this to start a new script (files starting with _ are hidden)
tests/                   pytest suite (includes a test for every script in Scripts/)
build.py                 PyInstaller build (build.bat / build.sh wrappers)
```

---

## 2. Writing a rename script

### 2.1 The contract

Create `Scripts/<Display Name>.py` (UTF-8, no leading underscore). The only
required part is a `rename` function:

```python
import os

NAME = "Prefix And Suffix"                      # optional, defaults to the file name
DESCRIPTION = "Adds text before/after the name." # optional, shown in the app

PARAMS = {                                       # optional, shown as input fields
    "prefix": {"label": "Prefix", "default": ""},
    "suffix": {"label": "Suffix", "default": ""},
}

def rename(files, prefix="", suffix=""):
    new_names = []
    for path in files:
        name, ext = os.path.splitext(os.path.basename(path))
        new_names.append(f"{prefix}{name}{suffix}{ext}")
    return new_names
```

**Input:** `files` is a `list[str]` of **absolute file paths**, in the order the
user sees them (they can sort the list). Folders dropped by the user are
expanded into their files, so you only get files.

**Keyword arguments:** every key in `PARAMS` is passed to `rename` as a keyword
argument with the user's current value. The function must accept all of them
(or `**kwargs`). If there is no `PARAMS`, it is called as `rename(files)`.

**Output:** return one new **file name** (not a path) per input file. Preferred:

```python
return ["new1.txt", "new2.txt", ...]        # same length and order as files
```

Also accepted (for compatibility):

```python
return [("old.txt", "new.txt"), ...]         # old = basename or full path, any order, may be partial
return {"old.txt": "new.txt", ...}          # dict keyed by basename or full path
```

Returning `None`, `""` or the unchanged name for an entry means "leave this file
alone".

### 2.2 PARAMS reference

`PARAMS` is a dict of `key -> spec` (the key must be a valid Python identifier
and match the `rename` argument name). A spec is a dict with these fields:

| field         | used by        | meaning                                                      |
|---------------|----------------|--------------------------------------------------------------|
| `type`        | all            | `text` (default), `int`, `float`, `bool`, `choice`           |
| `label`       | all            | text shown in the form (defaults to the key, prettified)     |
| `default`     | all            | initial value (type is inferred from it if `type` is omitted)|
| `help`        | all            | tooltip                                                      |
| `choices`     | `choice`       | list of strings (required for `choice`)                      |
| `min`, `max`, `step` | `int`/`float` | numeric limits (values are clamped)                    |
| `placeholder` | `text`         | grey hint text in an empty field                             |

Shorthand: `PARAMS = {"count": 3, "upper": False}` infers `int` and `bool`.
Values are type-converted before your function sees them. Users' last-used values
are remembered per script.

### 2.3 Rules scripts must follow

1. **Never rename, move, delete or write files.** Only return names. The app
   previews, validates (duplicates, existing files, invalid characters, reserved
   Windows names), renames everything or nothing (it rolls back if one fails),
   and supports undo.
2. **Be pure and fast.** `rename` runs on every keystroke in the options while
   live preview is on. The same input must give the same output, otherwise the
   preview won't match what gets renamed. Reading file metadata
   (`os.path.getmtime`, size) is fine. Don't use the network, sleep, or anything
   random unless it is seeded.
3. **No GUI code.** Do not use `tkinter`, `input()` or dialogs. Declare `PARAMS`
   instead. (Old scripts that open tkinter dialogs still load, but they turn off
   live preview and are skipped by `check`.)
4. **Return names, not paths.** A `/` or `\` in a new name is an error. Keep
   the extension unless the script is meant to change it (`os.path.splitext`).
5. **Handle every file.** Return exactly `len(files)` entries when using the list
   form, using `None` for files you skip. Don't raise for odd names (no
   extension, dotfiles like `.gitignore`, names with several dots like
   `a.tar.gz`, unicode).
6. **Numbering and grouping:** you get the whole list at once, so you can number
   files, restart per folder (`os.path.dirname(path)`), or avoid duplicate
   names yourself (see `Parent Folder As Name.py`).
7. **Imports:** standard library only, unless the user installs extras. The
   built exe bundles the stdlib modules listed in `build.py` (`EXTRA_MODULES`).
   Add to that list if a new script needs another module. A script can import
   helper modules from `Scripts/` whose names start with `_` (e.g.
   `from _helpers import slugify`); those files don't appear in the list.
8. Save the file as **UTF-8**. The file name (without `.py`) is the script's
   stable id, used on the CLI and in saved settings.

### 2.4 Test your script (always do this)

You don't need the GUI. From the repo root:

```bash
python -m renamescripter check "My Script"      # load it, run it on sample files, apply + undo in a temp folder
python -m renamescripter list                    # confirm it loads and shows the right params
python -m renamescripter preview "My Script" -p text=abc path/to/files   # dry run on real files
python -m renamescripter preview "My Script" path/to/files --json        # machine-readable plan
python -m pytest -q                              # full suite; includes every script in Scripts/
```

`check` must say `OK` (a `WARN` line means the sample files produced a problem
you should look at, for example duplicate names). `preview` exits with code 1
if any file has a problem and prints why (`[... already exists in this folder]`).
Pass `-p key=value` once for each parameter. Unknown keys are an error.

The GUI reloads scripts automatically when files in `Scripts/` change. A script
that fails to load shows a warning icon, and the error appears in its options panel.

### 2.5 Checklist before you finish

- [ ] `python -m renamescripter check "<name>"` → `OK`
- [ ] `python -m pytest -q` passes
- [ ] `NAME` and a one-sentence `DESCRIPTION` are set; every `PARAMS` entry has a `label`
- [ ] defaults do something sensible (or return `None` for all files when an
      empty required field makes the script a no-op, like `Search And Replace`)

---

## 3. Changing the app

- Setup: `python -m venv venv`, activate it, then `pip install -r requirements-dev.txt`
  (on Windows, `venv_create.bat` does this interactively).
- Run: `python RenameScripter.py [files...]` (or `RenameScripter.bat` / `RenameScripter.sh`).
- Tests: `python -m pytest -q`. The GUI test runs headless (`QT_QPA_PLATFORM=offscreen`)
  and is skipped if Qt can't start.
- Build: `python build.py` (or `build.bat` / `build.sh`). It runs `check` and the
  tests, then PyInstaller, and writes `dist/RenameScripter/` (exe + `Scripts/` +
  `Settings/`) and a zip. Options: `--onedir`, `--with-tkinter`, `--skip-tests`.
- Keep the core (`scripts.py`, `plan.py`, `renamer.py`, `files.py`, `cli.py`)
  free of Qt imports. Only `renamescripter/gui/` may import PySide6.
- The script contract in section 2 is a public API. Existing user scripts must
  keep working. Add new return shapes or PARAMS fields in a backward-compatible way,
  and cover them in `tests/test_core.py`.
- Safety features you must keep: plan validation before any rename; the
  all-or-nothing two-phase rename; never overwriting an existing file (POSIX
  `os.rename` would do that silently); undo.
- Paths: use `renamescripter.paths` (it handles PyInstaller builds, where
  `Scripts/` and `Settings/` sit next to the executable).
- Version: `renamescripter/__init__.py` (`__version__`).
