import os
import re

NAME = "Search And Replace"
DESCRIPTION = "Replaces text in file names. Supports plain text or regular expressions."

PARAMS = {
    "search": {"label": "Search for", "default": ""},
    "replace": {"label": "Replace with", "default": ""},
    "regex": {"type": "bool", "label": "Regular expression", "default": False,
              "help": "Use Python regex syntax; refer to groups as \\1 in the replacement."},
    "case_sensitive": {"type": "bool", "label": "Case sensitive", "default": True},
    "include_extension": {"type": "bool", "label": "Also replace in extension", "default": False},
}


def rename(files, search="", replace="", regex=False, case_sensitive=True, include_extension=False):
    if not search:
        return [None] * len(files)  # nothing to do yet
    flags = 0 if case_sensitive else re.IGNORECASE
    pattern = re.compile(search if regex else re.escape(search), flags)
    if not regex:
        replace = replace.replace("\\", "\\\\")  # treat replacement literally

    new_names = []
    for path in files:
        filename = os.path.basename(path)
        if include_extension:
            new_names.append(pattern.sub(replace, filename))
        else:
            name, ext = os.path.splitext(filename)
            new_names.append(pattern.sub(replace, name) + ext)
    return new_names
