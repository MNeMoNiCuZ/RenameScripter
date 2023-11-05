import os
import datetime

def rename(files):
    rename_plan = []
    current_date = datetime.datetime.now().strftime('%Y-%m-%d')  # Format: YYYY-MM-DD
    for file_path in files:
        filename = os.path.basename(file_path)
        new_filename = f"{current_date}_{filename}"
        rename_plan.append((filename, new_filename))
    return rename_plan
