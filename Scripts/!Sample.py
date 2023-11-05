import os

# Additional functions to support the renaming logic can be defined here. Example function below:
def custom_function(filename):
    # A helper function that processes the filename and returns a modified version.
    # Perform some operation on the filename
    # Example: Make filename lowercase
    modified_filename = filename.lower()
    return modified_filename

def rename(files):
    # This function is called by the renamer tool
    # It should return a list of tuples with the old and new filenames.
    
    # Initialize the list to store the rename instructions
    rename_plan = []
    for file_path in files:
        # Extract the file name from the path
        filename = os.path.basename(file_path)
        
        # Apply custom renaming logic, or do it directly in this function.
        new_filename = custom_function(filename)
        
        # Append the old and new names as a tuple to the rename plan
        rename_plan.append((filename, new_filename))
    return rename_plan