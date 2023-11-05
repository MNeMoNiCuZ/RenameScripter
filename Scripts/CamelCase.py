import os
import re  # Import the regular expression module

# Helper function to convert a filename to CamelCase
def to_camel_case(filename):
    """
    This function converts a given filename to CamelCase.
    It removes any non-alphanumeric characters and converts
    the filename to CamelCase where each word starts with a capital letter
    and all the words are joined together without spaces.
    
    Parameters:
    - filename: The original filename (without path).
    
    Returns:
    - The filename converted to CamelCase.
    """
    # Remove file extension and split by non-alphanumeric characters
    name, ext = os.path.splitext(filename)
    words = filter(None, re.split('[^a-zA-Z0-9]+', name))
    # Capitalize the first letter of each word and join them together
    camel_case_name = ''.join(word.capitalize() for word in words)
    # Return the new filename with the original extension
    return camel_case_name + ext

def rename(files):
    """
    The main renaming function that the file renamer tool will call.
    It converts each filename in the provided list to CamelCase.
    
    Parameters:
    - files: A list of full file paths that need to be renamed.
    
    Returns:
    - A list of tuples, each containing the old filename and the new CamelCase filename.
    """
    rename_plan = []  # Initialize the list to store the rename instructions
    for file_path in files:
        filename = os.path.basename(file_path)  # Extract the file name from the path
        new_filename = to_camel_case(filename)  # Convert to CamelCase
        rename_plan.append((filename, new_filename))  # Append the old and new names as a tuple to the rename plan
    return rename_plan  # Return the complete rename plan