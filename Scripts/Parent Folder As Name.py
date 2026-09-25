import os

NAME = "Parent Folder As Name"
DESCRIPTION = "Names each file after the folder it is in. Files that would share a name get a number."

PARAMS = {
    "number_duplicates": {"type": "bool", "label": "Number files that share a folder", "default": True},
    "separator": {"label": "Number separator", "default": "_"},
    "padding": {"type": "int", "label": "Number digits", "default": 2, "min": 1, "max": 6},
}


def rename(files, number_duplicates=True, separator="_", padding=2):
    # Count how many files would get the same name so only those are numbered.
    targets = []
    for path in files:
        folder = os.path.basename(os.path.dirname(path))
        ext = os.path.splitext(path)[1]
        targets.append((os.path.dirname(path), folder, ext.lower()))
    counts = {}
    for t in targets:
        counts[t] = counts.get(t, 0) + 1

    seen = {}
    new_names = []
    for path, (directory, folder, _ext) in zip(files, targets):
        ext = os.path.splitext(path)[1]
        key = (directory, folder, _ext)
        if number_duplicates and counts[key] > 1:
            seen[key] = seen.get(key, 0) + 1
            new_names.append(f"{folder}{separator}{seen[key]:0{padding}d}{ext}")
        else:
            new_names.append(f"{folder}{ext}")
    return new_names
