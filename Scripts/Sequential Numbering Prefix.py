import os

def rename(files):
    rename_plan = []
    for index, file_path in enumerate(files, start=1):  # Start numbering at 1
        filename = os.path.basename(file_path)
        new_filename = f"{index:03d}_{filename}"  # 03d will pad the number with zeros (001, 002, ...)
        rename_plan.append((filename, new_filename))
    return rename_plan
