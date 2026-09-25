"""Every script shipped in Scripts/ must load and pass the same check the CLI runs."""

import pytest

from renamescripter import paths
from renamescripter.cli import check_script
from renamescripter.scripts import discover_scripts, load_script

SCRIPT_FILES = discover_scripts(paths.scripts_dir())


def test_scripts_folder_not_empty():
    assert SCRIPT_FILES


@pytest.mark.parametrize("path", SCRIPT_FILES, ids=[p.stem for p in SCRIPT_FILES])
def test_script(path):
    script = load_script(path)
    assert script.ok, script.error
    assert not script.uses_tkinter, "bundled scripts should declare PARAMS instead of opening tkinter dialogs"
    errors = [p for p in check_script(script) if not p.startswith("warning:")]
    assert not errors, "\n".join(errors)


def test_template_is_valid():
    script = load_script(paths.scripts_dir() / "_Template.py")
    assert script.ok, script.error
    assert script.run(["/x/a.txt"], {"text": "_b"}) == ["a_b.txt"]
