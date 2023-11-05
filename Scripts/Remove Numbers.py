import os
import re

def rename(files):
    rename_plan = []
    for file_path in files:
        filename = os.path.basename(file_path)
        name, ext = os.path.splitext(filename)
        cleaned_name = re.sub(r'\d+', '', name)
        new_filename = f"{cleaned_name}{ext}"
        rename_plan.append((filename, new_filename))
    return rename_plan
