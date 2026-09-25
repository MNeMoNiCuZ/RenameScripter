import os
import re

NAME = "CamelCase"
DESCRIPTION = "Removes separators and capitalizes each word: 'my holiday-photo 01.jpg' -> 'MyHolidayPhoto01.jpg'."

PARAMS = {
    "lower_first": {"type": "bool", "label": "lowerCamelCase (first word lowercase)", "default": False},
}


def to_camel_case(filename, lower_first=False):
    name, ext = os.path.splitext(filename)
    words = [w for w in re.split(r"[^a-zA-Z0-9]+", name) if w]
    camel = "".join(w[:1].upper() + w[1:].lower() for w in words)
    if lower_first and camel:
        camel = camel[0].lower() + camel[1:]
    return (camel or name) + ext


def rename(files, lower_first=False):
    return [to_camel_case(os.path.basename(f), lower_first) for f in files]
