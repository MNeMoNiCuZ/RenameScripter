import os
from tkinter import simpledialog

def rename(files):
    rename_plan = []

    # Ask the user for the new extension
    root = simpledialog.Tk()
    root.withdraw()  # Hide the root window
    new_extension = simpledialog.askstring("Input", "Enter the new file extension (with or without the dot):\nLeave empty to remove the extension.", parent=root)
    root.destroy()

    for file_path in files:
        name, current_extension = os.path.splitext(os.path.basename(file_path))
        if new_extension is not None:  # Check if user provided an input
            new_extension = new_extension.strip()
            # Add a dot if the user has not provided it and the field is not empty
            if new_extension and not new_extension.startswith('.'):
                new_extension = '.' + new_extension
        else:
            # If the user wants to remove the extension
            new_extension = ''

        new_filename = f"{name}{new_extension}"
        rename_plan.append((os.path.basename(file_path), new_filename))

    return rename_plan
