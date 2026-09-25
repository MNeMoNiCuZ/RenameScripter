import os

NAME = "Prefix And Suffix"
DESCRIPTION = "Adds text before and/or after the name. The suffix goes before the extension."

PARAMS = {
    "prefix": {"label": "Prefix", "default": ""},
    "suffix": {"label": "Suffix", "default": ""},
}


def rename(files, prefix="", suffix=""):
    new_names = []
    for path in files:
        name, ext = os.path.splitext(os.path.basename(path))
        new_names.append(f"{prefix}{name}{suffix}{ext}")
    return new_names
