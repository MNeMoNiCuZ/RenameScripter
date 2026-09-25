import os

NAME = "Replace Space With Underscore"
DESCRIPTION = "Replaces every space in the file name with an underscore."


def rename(files):
    return [os.path.basename(f).replace(" ", "_") for f in files]
