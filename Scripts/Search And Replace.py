import os
from tkinter import simpledialog

def rename(files):
    rename_plan = []

    # Ask the user for the search and replace strings
    root = simpledialog.Tk()
    root.withdraw()  # Hide the root window

    # Get the search string from the user
    search_string = simpledialog.askstring("Input", "Enter the search string:", parent=root)
    if search_string is None:  # If the user pressed cancel
        root.destroy()
        return []  # No operation

    # Get the replace string from the user
    replace_string = simpledialog.askstring("Input", "Enter the replace string:", parent=root)
    if replace_string is None:  # If the user pressed cancel
        root.destroy()
        return []  # No operation

    root.destroy()

    # Go through the list of files and create a rename plan
    for file_path in files:
        file_name = os.path.basename(file_path)
        # Replace the search string with the replace string in the file name
        new_file_name = file_name.replace(search_string, replace_string)
        rename_plan.append((file_name, new_file_name))

    return rename_plan
