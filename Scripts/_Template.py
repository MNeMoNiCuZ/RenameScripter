"""Template for a new rename script.

Copy this file to a new name WITHOUT a leading underscore (files starting with
"_" are ignored by the app), e.g. "Scripts/My Rename.py", then edit it.
The app reloads scripts automatically when files in this folder change.

Test it without the GUI:
    python -m renamescripter check "My Rename"
    python -m renamescripter preview "My Rename" -p text=hello path/to/files
"""

import os

# Shown in the script list and as help text in the app.
NAME = "My Rename"
DESCRIPTION = "Adds some text to the end of each file name (before the extension)."

# Options shown as input fields in the app and passed to rename() as keyword
# arguments. Types: text, int, float, bool, choice. Delete PARAMS if you need none.
PARAMS = {
    "text": {"label": "Text to add", "default": "_new"},
    "lowercase": {"type": "bool", "label": "Also make lowercase", "default": False},
}


def rename(files, text="_new", lowercase=False):
    """Return the new file name for each path in `files` (same order).

    `files` is a list of absolute paths. Return a list of *names* (not paths),
    one per file. Return None or the unchanged name to leave a file alone.
    Do not rename anything yourself - the app previews, validates and applies.
    """
    new_names = []
    for path in files:
        name, ext = os.path.splitext(os.path.basename(path))
        new_name = f"{name}{text}{ext}"
        if lowercase:
            new_name = new_name.lower()
        new_names.append(new_name)
    return new_names
