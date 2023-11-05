import os
from tkinter import simpledialog

def rename(files):
    rename_plan = []

    # Create a root window and hide it
    root = simpledialog.Tk()
    root.withdraw()

    # Ask the user for a prefix
    prefix = simpledialog.askstring("Input", "Enter the prefix to add (optional):", parent=root)
    # Ask the user for a suffix
    suffix = simpledialog.askstring("Input", "Enter the suffix to add (optional):", parent=root)

    # Destroy the root window after input is complete
    root.destroy()

    # Iterate through each file
    for file_path in files:
        file_name, file_extension = os.path.splitext(os.path.basename(file_path))
        
        # Add prefix and suffix if provided
        new_file_name = f"{prefix if prefix else ''}{file_name}{suffix if suffix else ''}{file_extension}"
        rename_plan.append((os.path.basename(file_path), new_file_name))

    return rename_plan
