import os

NAME = "Inverter"
DESCRIPTION = "Reverses the file name (the extension is kept): 'abc.txt' -> 'cba.txt'."


def rename(files):
    new_names = []
    for path in files:
        name, ext = os.path.splitext(os.path.basename(path))
        new_names.append(name[::-1] + ext)
    return new_names
