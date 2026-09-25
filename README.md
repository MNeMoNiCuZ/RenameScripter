# RenameScripter

RenameScripter is a desktop tool for batch-renaming files with small Python
scripts. Pick a script, set its options, check the live preview, and rename.
Adding a new renaming rule means dropping a short `.py` file into `Scripts/`.
You can write these yourself or ask an AI assistant for one (see [AGENTS.md](AGENTS.md)).

## Features

- **Qt 6 (PySide6) interface** that follows the system light/dark theme
- **Live preview**: new names update as you type in a script's options
- **Checks every name before renaming**: duplicate targets, files that already
  exist, invalid or reserved Windows names, and missing files are flagged in red
- **Safe renaming**: all or nothing, with automatic rollback. Swaps like
  `a→b, b→a` and case-only changes work. Existing files are never overwritten
- **Multi-level undo** (Ctrl+Z)
- **Script options as form fields**: scripts declare `PARAMS` and get text boxes,
  checkboxes, number fields and dropdowns without any GUI code
- **Hot reload**: edit or add a script and the list updates immediately. Scripts
  that fail to load show their error in the app
- Drag and drop files or folders (with or without subfolders), sort the list,
  remove entries, and filter scripts by name
- **Command line** for scripting and for testing scripts:
  `list`, `preview`, `apply`, `check`
- **Standalone build** with one command (`build.bat` / `build.sh`)

## Installation

Requires Python 3.10 or newer.

```bash
python -m venv venv
venv\Scripts\activate          # Windows  (Linux/macOS: source venv/bin/activate)
pip install -r requirements.txt
```

On Windows you can run `venv_create.bat` to do this interactively.

## Usage

Run `RenameScripter.bat` (Windows) or `./RenameScripter.sh` (Linux/macOS), or
`python RenameScripter.py`. Paths passed on the command line are loaded into the
list, so you can also drop files onto the launcher/exe or use it from "Send To".

1. Drop files/folders onto the window (or use **Add Files** / **Add Folder**).
2. Pick a script on the left and adjust its options.
3. Check the preview: green = will be renamed, red = problem (hover for details).
4. Press **Rename** (F2). Press Ctrl+Z to undo.

| Shortcut | Action | Shortcut | Action |
|---|---|---|---|
| F2 / Ctrl+Enter | Rename (refreshes the preview first if it is out of date) | Ctrl+O / Ctrl+Shift+O | Add files / folder |
| F5 | Preview | Delete | Remove selected files |
| Ctrl+Z | Undo last rename | Ctrl+W | Clear list |
| Ctrl+R | Reload scripts | Ctrl+F | Filter scripts |
| Ctrl+N | New script from template | Ctrl+E | Edit selected script |

Click a column header to sort the file list. The order matters for scripts
such as *Sequential Numbering Prefix*. Options are under **Settings**: live
preview, confirm before renaming, remember the last script and its options,
and include subfolders.

### Command line

```bash
python RenameScripter.py list                                  # scripts and their options
python RenameScripter.py preview "Search And Replace" -p search=" " -p replace=_ ./photos
python RenameScripter.py apply Inverter ./photos --yes         # --skip-errors to rename the valid ones only
python RenameScripter.py check                                 # test every script on sample files
```

Add `--json` to `list`, `preview` and `apply` for machine-readable output.

## Included scripts

CamelCase · Change Case · Change Extension · Date As Prefix (today or file date,
custom format) · Inverter · Parent Folder As Name (numbers duplicates) · Prefix
And Suffix · Remove Numbers · Replace Space With Underscore · Search And Replace
(plain or regex, case options) · Sequential Numbering Prefix (start, digits,
per-folder).

## Writing your own scripts

Copy `Scripts/_Template.py` to `Scripts/My Script.py` (or use **Scripts → New
Script…**):

```python
import os

NAME = "Prefix And Suffix"
DESCRIPTION = "Adds text before and/or after the name."
PARAMS = {
    "prefix": {"label": "Prefix", "default": ""},
    "suffix": {"label": "Suffix", "default": ""},
}

def rename(files, prefix="", suffix=""):
    new_names = []
    for path in files:                      # absolute paths
        name, ext = os.path.splitext(os.path.basename(path))
        new_names.append(f"{prefix}{name}{suffix}{ext}")
    return new_names                        # one new *name* per file (None = unchanged)
```

Then run `python RenameScripter.py check "Prefix And Suffix"`.
[AGENTS.md](AGENTS.md) has the full contract (parameter types, accepted return
formats, rules) and is written so you can hand it to an AI assistant.

Scripts from version 1.x that return `[(old_name, new_name), ...]` still work.
Scripts that open tkinter dialogs also still work when run from source, but
converting them to `PARAMS` gives you live preview.

## Building a standalone app

```bash
build.bat            # Windows
./build.sh           # Linux/macOS
python build.py --help
```

The build runs the script check and the tests, then packages the app with
PyInstaller into `dist/RenameScripter/`: the executable, an editable `Scripts/`
folder next to it, and `Settings/`. It also writes a zip. Options:
`--onedir` (starts faster), `--with-tkinter` (for old dialog-based scripts),
`--skip-tests`.

## Development

```bash
pip install -r requirements-dev.txt
python -m pytest -q
```

See [AGENTS.md](AGENTS.md) for the project layout and conventions.
