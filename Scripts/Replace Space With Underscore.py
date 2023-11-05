import os

def rename(files):
    rename_plan = []
    for file_path in files:
        filename = os.path.basename(file_path)
        new_filename = filename.replace(' ', '_')
        rename_plan.append((filename, new_filename))
    return rename_plan
