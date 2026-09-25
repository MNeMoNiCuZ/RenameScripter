import os

NAME = "Change Case"
DESCRIPTION = "Changes the letter case of file names."

PARAMS = {
    "mode": {"type": "choice", "label": "Case", "choices": ["lowercase", "UPPERCASE", "Title Case", "Sentence case"], "default": "lowercase"},
    "include_extension": {"type": "bool", "label": "Also change extension", "default": False},
}


def convert(text, mode):
    if mode == "UPPERCASE":
        return text.upper()
    if mode == "Title Case":
        return text.title()
    if mode == "Sentence case":
        return text[:1].upper() + text[1:].lower()
    return text.lower()


def rename(files, mode="lowercase", include_extension=False):
    new_names = []
    for path in files:
        filename = os.path.basename(path)
        if include_extension:
            new_names.append(convert(filename, mode))
        else:
            name, ext = os.path.splitext(filename)
            new_names.append(convert(name, mode) + ext)
    return new_names
