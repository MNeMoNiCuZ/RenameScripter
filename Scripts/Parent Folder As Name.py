import os

def rename(files):
    rename_plan = []
    
    # Create a preview list of new names
    for file_path in files:
        directory, file_name = os.path.split(file_path)
        folder_name = os.path.basename(directory)
        file_extension = os.path.splitext(file_name)[1]
        new_name = f"{folder_name}{file_extension}"
        rename_plan.append((file_name, new_name))
    
    return rename_plan
