"""Launcher for RenameScripter.

    python RenameScripter.py                 # open the GUI
    python RenameScripter.py file1 folder2   # open the GUI with files loaded
    python RenameScripter.py list|preview|apply|check ...   # command line (see --help)
"""

import sys

from renamescripter.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
