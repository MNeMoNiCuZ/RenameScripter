import os

def invert_filename(filename):
    name, ext = os.path.splitext(filename)
    inverted_name = name[::-1]
    return inverted_name + ext

def rename(files):
    rename_plan = []
    for file in files:
        filename = os.path.basename(file)
        new_name = invert_filename(filename)
        rename_plan.append((filename, new_name))
    return rename_plan
