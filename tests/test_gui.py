"""Headless smoke test of the Qt window (skipped when PySide6 is unavailable)."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtWidgets = pytest.importorskip("PySide6.QtWidgets")

from renamescripter import paths  # noqa: E402
from renamescripter.settings import Settings  # noqa: E402


@pytest.fixture(scope="module")
def app():
    try:
        return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    except Exception as exc:  # pragma: no cover - e.g. missing system GL libraries
        pytest.skip(f"Qt cannot start: {exc}")


def test_preview_rename_undo(app, tmp_path):
    from renamescripter.gui.main_window import MainWindow

    folder = tmp_path / "files"
    folder.mkdir()
    for n in ("a 1.txt", "b 2.txt"):
        (folder / n).write_text(n)
    settings = Settings(tmp_path / "settings.json")
    settings["confirm_rename"] = False
    w = MainWindow(settings, paths.scripts_dir(), [str(folder)])
    names = [w.script_list.item(i).text() for i in range(w.script_list.count())]
    w.script_list.setCurrentRow(names.index("Replace Space With Underscore"))
    w.run_preview()
    assert [i.new_name for i in w.model.plan.items] == ["a_1.txt", "b_2.txt"]
    w.rename_files()
    assert sorted(os.listdir(folder)) == ["a_1.txt", "b_2.txt"]
    assert [p.name for p in w.model.files] == ["a_1.txt", "b_2.txt"]
    w.undo()
    assert sorted(os.listdir(folder)) == ["a 1.txt", "b 2.txt"]
    w.close()
    assert (tmp_path / "settings.json").exists()
