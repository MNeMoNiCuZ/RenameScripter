import os
import sys
from pathlib import Path

import pytest

from renamescripter.cli import main as cli_main
from renamescripter.plan import Status, build_plan, name_problem
from renamescripter.renamer import History, RenameError, RenameOp, apply_ops
from renamescripter.scripts import ScriptError, load_script, normalize_result, parse_params


def write_script(tmp_path, name, body):
    path = tmp_path / f"{name}.py"
    path.write_text(body, encoding="utf-8")
    return path


def make_files(folder, *names):
    folder.mkdir(parents=True, exist_ok=True)
    for n in names:
        (folder / n).write_text(n, encoding="utf-8")
    return [folder / n for n in names]


# --- result normalization (all supported return shapes) -------------------

FILES = ["/d/a.txt", "/d/b.txt", "/e/a.txt"]


def test_list_of_names():
    assert normalize_result(FILES, ["1", None, ""]) == ["1", None, None]


def test_legacy_tuples_positional_handles_duplicate_basenames():
    result = [("a.txt", "x"), ("b.txt", "y"), ("a.txt", "z")]
    assert normalize_result(FILES, result) == ["x", "y", "z"]


def test_tuples_out_of_order_and_partial():
    assert normalize_result(FILES, [("b.txt", "y"), ("/e/a.txt", "z")]) == [None, "y", "z"]


def test_dict_result():
    assert normalize_result(FILES, {"/d/b.txt": "y", "a.txt": "x"}) == ["x", "y", None]


@pytest.mark.parametrize("bad", ["abc", 5, ["a"], [("nope.txt", "x")], [1, 2, 3]])
def test_bad_results(bad):
    with pytest.raises(ScriptError):
        normalize_result(FILES, bad)


# --- params ---------------------------------------------------------------

def test_params_shorthand_and_coercion():
    params = {p.key: p for p in parse_params({"n": 3, "flag": False, "s": "x", "c": {"choices": ["a", "b"]}})}
    assert (params["n"].type, params["flag"].type, params["s"].type, params["c"].type) == ("int", "bool", "text", "choice")
    assert params["n"].coerce("7") == 7
    assert params["flag"].coerce("yes") is True
    assert params["c"].default == "a"
    with pytest.raises(ScriptError):
        params["c"].coerce("z")


def test_param_limits():
    (p,) = parse_params({"n": {"type": "int", "default": 5, "min": 1, "max": 10}})
    assert p.coerce(50) == 10 and p.coerce(-1) == 1


def test_script_loading_errors(tmp_path):
    assert "rename" in load_script(write_script(tmp_path, "none", "x = 1")).error
    assert "Failed to load" in load_script(write_script(tmp_path, "boom", "raise ValueError('x')")).error
    assert "Failed to load" in load_script(write_script(tmp_path, "exit", "import sys; sys.exit(1)")).error
    bad_params = write_script(tmp_path, "badp", "PARAMS = {'a': ''}\ndef rename(files):\n    return files")
    assert "keyword" in load_script(bad_params).error
    latin = tmp_path / "latin.py"
    latin.write_bytes("# caf\xe9\ndef rename(files): return files".encode("latin-1"))
    assert "UTF-8" in load_script(latin).error


def test_script_runtime_error_is_wrapped(tmp_path):
    s = load_script(write_script(tmp_path, "err", "def rename(files):\n    raise KeyError('oops')"))
    with pytest.raises(ScriptError, match="oops"):
        s.run(["/a"])


def test_scripts_can_import_helpers_from_their_folder(tmp_path):
    write_script(tmp_path, "_helpers", "def up(s): return s.upper()")
    s = load_script(write_script(tmp_path, "uses", "from _helpers import up\nimport os\ndef rename(files):\n    return [up(os.path.basename(f)) for f in files]"))
    assert s.run(["/x/a.txt"]) == ["A.TXT"]


# --- plan validation ------------------------------------------------------

def test_plan_statuses(tmp_path):
    a, b, c, d = make_files(tmp_path, "a.txt", "b.txt", "c.txt", "d.txt")
    plan = build_plan([a, b, c, d], ["same.txt", "same.txt", "d.txt", None])
    assert [i.status for i in plan.items] == [Status.ERROR, Status.ERROR, Status.ERROR, Status.UNCHANGED]
    assert "already exists" in plan.items[2].message


def test_plan_allows_swap_and_chain(tmp_path):
    a, b, c = make_files(tmp_path, "a", "b", "c")
    plan = build_plan([a, b, c], ["b", "c", "a"])
    assert all(i.status is Status.OK for i in plan.items)


def test_plan_blocked_chain_propagates(tmp_path):
    a, b = make_files(tmp_path, "a", "b")
    # b cannot move (bad name), so a -> b must be blocked too.
    plan = build_plan([a, b], ["b", "x/y"])
    assert [i.status for i in plan.items] == [Status.ERROR, Status.ERROR]


def test_name_rules():
    assert name_problem("") and name_problem("a/b") and name_problem("..")
    assert name_problem("a?b", windows_rules=True) and name_problem("CON.txt", windows_rules=True)
    assert name_problem("ok name.txt", windows_rules=True) is None


# --- renaming -------------------------------------------------------------

def test_swap_apply_and_undo(tmp_path):
    a, b = make_files(tmp_path, "a", "b")
    history = History()
    history.apply([RenameOp(a, b), RenameOp(b, a)])
    assert a.read_text() == "b" and b.read_text() == "a"
    history.undo()
    assert a.read_text() == "a" and b.read_text() == "b"


def test_apply_never_overwrites_and_rolls_back(tmp_path):
    a, b, c = make_files(tmp_path, "a", "b", "c")
    with pytest.raises(RenameError):
        apply_ops([RenameOp(a, tmp_path / "new"), RenameOp(b, c)])
    assert sorted(p.name for p in tmp_path.iterdir()) == ["a", "b", "c"]
    assert c.read_text() == "c"


def test_case_only_rename(tmp_path):
    (a,) = make_files(tmp_path, "abc.txt")
    plan = build_plan([a], ["ABC.txt"])
    assert plan.items[0].status is Status.OK
    apply_ops([RenameOp(a, tmp_path / "ABC.txt")])
    assert [p.name for p in tmp_path.iterdir()] == ["ABC.txt"]


# --- CLI ------------------------------------------------------------------

def test_cli_preview_and_apply(tmp_path, capsys):
    folder = tmp_path / "files"
    make_files(folder, "a b.txt", "c d.txt")
    assert cli_main(["preview", "Replace Space With Underscore", str(folder)]) == 0
    assert "a_b.txt" in capsys.readouterr().out
    assert sorted(os.listdir(folder)) == ["a b.txt", "c d.txt"]  # preview is a dry run
    assert cli_main(["apply", "Search And Replace", str(folder), "-p", "search= ", "-p", "replace=-", "--yes"]) == 0
    assert sorted(os.listdir(folder)) == ["a-b.txt", "c-d.txt"]


def test_cli_rejects_unknown_param(tmp_path, capsys):
    make_files(tmp_path, "a.txt")
    assert cli_main(["preview", "Inverter", str(tmp_path), "-p", "x=1"]) == 2


def test_cli_check_and_list():
    assert cli_main(["check"]) == 0
    assert cli_main(["list", "--json"]) == 0
