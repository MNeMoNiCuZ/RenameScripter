"""Discovery, loading and execution of rename scripts from the ``Scripts`` folder.

A rename script is a ``.py`` file that defines ``rename(files, **params)``.
See ``AGENTS.md`` for the full authoring contract. In short:

* ``files`` is a list of absolute path strings, in the order shown in the app.
* ``PARAMS`` (optional) declares options that the GUI renders as input fields
  and passes to ``rename`` as keyword arguments.
* ``rename`` returns the new file *names* in one of these shapes:
    - ``["new1.txt", "new2.txt", ...]`` (same length and order as ``files``)
    - ``[("old.txt", "new.txt"), ...]`` (legacy; old may be a name or a path)
    - ``{"old.txt" or "/full/old.txt": "new.txt", ...}``
  ``None``/``""``/the unchanged name means "leave this file alone".
"""

from __future__ import annotations

import importlib.util
import inspect
import re
import sys
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

PARAM_TYPES = ("text", "int", "float", "bool", "choice")
_TYPE_ALIASES = {"str": "text", "string": "text", "integer": "int", "number": "float", "boolean": "bool", "select": "choice"}
_MODULE_PREFIX = "renamescripter_user_script_"


class ScriptError(Exception):
    """A script failed to load, run, or returned something unusable."""


@dataclass
class Param:
    key: str
    type: str = "text"
    label: str = ""
    default: Any = None
    help: str = ""
    choices: list[str] = field(default_factory=list)
    min: float | None = None
    max: float | None = None
    step: float | None = None
    placeholder: str = ""

    def __post_init__(self) -> None:
        self.type = _TYPE_ALIASES.get(self.type, self.type)
        if self.type not in PARAM_TYPES:
            raise ScriptError(f"Parameter '{self.key}': unknown type '{self.type}' (use one of {', '.join(PARAM_TYPES)})")
        if not self.label:
            self.label = self.key.replace("_", " ").capitalize()
        if self.type == "choice":
            self.choices = [str(c) for c in self.choices]
            if not self.choices:
                raise ScriptError(f"Parameter '{self.key}': type 'choice' needs a non-empty 'choices' list")
        if self.default is None:
            self.default = {"text": "", "int": 0, "float": 0.0, "bool": False, "choice": self.choices[0] if self.choices else ""}[self.type]
        self.default = self.coerce(self.default)

    def coerce(self, value: Any) -> Any:
        """Convert ``value`` (possibly a string from the CLI or settings) to this param's type."""
        try:
            if self.type == "text":
                return "" if value is None else str(value)
            if self.type == "bool":
                if isinstance(value, str):
                    return value.strip().lower() in ("1", "true", "yes", "on", "y")
                return bool(value)
            if self.type == "int":
                result: Any = int(float(value)) if isinstance(value, str) else int(value)
            elif self.type == "float":
                result = float(value)
            else:  # choice
                result = str(value)
                if result not in self.choices:
                    raise ValueError(f"'{result}' is not one of {self.choices}")
                return result
        except (TypeError, ValueError) as exc:
            raise ScriptError(f"Parameter '{self.key}': invalid {self.type} value {value!r} ({exc})") from None
        if self.min is not None and result < self.min:
            result = type(result)(self.min)
        if self.max is not None and result > self.max:
            result = type(result)(self.max)
        return result


def _infer_type(value: Any) -> str:
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    return "text"


def parse_params(raw: Any) -> list[Param]:
    """Parse a script's ``PARAMS`` declaration.

    Accepts a dict ``{key: spec}`` where spec is either a dict of Param fields
    or a plain default value (type inferred), or a list of dicts with a
    ``key`` (or ``name``) entry.
    """
    if raw is None:
        return []
    items: list[tuple[str, Any]]
    if isinstance(raw, Mapping):
        items = list(raw.items())
    elif isinstance(raw, (list, tuple)):
        items = []
        for entry in raw:
            if not isinstance(entry, Mapping) or not (entry.get("key") or entry.get("name")):
                raise ScriptError("PARAMS list entries must be dicts with a 'key'")
            entry = dict(entry)
            key = entry.pop("key", None) or entry.pop("name")
            items.append((key, entry))
    else:
        raise ScriptError("PARAMS must be a dict or a list of dicts")

    params = []
    for key, spec in items:
        if not isinstance(key, str) or not key.isidentifier():
            raise ScriptError(f"Parameter key {key!r} must be a valid Python identifier")
        if isinstance(spec, Mapping):
            spec = dict(spec)
            if "type" not in spec:
                spec["type"] = "choice" if spec.get("choices") else _infer_type(spec.get("default", ""))
            known = set(Param.__dataclass_fields__) - {"key"}
            unknown = set(spec) - known
            if unknown:
                raise ScriptError(f"Parameter '{key}': unknown field(s) {sorted(unknown)}")
            params.append(Param(key=key, **spec))
        else:
            params.append(Param(key=key, type=_infer_type(spec), default=spec))
    return params


def normalize_result(files: Sequence[str], result: Any) -> list[str | None]:
    """Turn whatever ``rename`` returned into one new name (or None) per input file."""
    count = len(files)
    new_names: list[str | None] = [None] * count
    if result is None:
        return new_names

    basenames = [Path(f).name for f in files]

    def lookup(old: Any, used: set[int]) -> int | None:
        old = str(old)
        for i, full in enumerate(files):
            if i not in used and full == old:
                return i
        for i, name in enumerate(basenames):
            if i not in used and name == old:
                return i
        return None

    def set_name(i: int, new: Any) -> None:
        if new is not None and not isinstance(new, str):
            if isinstance(new, Path):
                new = str(new)
            else:
                raise ScriptError(f"New name for '{basenames[i]}' must be a string, got {type(new).__name__}")
        new_names[i] = new or None

    if isinstance(result, Mapping):
        used: set[int] = set()
        for old, new in result.items():
            i = lookup(old, used)
            if i is None:
                raise ScriptError(f"rename() returned a name for unknown file '{old}'")
            used.add(i)
            set_name(i, new)
        return new_names

    if isinstance(result, (str, bytes)) or not isinstance(result, Iterable):
        raise ScriptError(f"rename() must return a list or dict, got {type(result).__name__}")

    result = list(result)
    if all(isinstance(r, (str, Path)) or r is None for r in result):
        if len(result) != count:
            raise ScriptError(f"rename() returned {len(result)} names for {count} files")
        for i, new in enumerate(result):
            set_name(i, new)
        return new_names

    pairs = []
    for r in result:
        if not isinstance(r, (tuple, list)) or len(r) != 2:
            raise ScriptError(f"rename() result entries must be names or (old, new) pairs, got {r!r}")
        pairs.append((str(r[0]), r[1]))

    # Fast path: pairs line up with the input order.
    if len(pairs) == count and all(old in (files[i], basenames[i]) for i, (old, _) in enumerate(pairs)):
        for i, (_, new) in enumerate(pairs):
            set_name(i, new)
        return new_names

    used = set()
    for old, new in pairs:
        i = lookup(old, used)
        if i is None:
            raise ScriptError(f"rename() returned a name for unknown file '{old}'")
        used.add(i)
        set_name(i, new)
    return new_names


@dataclass
class RenameScript:
    key: str
    path: Path
    name: str
    description: str = ""
    params: list[Param] = field(default_factory=list)
    func: Callable[..., Any] | None = None
    error: str | None = None
    uses_tkinter: bool = False

    @property
    def ok(self) -> bool:
        return self.func is not None and self.error is None

    def defaults(self) -> dict[str, Any]:
        return {p.key: p.default for p in self.params}

    def resolve_values(self, values: Mapping[str, Any] | None = None, strict: bool = False) -> dict[str, Any]:
        """Merge ``values`` over the defaults, coercing types.

        Unknown keys raise in strict mode (CLI) and are ignored otherwise
        (stale saved settings). Invalid values fall back to the default unless strict.
        """
        values = dict(values or {})
        resolved = {}
        for p in self.params:
            if p.key in values:
                try:
                    resolved[p.key] = p.coerce(values.pop(p.key))
                except ScriptError:
                    if strict:
                        raise
                    resolved[p.key] = p.default
            else:
                resolved[p.key] = p.default
        if strict and values:
            known = ", ".join(p.key for p in self.params) or "none"
            raise ScriptError(f"Unknown parameter(s) for '{self.name}': {', '.join(values)} (known: {known})")
        return resolved

    def run(self, files: Sequence[str | Path], values: Mapping[str, Any] | None = None, strict: bool = False) -> list[str | None]:
        """Run the script and return one new name (or None for "unchanged") per file."""
        if not self.ok:
            raise ScriptError(self.error or f"Script '{self.name}' has no rename() function")
        file_strs = [str(f) for f in files]
        kwargs = self.resolve_values(values, strict=strict)
        try:
            result = self.func(list(file_strs), **kwargs) if self.params else self.func(list(file_strs))
        except Exception:
            raise ScriptError(f"'{self.name}' raised an error:\n{traceback.format_exc(limit=-3)}") from None
        return normalize_result(file_strs, result)


def _module_name(path: Path) -> str:
    return _MODULE_PREFIX + re.sub(r"\W", "_", path.stem)


def load_script(path: Path) -> RenameScript:
    """Import one script file. Never raises; failures are reported via ``.error``."""
    path = Path(path)
    script = RenameScript(key=path.stem, path=path, name=path.stem)
    try:
        source = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        script.error = "File is not saved as UTF-8. Re-save it with UTF-8 encoding."
        return script
    except OSError as exc:
        script.error = f"Could not read file: {exc}"
        return script
    script.uses_tkinter = bool(re.search(r"^\s*(from|import)\s+tkinter", source, re.MULTILINE))

    module_name = _module_name(path)
    sys.modules.pop(module_name, None)
    added_path = str(path.parent)
    sys.path.insert(0, added_path)
    write_bytecode = sys.dont_write_bytecode
    sys.dont_write_bytecode = True  # keep Scripts/ free of __pycache__
    try:
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            raise ImportError("cannot create import spec")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
    except BaseException:  # noqa: BLE001 - a script calling sys.exit() must not kill the app
        script.error = "Failed to load:\n" + traceback.format_exc(limit=-3)
        sys.modules.pop(module_name, None)
        return script
    finally:
        sys.dont_write_bytecode = write_bytecode
        try:
            sys.path.remove(added_path)
        except ValueError:
            pass

    script.name = str(getattr(module, "NAME", "") or path.stem)
    script.description = inspect.cleandoc(str(getattr(module, "DESCRIPTION", "") or module.__doc__ or ""))
    func = getattr(module, "rename", None)
    if not callable(func):
        script.error = "Script does not define a rename(files) function."
        return script
    try:
        script.params = parse_params(getattr(module, "PARAMS", None))
    except ScriptError as exc:
        script.error = f"Invalid PARAMS: {exc}"
        return script
    if script.params:
        sig = inspect.signature(func)
        accepts_kwargs = any(p.kind is p.VAR_KEYWORD for p in sig.parameters.values())
        missing = [p.key for p in script.params if p.key not in sig.parameters]
        if missing and not accepts_kwargs:
            script.error = f"rename() must accept the declared parameter(s) as keyword arguments: {', '.join(missing)}"
            return script
    script.func = func
    return script


def discover_scripts(directory: Path) -> list[Path]:
    """Script files in ``directory``. Files starting with ``_`` are helpers/templates and are skipped."""
    directory = Path(directory)
    if not directory.is_dir():
        return []
    return sorted(
        (p for p in directory.glob("*.py") if not p.name.startswith("_")),
        key=lambda p: p.stem.lower(),
    )


def load_scripts(directory: Path) -> list[RenameScript]:
    scripts = [load_script(p) for p in discover_scripts(directory)]
    return sorted(scripts, key=lambda s: s.name.lower())


def find_script(scripts: Sequence[RenameScript], name: str) -> RenameScript | None:
    """Find by file stem or display name (case-insensitive)."""
    needle = name.strip().lower().removesuffix(".py")
    for s in scripts:
        if needle in (s.key.lower(), s.name.lower()):
            return s
    return None
