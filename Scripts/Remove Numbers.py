import os
import re

NAME = "Remove Numbers"
DESCRIPTION = "Removes all digits from the name (the extension is kept)."

PARAMS = {
    "tidy": {"type": "bool", "label": "Tidy up leftover spaces/separators", "default": True},
}


def rename(files, tidy=True):
    new_names = []
    for path in files:
        name, ext = os.path.splitext(os.path.basename(path))
        cleaned = re.sub(r"\d+", "", name)
        if tidy:
            cleaned = re.sub(r"([ _\-.])[ _\-.]+", r"\1", cleaned).strip(" _-.")
            cleaned = re.sub(r"\(\s*\)", "", cleaned).strip()
        new_names.append(f"{cleaned or name}{ext}")
    return new_names
