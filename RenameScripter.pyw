import os
import subprocess
import sys
import configparser
import uuid
import tkinter as tk
from tkinter import ttk, messagebox
from tkinter import font as tkFont
from tkinterdnd2 import DND_FILES, TkinterDnD


# Function to check and install required modules
def check_and_install_module(module_name):
    try:
        __import__(module_name)
    except ImportError:
        print(f"Installing required module: {module_name}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", module_name])

# Check for required modules
check_and_install_module("tkinter")
check_and_install_module("tkinterdnd2")

# Global variables to store the state of previous renaming actions and the last used directory
previous_state = {}
last_directory = ""

# Constants to define different modes for the preview/rename button
PREVIEW_MODE = 1
RENAME_MODE = 2
button_mode = PREVIEW_MODE  # Initial state of the button

# Constants for button states
PREVIEW_BUTTON_TEXT = "Preview [F2]"
RENAME_BUTTON_TEXT = "Rename [F2]"
CLEAR_BUTTON_TEXT = "Clear [CTRL+W]"
UNDO_BUTTON_TEXT = "Undo [CTRL+Z]"

def handle_f2_key(event=None):
    global button_mode
    print("F2 Pressed. Current button_mode:", "RENAME_MODE" if button_mode == RENAME_MODE else "PREVIEW_MODE")
    if button_mode == PREVIEW_MODE:
        run_selected_script()
    elif button_mode == RENAME_MODE:
        rename_files()

# Get the directory of the currently executing script
script_directory = os.path.dirname(os.path.abspath(__file__))

# Now join this with the relative path to your config.ini file.
config_path = os.path.join(script_directory, 'Settings', 'config.ini')

def read_config(config_path):
    config = configparser.ConfigParser()
    config.read(config_path)
    return config

# Save Config
def save_config(config_path, script_name, auto_preview_state):
    config = read_config(config_path)
    if 'Settings' not in config:
        config['Settings'] = {}
    config['Settings']['last_selected_script'] = script_name
    config['Settings']['auto_preview'] = str(auto_preview_state)
    with open(config_path, 'w') as configfile:
        config.write(configfile)

# Make sure the Settings directory exists
if not os.path.exists(os.path.join(script_directory, 'Settings')):
    os.makedirs(os.path.join(script_directory, 'Settings'))

# Make sure the config.ini file exists
config_path = os.path.join(script_directory, 'Settings', 'config.ini')
if not os.path.isfile(config_path):
    # Open the file with 'w+' to create it if it doesn't exist
    with open(config_path, 'w+') as f:
        f.write('[Settings]\n')
        f.write('last_selected_script=\n')
        f.write('auto_preview=True\n')

def get_all_files_from_directory(directory):
    """Recursively fetch all files from a directory."""
    all_files = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            all_files.append(os.path.join(root, file))
    return all_files

def apply_renaming(rename_plan):
    global previous_state, undo_button
    previous_state = {}

    # Iterate over each file in the rename plan and perform the renaming operation
    for old_full_path, new_name, directory in rename_plan:
        new_full_path = os.path.join(directory, new_name)

        # Adding detailed logging before attempting to rename
        print(f"Attempting to rename: '{old_full_path}' to '{new_full_path}'")

        try:
            # Direct renaming without intermediate step
            os.rename(old_full_path, new_full_path)
            previous_state[new_name] = os.path.basename(old_full_path)
            print(f"Successfully renamed: '{old_full_path}' to '{new_full_path}'")
        except Exception as e:
            print(f"Error renaming: {e} | From '{old_full_path}' to '{new_full_path}'")

    if previous_state:  # Only enable the undo button if at least one file was renamed
        undo_button.config(state=tk.NORMAL)

    return bool(previous_state)  # Return True if at least one file was renamed, False otherwise

def undo_renaming():
    global undo_button, files_to_rename
    if not previous_state:
        messagebox.showinfo("Undo Unavailable", "No renaming action to undo.")
        return

    # Iterate over the previous state to revert the renaming actions
    for new_name, old_name in previous_state.items():
        new_full_path = os.path.join(last_directory, new_name)
        old_full_path = os.path.join(last_directory, old_name)
        try:
            os.rename(new_full_path, old_full_path)
        except Exception as e:
            print(f"! Error: {e}")

    messagebox.showinfo("Undo Complete", "Previous renaming has been undone.")
    undo_button.config(state=tk.DISABLED)

    # Refresh the file list in the treeview and the files_to_rename list
    file_treeview.delete(*file_treeview.get_children())
    files_to_rename.clear()  # Clear the existing list of files to rename

    # Repopulate the file list with the original names
    for _, old_name in previous_state.items():
        file_treeview.insert("", "end", values=(old_name, ""))  # Insert the original name as 'Old Name'
        files_to_rename.append(os.path.join(last_directory, old_name))  # Append the original name to files_to_rename list

    # Clear previous_state after undo
    previous_state.clear()

def is_utf8(filename):
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            f.read()
        return True
    except UnicodeDecodeError:
        return False    

# Dynamically import renaming scripts from the 'scripts' directory
# Current directory of the script
current_script_directory = os.path.dirname(os.path.abspath(__file__))

# Dynamically import renaming scripts from the 'scripts' directory
SCRIPT_DIR = os.path.join(current_script_directory, "Scripts")
script_files = [f[:-3] for f in os.listdir(SCRIPT_DIR) if f.endswith('.py')]
script_functions = {}

non_utf8_files = []

# Add the SCRIPT_DIR to the system path to allow importing modules
sys.path.insert(0, SCRIPT_DIR)

for script in script_files:
    script_path = os.path.join(SCRIPT_DIR, script + ".py")
    if not is_utf8(script_path):
        non_utf8_files.append(script_path)
    else:
        try:
            # Import the script using the module name only, without the directory
            script_module = __import__(script, fromlist=[script])
            standard_function_name = "rename"  # The standard function name
            if hasattr(script_module, standard_function_name):
                script_functions[script] = getattr(script_module, standard_function_name)
        except Exception as e:
            print(f"Error loading {script}: {e}")

# Remove the SCRIPT_DIR from the system path after importing to avoid conflicts
sys.path.remove(SCRIPT_DIR)


if non_utf8_files:
    warning_msg = "\nThe following files are not saved with UTF-8 encoding and may cause issues:\n"
    warning_msg += "\n".join(non_utf8_files)
    warning_msg += "\nPlease convert them to UTF-8 and restart the application."
    messagebox.showwarning("Encoding Warning", warning_msg)


def on_script_select(files, chosen_script):
    # Generate and preview the rename plan based on the selected script and user confirmation
    renaming_function = script_functions[chosen_script]
    rename_plan = renaming_function(files)
    
    # Modify the rename plan to include full file path, new name, and directory
    modified_rename_plan = []
    for old, new in rename_plan:
        full_old_path = next((f for f in files if os.path.basename(f) == old), None)
        if full_old_path:
            directory = os.path.dirname(full_old_path)
            modified_rename_plan.append((full_old_path, new, directory))

    # Preview the renaming to the user
    plan_str = "\n".join([f"{old} -> {new}" for old, new in modified_rename_plan])
    is_proceed = messagebox.askyesno("Preview Renaming", f"Do you want to proceed with the following renaming?\n\n{plan_str}")
        
    if is_proceed:
        apply_renaming(modified_rename_plan)
        messagebox.showinfo("Renaming Complete", "Files have been renamed.")
    else:
        messagebox.showinfo("Renaming Cancelled", "Files renaming has been cancelled.")

# Global variable to hold the list of files to rename
files_to_rename = []

def get_all_files_from_directory(directory):
    # This function will return all file paths from the given directory, including subdirectories.
    file_paths = []
    for root, _, files in os.walk(directory):
        for file in files:
            file_paths.append(os.path.join(root, file))
    return file_paths

def on_drop(event):
    # Clear the existing files
    clear_files()

    # The dropped data may be in one long string. If the paths have spaces, they'll be enclosed in {}.
    # We'll split the data accordingly.
    dropped_items = []
    temp = ''
    in_braces = False
    for char in event.data:
        if char == '{':
            in_braces = True
            temp += char
        elif char == '}' and in_braces:
            in_braces = False
            temp += char
            dropped_items.append(temp)
            temp = ''
        elif in_braces:
            temp += char
        elif char == ' ' and not in_braces:
            if temp:
                dropped_items.append(temp)
                temp = ''
        else:
            temp += char
    if temp:  # Add the last item if there is one
        dropped_items.append(temp)

    # Clean the dropped items from any leading/trailing braces and whitespace
    dropped_items = [item.strip('{} \n\r') for item in dropped_items]

    # Process dropped items (files/directories) and add them to the renaming list
    for item in dropped_items:
        # Check if the item is a directory or a file
        if os.path.isdir(item):
            # If it's a directory, get all files recursively
            for root, _, files in os.walk(item):
                for file in files:
                    file_path = os.path.join(root, file)
                    if file_path not in files_to_rename:
                        files_to_rename.append(file_path)
                        file_treeview.insert("", "end", values=(os.path.basename(file_path), ""))
        elif os.path.isfile(item):
            # If it's a file, process as usual
            if item not in files_to_rename:
                files_to_rename.append(item)
                file_treeview.insert("", "end", values=(os.path.basename(item), ""))

    # Update button states after processing dropped files/folders
    update_button_state()

def clear_files():
    global files_to_rename
    files_to_rename = []
    file_treeview.delete(*file_treeview.get_children())
    update_button_state()

def run_selected_script():
    chosen_script = script_listbox.get(script_listbox.curselection())
    if not chosen_script:
        messagebox.showerror("Error", "Please select a renaming script from the list.")
        return

    # Ensure there are files to rename
    if not files_to_rename:
        messagebox.showerror("Error", "No files to rename. Please add files to the list.")
        return

    renaming_function = script_functions[chosen_script]
    try:
        rename_plan = renaming_function(files_to_rename)
    except Exception as e:
        messagebox.showerror("Error", f"An error occurred while generating the rename plan: {e}")
        return
    
    # Clear any existing "New Name" entries before setting the new names.
    for item in file_treeview.get_children():
        file_treeview.set(item, 'New Name', '')  # Reset to empty string

    # Set new names only for files that match the rename script's criteria
    for item, (old_name, new_name) in zip(file_treeview.get_children(), rename_plan):
        file_treeview.set(item, 'New Name', new_name)
    
    # Change the button to 'Rename Files' if the auto-preview is checked
    global button_mode
    button_mode = RENAME_MODE
    update_button_state()

def toggle_rename_button():
    global button_mode
    if button_mode == PREVIEW_MODE:
        button_mode = RENAME_MODE
        run_button.config(text=RENAME_BUTTON_TEXT, command=rename_files)
    else:
        button_mode = PREVIEW_MODE
        run_button.config(text=PREVIEW_BUTTON_TEXT, command=run_selected_script)

    #update_button_state()
    
    #global button_mode
    #if button_mode == PREVIEW_MODE:
    #    button_mode = RENAME_MODE
    #    run_button.config(text=RENAME_BUTTON_TEXT, command=rename_files)
    #else:
    #    button_mode = PREVIEW_MODE
    #    run_button.config(text=PREVIEW_BUTTON_TEXT, command=run_selected_script)

def clear_rename_plan():
    global rename_plan
    rename_plan = []

def rename_files():
    global run_button, files_to_rename, button_mode  # Declare button_mode as global

    # Ensure there is at least one file to rename
    if not files_to_rename:
        messagebox.showinfo("No Files", "No files to rename.")
        return

    # Get the configuration
    config = read_config(config_path)
    ask_confirmation = config.getboolean('Settings', 'ask_confirmation', fallback=True)

    # Modify the rename plan to include full file path, new name, and directory
    modified_rename_plan = []
    for item in file_treeview.get_children():
        old_name = file_treeview.set(item, 'Old Name')
        new_name = file_treeview.set(item, 'New Name')
        full_old_path = next((f for f in files_to_rename if os.path.basename(f) == old_name), None)
        if full_old_path:
            directory = os.path.dirname(full_old_path)
            modified_rename_plan.append((full_old_path, new_name, directory))

    is_proceed = True
    if ask_confirmation:
        # Ask user for confirmation before proceeding with renaming
        is_proceed = messagebox.askyesno("Confirm Renaming", "Do you want to proceed with the renaming?")

    if is_proceed:
        # Apply the renaming
        try:
            successful_renames = apply_renaming(modified_rename_plan)
            if successful_renames and ask_confirmation:
                messagebox.showinfo("Renaming Complete", "Files have been renamed.")

            # Clear the treeview and repopulate with new names, keeping original names for files that were not renamed
            file_treeview.delete(*file_treeview.get_children())
            files_to_rename.clear()  # Clear the existing list of files to rename

            for full_old_path, new_name, directory in modified_rename_plan:
                if new_name:  # Only update the name if a new name was provided
                    file_treeview.insert("", "end", values=(new_name, ""))
                    files_to_rename.append(os.path.join(directory, new_name))  # Append the new name to files_to_rename list
                else:
                    old_name = os.path.basename(full_old_path)
                    file_treeview.insert("", "end", values=(old_name, ""))
                    files_to_rename.append(full_old_path)  # Re-append the old name to files_to_rename list

            # Reset the button to "Preview Name" after renaming is complete
            button_mode = PREVIEW_MODE
            run_button.config(text=PREVIEW_BUTTON_TEXT, command=run_selected_script)

        except Exception as e:
            messagebox.showerror("Error", f"An error occurred while renaming files: {e}")

    button_mode = PREVIEW_MODE  # Reset to preview mode after renaming
    update_button_state()  # Update the button state to reflect the change
    clear_rename_plan()  # Clear the rename plan to prevent redundant renames
    # Save the last selected script
    save_config(config_path, script_listbox.get(script_listbox.curselection()), auto_preview_var.get())


# Global function to update the state of the "Preview Name" button
def update_button_state():
    # Get the current selection in the script listbox
    script_selected = len(script_listbox.curselection()) != 0
    # Check if there are files listed for renaming
    files_available = len(files_to_rename) > 0

    print("update_button_state called. Current button_mode:", "RENAME_MODE" if button_mode == RENAME_MODE else "PREVIEW_MODE")
    
    # If there is a script selected and files are available, enable the button
    if script_selected and files_available:
        run_button.config(state=tk.NORMAL)
        if button_mode == PREVIEW_MODE:
            run_button.config(text=PREVIEW_BUTTON_TEXT, command=run_selected_script)
        elif button_mode == RENAME_MODE:
            run_button.config(text=RENAME_BUTTON_TEXT, command=rename_files)
    else:
        run_button.config(state=tk.DISABLED)

def main():
    print("Entering main function...")  # Debug print
    global root, script_listbox, file_treeview, run_button, undo_button, auto_preview_checkbox, auto_preview_var

    # Set up the main GUI elements including frames, buttons, and treeview for file listing
    root = TkinterDnD.Tk()
    root.title("Rename Scripter")
    icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Settings', 'icon.ico')
    if os.path.exists(icon_path):
        root.iconbitmap(icon_path)
    else:
        print(f"Icon file not found at {icon_path}")
    root.geometry("900x700")  # Adjust the window size

    # Initialize the variable for Auto Preview before reading the config
    auto_preview_var = tk.IntVar()
    config = read_config(config_path)
    auto_preview_state = config.getboolean('Settings', 'auto_preview', fallback=True)
    auto_preview_var.set(auto_preview_state)
    last_used_script = config.get('Settings', 'last_selected_script', fallback=None)

    # Create a frame to hold the buttons on their own row
    button_frame = ttk.Frame(root)
    button_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=(10, 0))  # Add some vertical padding here

    # Button to run the selected script
    run_button = ttk.Button(button_frame, text=PREVIEW_BUTTON_TEXT, command=run_selected_script)

    run_button.pack(side=tk.LEFT, padx=5, pady=10)
    run_button['padding'] = (10, 10)

    # Button to clear the file list
    clear_button = ttk.Button(button_frame, text=CLEAR_BUTTON_TEXT, command=clear_files)
    clear_button.pack(side=tk.LEFT, padx=5, pady=10)
    clear_button['padding'] = (10, 10)

    # Add a button for undo functionality
    undo_button = ttk.Button(button_frame, text=UNDO_BUTTON_TEXT, command=undo_renaming, state=tk.DISABLED)
    undo_button.pack(side=tk.LEFT, padx=5, pady=10)
    undo_button['padding'] = (10, 10)

    # Create a checkbox for "Automatically Preview"
    auto_preview_checkbox = ttk.Checkbutton(button_frame, text="Automatically Preview", variable=auto_preview_var)
    auto_preview_checkbox.pack(side=tk.LEFT, padx=5, pady=10)

    def toggle_auto_preview():
        # This function will be called whenever the checkbox is toggled
        auto_preview_state = auto_preview_var.get()
        save_config(config_path, script_listbox.get(script_listbox.curselection()), auto_preview_state)

    auto_preview_checkbox.config(command=toggle_auto_preview)

    # Create a main frame that will contain the listbox and the treeview side by side
    main_frame = ttk.Frame(root)
    main_frame.pack(side=tk.TOP, padx=10, pady=5, fill=tk.BOTH, expand=True)  # Allow frame to fill and expand vertically

    # Create the frame for the renaming scripts listbox and add a scrollbar
    script_frame = ttk.Frame(main_frame, width=200)  # Set the maximum width
    script_frame.pack(side=tk.LEFT, fill=tk.Y, expand=False)  # Prevent the frame from expanding
    script_frame.pack_propagate(False)  # Prevent the frame from shrinking to fit its contents

    # Configure the scrollbar
    script_scrollbar = ttk.Scrollbar(script_frame, orient="vertical")
    # Configure the listbox to work with the scrollbar
    script_listbox = tk.Listbox(script_frame, yscrollcommand=script_scrollbar.set, width=100, exportselection=False)
    script_scrollbar.config(command=script_listbox.yview)
    script_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    script_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)  # Ensure the listbox fills the frame and scrollbar area

    # After setting up the UI, disable the "Preview Name" button if there are no files to rename
    if not files_to_rename:
        run_button.config(state=tk.DISABLED)

    # After populating the listbox with the script names
    for script in script_functions:
        script_listbox.insert(tk.END, script)

    # Attempt to select the last used script if it's in the list
    if last_used_script in script_files:
        last_script_index = script_files.index(last_used_script)
        script_listbox.selection_set(last_script_index)
    else:
        script_listbox.selection_set(0)  # Default to the first script if not found or if None


    # Create the frame for the Old Name and New Name fields and add a scrollbar
    name_frame = ttk.Frame(main_frame)
    name_frame.pack(side=tk.LEFT, padx=10, fill=tk.BOTH, expand=True)  # Allow frame to fill and expand

    file_treeview = ttk.Treeview(name_frame, columns=("Old Name", "New Name"), show="headings")
    file_treeview.column("Old Name", width=200)  # Adjust the width as needed
    file_treeview.column("New Name", width=200)
    file_treeview.heading("Old Name", text="Old Name")
    file_treeview.heading("New Name", text="New Name")
    treeview_scrollbar = ttk.Scrollbar(name_frame, orient="vertical", command=file_treeview.yview)
    file_treeview.config(yscrollcommand=treeview_scrollbar.set)
    treeview_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    file_treeview.pack(side=tk.LEFT, padx=10, fill=tk.BOTH, expand=True)  # Allow treeview to fill and expand

    # Add drag and drop bindings for the file_treeview
    file_treeview.drop_target_register(DND_FILES)
    file_treeview.dnd_bind('<<Drop>>', on_drop)

    # Button state reset function
    def reset_button_to_preview(event=None):
        run_button.config(text="Preview Name [F2]", command=run_selected_script)

 # Update button to 'Preview Name' when a new script is selected
    def on_script_list_select(event=None):
        global button_mode
        # Update the button state based on current conditions
        update_button_state()
        # Automatically run the selected script if the checkbox is checked, without checking the button mode
        if auto_preview_var.get():
            run_selected_script()
        else:
            button_mode = PREVIEW_MODE
            run_button.config(text=PREVIEW_BUTTON_TEXT, command=run_selected_script)

    # Bind the on_script_select function to the script listbox selection event
    script_listbox.bind("<<ListboxSelect>>", on_script_list_select)

    # Process command-line arguments for dragged files
    if len(sys.argv) > 1:
        # Exclude the script name and get only the file paths
        dragged_files = sys.argv[1:]
        # Add the dragged files to the files_to_rename list and the file_treeview
        for file in dragged_files:
            if file not in files_to_rename:
                files_to_rename.append(file)
                file_treeview.insert("", "end", values=(os.path.basename(file), ""))
        update_button_state()
        if auto_preview_var.get():
            run_selected_script()
    def handle_ctrl_z_key(event):
        print("CTRL+Z Pressed")  # Debug print statement
        # Directly call the function without any condition check
        undo_renaming()

    # Bind CTRL + W to clear files
    def handle_ctrl_w_key(event):
        print("CTRL+W Pressed")  # Debug print statement
        clear_files()

    # Add this line to ensure the root window captures key events
    root.focus_force()

    # Add hotkeys to the application
    root.bind('<F2>', handle_f2_key)
    root.bind('<Control-z>', handle_ctrl_z_key)
    root.bind('<Control-w>', handle_ctrl_w_key)

    # Run the application
    print("Starting main loop...")  # Debug print
    root.mainloop()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"An uncaught exception occurred: {e}")
        # Depending on the exception, you may want to import traceback and print the full stack trace
        import traceback
        traceback.print_exc()
        input("Press Enter to exit...")  # This will keep the command window open until you press Enter
