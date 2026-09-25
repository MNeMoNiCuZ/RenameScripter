import datetime
import os

NAME = "Date As Prefix"
DESCRIPTION = "Adds a date in front of each name, either today's date or the file's modified date."

PARAMS = {
    "source": {"type": "choice", "label": "Date", "choices": ["Today", "File modified date"], "default": "Today"},
    "date_format": {"label": "Format", "default": "%Y-%m-%d", "help": "Python strftime format, e.g. %Y%m%d or %Y-%m-%d_%H%M"},
    "separator": {"label": "Separator", "default": "_"},
}


def rename(files, source="Today", date_format="%Y-%m-%d", separator="_"):
    today = datetime.datetime.now()
    new_names = []
    for path in files:
        if source == "File modified date":
            date = datetime.datetime.fromtimestamp(os.path.getmtime(path))
        else:
            date = today
        new_names.append(f"{date.strftime(date_format)}{separator}{os.path.basename(path)}")
    return new_names
