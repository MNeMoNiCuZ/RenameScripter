import os

NAME = "Change Extension"
DESCRIPTION = "Replaces the file extension. Leave the field empty to remove the extension."

PARAMS = {
    "extension": {"label": "New extension", "default": "txt", "placeholder": "e.g. jpg or .jpg"},
}


def rename(files, extension="txt"):
    extension = extension.strip()
    if extension and not extension.startswith("."):
        extension = "." + extension
    new_names = []
    for path in files:
        name, _old_ext = os.path.splitext(os.path.basename(path))
        new_names.append(name + extension)
    return new_names
