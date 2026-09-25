import os

NAME = "Sequential Numbering Prefix"
DESCRIPTION = "Puts a running number in front of each name, in the order shown in the file list."

PARAMS = {
    "start": {"type": "int", "label": "Start at", "default": 1, "min": 0, "max": 999999},
    "padding": {"type": "int", "label": "Digits", "default": 3, "min": 1, "max": 10},
    "separator": {"label": "Separator", "default": "_"},
    "per_folder": {"type": "bool", "label": "Restart numbering in each folder", "default": False},
}


def rename(files, start=1, padding=3, separator="_", per_folder=False):
    counters = {}
    new_names = []
    for path in files:
        key = os.path.dirname(path) if per_folder else None
        number = counters.get(key, start)
        counters[key] = number + 1
        new_names.append(f"{number:0{padding}d}{separator}{os.path.basename(path)}")
    return new_names
