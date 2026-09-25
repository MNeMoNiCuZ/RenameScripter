"""Main application window."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Any

from PySide6.QtCore import QByteArray, QFileSystemWatcher, QSize, Qt, QTimer, QUrl
from PySide6.QtGui import QAction, QDesktopServices, QIcon, QKeySequence, QPalette
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStackedWidget,
    QStyle,
    QTableView,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from .. import APP_NAME, __version__, paths
from ..files import expand_paths, merge_unique
from ..plan import build_plan
from ..renamer import History, RenameError, ops_from_plan
from ..scripts import RenameScript, ScriptError, load_scripts
from ..settings import Settings
from .file_model import COL_FOLDER, COL_NEW, COL_OLD, COL_STATUS, FileTableModel
from .param_form import ParamForm

REPO_URL = "https://github.com/MNeMoNiCuZ/RenameScripter"
PREVIEW_DELAY_MS = 150


class MainWindow(QMainWindow):
    def __init__(self, settings: Settings, scripts_dir: Path, initial_paths: list[str] | None = None) -> None:
        super().__init__()
        self.settings = settings
        self.scripts_dir = scripts_dir
        self.scripts: list[RenameScript] = []
        self.current: RenameScript | None = None
        self.history = History()
        self.plan_current = False
        self._pending_values: dict[str, Any] | None = None

        self.setWindowTitle(APP_NAME)
        icon_path = paths.resource_path("Settings/icon.ico")
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        self.setAcceptDrops(True)
        self.resize(1100, 700)

        self.preview_timer = QTimer(self, singleShot=True, interval=PREVIEW_DELAY_MS)
        self.preview_timer.timeout.connect(self.run_preview)
        self.reload_timer = QTimer(self, singleShot=True, interval=300)
        self.reload_timer.timeout.connect(self.reload_scripts)
        self.watcher = QFileSystemWatcher(self)
        self.watcher.directoryChanged.connect(lambda _: self.reload_timer.start())
        self.watcher.fileChanged.connect(lambda _: self.reload_timer.start())

        self._build_actions()
        self._build_ui()
        self._build_menus()
        self._restore_window_state()
        QApplication.styleHints().colorSchemeChanged.connect(lambda _: self._apply_style())

        self.reload_scripts(initial=True)
        if initial_paths:
            self.add_paths(initial_paths)
        self._update_ui()

    # ------------------------------------------------------------------ UI
    def _icon(self, standard: QStyle.StandardPixmap) -> QIcon:
        return self.style().standardIcon(standard)

    def _action(self, text: str, slot, shortcut: Any = None, icon: QStyle.StandardPixmap | None = None, tip: str = "") -> QAction:
        action = QAction(text, self)
        if icon is not None:
            action.setIcon(self._icon(icon))
        if shortcut is not None:
            action.setShortcut(QKeySequence(shortcut))
        shortcut_text = action.shortcut().toString(QKeySequence.SequenceFormat.NativeText)
        action.setToolTip(f"{tip or text.replace('…', '')}" + (f" ({shortcut_text})" if shortcut_text else ""))
        action.triggered.connect(slot)
        self.addAction(action)
        return action

    def _toggle(self, text: str, key: str) -> QAction:
        action = QAction(text, self, checkable=True)
        action.setChecked(bool(self.settings[key]))

        def changed(checked: bool) -> None:
            self.settings[key] = checked
            self.settings.save()
            if key in ("live_preview", "include_subfolders"):
                self.request_preview()

        action.toggled.connect(changed)
        return action

    def _build_actions(self) -> None:
        SP = QStyle.StandardPixmap
        self.act_add_files = self._action("Add Files…", self.add_files_dialog, QKeySequence.StandardKey.Open, SP.SP_FileIcon)
        self.act_add_folder = self._action("Add Folder…", self.add_folder_dialog, "Ctrl+Shift+O", SP.SP_DirIcon)
        self.act_remove = self._action("Remove", self.remove_selected, QKeySequence.StandardKey.Delete, SP.SP_DialogDiscardButton, "Remove selected files from the list")
        self.act_clear = self._action("Clear", self.clear_files, "Ctrl+W", SP.SP_DialogResetButton, "Clear the file list")
        self.act_preview = self._action("Preview", self.run_preview, "F5", SP.SP_BrowserReload)
        self.act_rename = self._action("Rename", self.rename_files, "F2", SP.SP_DialogApplyButton)
        self.act_rename_alt = QAction(self)
        self.act_rename_alt.setShortcut(QKeySequence("Ctrl+Return"))
        self.act_rename_alt.triggered.connect(self.rename_files)
        self.addAction(self.act_rename_alt)
        self.act_undo = self._action("Undo", self.undo, QKeySequence.StandardKey.Undo, SP.SP_ArrowBack, "Undo the last rename")
        self.act_reload = self._action("Reload Scripts", lambda: self.reload_scripts(), "Ctrl+R", SP.SP_BrowserReload)
        self.act_open_scripts = self._action("Open Scripts Folder", self.open_scripts_folder, None, SP.SP_DirOpenIcon)
        self.act_new_script = self._action("New Script…", self.new_script, "Ctrl+N", SP.SP_FileDialogNewFolder, "Create a new script from the template")
        self.act_edit_script = self._action("Edit Selected Script", self.edit_script, "Ctrl+E", None)
        self.act_find = self._action("Find Script", lambda: (self.search.setFocus(), self.search.selectAll()), QKeySequence.StandardKey.Find)
        self.act_quit = self._action("Quit", self.close, QKeySequence.StandardKey.Quit)

        self.opt_live = self._toggle("Live Preview", "live_preview")
        self.opt_confirm = self._toggle("Confirm Before Renaming", "confirm_rename")
        self.opt_remember_script = self._toggle("Remember Last Used Script", "remember_last_script")
        self.opt_remember_params = self._toggle("Remember Script Options", "remember_params")
        self.opt_subfolders = self._toggle("Include Subfolders When Adding Folders", "include_subfolders")

    def _build_menus(self) -> None:
        bar = self.menuBar()
        m = bar.addMenu("&File")
        m.addActions([self.act_add_files, self.act_add_folder])
        m.addSeparator()
        m.addActions([self.act_remove, self.act_clear])
        m.addSeparator()
        m.addAction(self.act_quit)

        m = bar.addMenu("&Edit")
        m.addActions([self.act_preview, self.act_rename, self.act_undo])

        m = bar.addMenu("&Scripts")
        m.addActions([self.act_find, self.act_reload, self.act_new_script, self.act_edit_script, self.act_open_scripts])

        m = bar.addMenu("S&ettings")
        m.addActions([self.opt_live, self.opt_confirm, self.opt_remember_script, self.opt_remember_params, self.opt_subfolders])

        m = bar.addMenu("&Help")
        m.addAction("Writing Scripts…", self.open_script_guide)
        m.addAction(f"About {APP_NAME}", self.about)

        tb = QToolBar("Main", self)
        tb.setObjectName("mainToolbar")
        tb.setMovable(False)
        tb.setIconSize(QSize(18, 18))
        tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        tb.addActions([self.act_add_files, self.act_add_folder, self.act_remove, self.act_clear])
        tb.addSeparator()
        tb.addAction(self.act_undo)
        tb.addSeparator()
        tb.addActions([self.act_reload, self.act_new_script, self.act_open_scripts])
        self.addToolBar(tb)

    def _build_ui(self) -> None:
        # Left: script picker + options
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(10, 10, 6, 10)
        self.search = QLineEdit(placeholderText="Filter scripts…", clearButtonEnabled=True)
        self.search.textChanged.connect(self._filter_scripts)
        self.script_list = QListWidget()
        self.script_list.setUniformItemSizes(True)
        self.script_list.currentItemChanged.connect(self._on_script_changed)
        left_layout.addWidget(self.search)
        left_layout.addWidget(self.script_list, 1)

        self.options_box = QGroupBox("Options")
        box_layout = QVBoxLayout(self.options_box)
        self.description = QLabel(wordWrap=True, textInteractionFlags=Qt.TextInteractionFlag.TextSelectableByMouse)
        self.description.setObjectName("description")
        self.script_error = QLabel(wordWrap=True, textInteractionFlags=Qt.TextInteractionFlag.TextSelectableByMouse)
        self.script_error.setObjectName("banner")
        self.script_error.hide()
        self.param_form = ParamForm()
        self.param_form.changed.connect(self._on_params_changed)
        self.reset_params_btn = QPushButton("Reset Options")
        self.reset_params_btn.clicked.connect(self.reset_params)
        box_layout.addWidget(self.description)
        box_layout.addWidget(self.script_error)
        box_layout.addWidget(self.param_form)
        box_layout.addWidget(self.reset_params_btn, 0, Qt.AlignmentFlag.AlignRight)
        scroll = QScrollArea(widgetResizable=True, frameShape=QFrame.Shape.NoFrame)
        scroll.setWidget(self.options_box)
        left_layout.addWidget(scroll, 1)

        # Right: file table
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(6, 10, 10, 10)
        self.preview_error = QLabel(wordWrap=True, textInteractionFlags=Qt.TextInteractionFlag.TextSelectableByMouse)
        self.preview_error.setObjectName("banner")
        self.preview_error.hide()

        self.model = FileTableModel(self)
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setWordWrap(False)
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(26)
        header = self.table.horizontalHeader()
        header.setHighlightSections(False)
        header.setSectionResizeMode(COL_STATUS, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(COL_STATUS, 28)
        header.setSectionResizeMode(COL_OLD, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(COL_NEW, QHeaderView.ResizeMode.Interactive)
        header.resizeSection(COL_OLD, 280)
        header.resizeSection(COL_NEW, 280)
        header.setStretchLastSection(True)
        header.setSortIndicatorShown(False)
        header.sectionClicked.connect(self._sort_by)
        self._sort_order = Qt.SortOrder.DescendingOrder

        self.drop_hint = QLabel("Drop files or folders here\n\nor use Add Files / Add Folder", alignment=Qt.AlignmentFlag.AlignCenter)
        self.drop_hint.setObjectName("dropHint")
        self.stack = QStackedWidget()
        self.stack.addWidget(self.drop_hint)
        self.stack.addWidget(self.table)

        bottom = QHBoxLayout()
        self.summary = QLabel()
        self.preview_btn = QPushButton("Preview  (F5)")
        self.preview_btn.clicked.connect(self.run_preview)
        self.rename_btn = QPushButton("Rename  (F2)")
        self.rename_btn.setObjectName("primary")
        bold = self.rename_btn.font()
        bold.setBold(True)
        self.rename_btn.setFont(bold)
        self.rename_btn.setMinimumWidth(170)
        self.rename_btn.clicked.connect(self.rename_files)
        bottom.addWidget(self.summary, 1)
        bottom.addWidget(self.preview_btn)
        bottom.addWidget(self.rename_btn)

        right_layout.addWidget(self.preview_error)
        right_layout.addWidget(self.stack, 1)
        right_layout.addLayout(bottom)

        self.splitter = QSplitter()
        self.splitter.addWidget(left)
        self.splitter.addWidget(right)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([300, 800])
        self.setCentralWidget(self.splitter)
        self._apply_style()

    def _apply_style(self) -> None:
        dark = QApplication.palette().color(QPalette.ColorRole.Window).lightness() < 128
        banner_bg, banner_fg = ("#4a1c1c", "#ffd7d5") if dark else ("#fdecea", "#6b1a14")
        hint = QApplication.palette().color(QPalette.ColorRole.PlaceholderText).name()
        self.setStyleSheet(f"""
            QPushButton {{ padding: 6px 14px; }}
            QPushButton#primary {{
                background: palette(highlight); color: palette(highlighted-text);
                border: none; border-radius: 5px; padding: 7px 20px;
            }}
            QPushButton#primary:disabled {{ background: palette(mid); color: palette(window); }}
            QLabel#banner {{ background: {banner_bg}; color: {banner_fg}; border-radius: 5px; padding: 8px; }}
            QLabel#dropHint {{ border: 2px dashed {hint}; border-radius: 12px; color: {hint}; font-size: 15px; }}
            QLabel#description {{ color: {hint}; }}
            QListWidget::item {{ padding: 3px 4px; }}
        """)

    # ------------------------------------------------------------- scripts
    def reload_scripts(self, initial: bool = False) -> None:
        previous = self.current.key if self.current else None
        if initial and self.settings["remember_last_script"]:
            previous = self.settings["last_script"] or None
        values = self.param_form.values() if self.current else None

        self.scripts = load_scripts(self.scripts_dir)
        self._watch_scripts()

        self.script_list.blockSignals(True)
        self.script_list.clear()
        for s in self.scripts:
            item = QListWidgetItem(s.name)
            item.setData(Qt.ItemDataRole.UserRole, s.key)
            if not s.ok:
                item.setIcon(self._icon(QStyle.StandardPixmap.SP_MessageBoxWarning))
                item.setToolTip(s.error)
            else:
                item.setToolTip(s.description)
            self.script_list.addItem(item)
        self.script_list.blockSignals(False)
        self._filter_scripts(self.search.text())

        target = next((i for i in range(self.script_list.count()) if self.script_list.item(i).data(Qt.ItemDataRole.UserRole) == previous), None)
        if target is not None:
            if not initial and values is not None and self.current and self.current.key == previous:
                self._pending_values = values
            self.script_list.setCurrentRow(target)  # emits currentItemChanged
        else:
            self.current = None
            self._show_script(None)
        if not initial:
            loaded = sum(s.ok for s in self.scripts)
            self.statusBar().showMessage(f"Loaded {loaded} script(s) from {self.scripts_dir}", 4000)

    def _watch_scripts(self) -> None:
        if self.watcher.files():
            self.watcher.removePaths(self.watcher.files())
        if self.watcher.directories():
            self.watcher.removePaths(self.watcher.directories())
        if self.scripts_dir.is_dir():
            self.watcher.addPath(str(self.scripts_dir))
            files = [str(p) for p in self.scripts_dir.glob("*.py")]
            if files:
                self.watcher.addPaths(files)

    def _filter_scripts(self, text: str) -> None:
        needle = text.strip().lower()
        for i in range(self.script_list.count()):
            item = self.script_list.item(i)
            script = self._script_for(item)
            haystack = f"{item.text()} {script.description if script else ''}".lower()
            item.setHidden(bool(needle) and needle not in haystack)

    def _script_for(self, item: QListWidgetItem | None) -> RenameScript | None:
        if item is None:
            return None
        key = item.data(Qt.ItemDataRole.UserRole)
        return next((s for s in self.scripts if s.key == key), None)

    def _on_script_changed(self, item: QListWidgetItem | None, _previous: QListWidgetItem | None) -> None:
        self._save_params()
        self.current = self._script_for(item)
        self._show_script(self.current)
        if self.current:
            self.settings["last_script"] = self.current.key
        self.request_preview()

    def _show_script(self, script: RenameScript | None) -> None:
        self.options_box.setTitle(script.name if script else "Options")
        self.description.setText(script.description if script else "Select a script on the left.")
        self.description.setVisible(bool(script is None or script.description))
        if script and script.error:
            self.script_error.setText(f"This script cannot be used:\n{script.error.strip()}")
            self.script_error.show()
        else:
            self.script_error.hide()
        values: dict[str, Any] = {}
        if script:
            pending, self._pending_values = self._pending_values, None
            saved = self.settings["params"].get(script.key, {}) if self.settings["remember_params"] else {}
            values = script.resolve_values(pending if pending is not None else saved)
        self.param_form.setVisible(bool(script and script.ok))
        self.param_form.blockSignals(True)
        self.param_form.set_params(script.params if script and script.ok else [], values)
        self.param_form.blockSignals(False)
        self.reset_params_btn.setVisible(bool(script and script.ok and script.params))

    def _save_params(self) -> None:
        if self.current and self.current.ok and self.current.params:
            self.settings["params"][self.current.key] = self.param_form.values()

    def _on_params_changed(self) -> None:
        self._save_params()
        self.request_preview()

    def reset_params(self) -> None:
        if self.current:
            self.settings["params"].pop(self.current.key, None)
            self._show_script(self.current)
            self.request_preview()

    # --------------------------------------------------------------- files
    def add_paths(self, items: list[str]) -> None:
        new = expand_paths(items, include_subfolders=bool(self.settings["include_subfolders"]))
        files, added = merge_unique(self.model.files, new)
        if added:
            self.model.set_files(files)
            self.statusBar().showMessage(f"Added {added} file(s)", 3000)
            self.request_preview()
        elif items:
            self.statusBar().showMessage("No new files to add", 3000)
        self._update_ui()

    def add_files_dialog(self) -> None:
        names, _ = QFileDialog.getOpenFileNames(self, "Add Files")
        self.add_paths(names)

    def add_folder_dialog(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Add Folder")
        if folder:
            self.add_paths([folder])

    def remove_selected(self) -> None:
        rows = {i.row() for i in self.table.selectionModel().selectedRows()}
        if not rows:
            return
        self.model.set_files([f for n, f in enumerate(self.model.files) if n not in rows])
        self.request_preview()

    def clear_files(self) -> None:
        self.model.set_files([])
        self.plan_current = False
        self.preview_error.hide()
        self._update_ui()

    def _sort_by(self, column: int) -> None:
        if column == COL_STATUS or not self.model.files:
            return
        self._sort_order = Qt.SortOrder.DescendingOrder if self._sort_order == Qt.SortOrder.AscendingOrder else Qt.SortOrder.AscendingOrder
        self.model.sort(COL_FOLDER if column == COL_FOLDER else COL_OLD, self._sort_order)
        self.plan_current = False
        self.request_preview()

    def dragEnterEvent(self, event) -> None:  # noqa: N802 - Qt override
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragMoveEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:  # noqa: N802
        local = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
        if local:
            event.acceptProposedAction()
            self.add_paths(local)

    # ------------------------------------------------------------- preview
    def request_preview(self) -> None:
        self.plan_current = False
        live = self.settings["live_preview"] and not (self.current and self.current.uses_tkinter)
        if live:
            self.preview_timer.start()
        else:
            self.model.set_plan(None)
        self._update_ui()

    def run_preview(self) -> None:
        self.preview_timer.stop()
        script, files = self.current, self.model.files
        self.preview_error.hide()
        if not script or not script.ok or not files:
            self.model.set_plan(None)
            self.plan_current = False
            self._update_ui()
            return
        try:
            names = script.run(files, self.param_form.values())
        except ScriptError as exc:
            self.model.set_plan(None)
            self.plan_current = False
            self.preview_error.setText(str(exc).strip())
            self.preview_error.show()
            self._update_ui()
            return
        self.model.set_plan(build_plan(files, names))
        self.plan_current = True
        self._update_ui()

    # -------------------------------------------------------------- rename
    def rename_files(self) -> None:
        if not self.current or not self.model.files:
            return
        if not self.plan_current or self.model.plan is None:
            self.run_preview()  # F2 on a stale preview refreshes it first
            return
        plan = self.model.plan
        changes = plan.changes
        if not changes:
            self.statusBar().showMessage("Nothing to rename", 3000)
            return
        if self.settings["confirm_rename"]:
            box = QMessageBox(QMessageBox.Icon.Question, "Confirm Rename", f"Rename {len(changes)} file(s)?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel, self)
            if plan.errors:
                box.setInformativeText(f"{len(plan.errors)} file(s) with problems will be skipped.")
            box.setDetailedText("\n".join(f"{i.src.name}  →  {i.new_name}" for i in changes))
            box.setDefaultButton(QMessageBox.StandardButton.Yes)
            if box.exec() != QMessageBox.StandardButton.Yes:
                return
        try:
            done = self.history.apply(ops_from_plan(plan))
        except RenameError as exc:
            QMessageBox.critical(self, "Rename Failed", str(exc))
            self.run_preview()
            return
        self._replace_paths({op.src: op.dst for op in done})
        skipped = f", {len(plan.errors)} skipped" if plan.errors else ""
        self.statusBar().showMessage(f"Renamed {len(done)} file(s){skipped}. Press Ctrl+Z to undo.", 8000)
        self.settings.save()

    def undo(self) -> None:
        if not len(self.history):
            self.statusBar().showMessage("Nothing to undo", 3000)
            return
        try:
            reverse = self.history.undo()
        except RenameError as exc:
            QMessageBox.critical(self, "Undo Failed", str(exc))
            return
        self._replace_paths({op.src: op.dst for op in reverse})
        self.statusBar().showMessage(f"Undid rename of {len(reverse)} file(s)", 5000)

    def _replace_paths(self, mapping: dict[Path, Path]) -> None:
        self.model.set_files([mapping.get(f, f) for f in self.model.files])
        # Don't auto-preview again right away: showing the next rename of the
        # files just renamed (e.g. Inverter flipping back) is confusing.
        self.plan_current = False
        self._update_ui()

    # ---------------------------------------------------------------- misc
    def _update_ui(self) -> None:
        files = self.model.files
        self.stack.setCurrentWidget(self.table if files else self.drop_hint)
        plan = self.model.plan if self.plan_current else None
        ready = bool(self.current and self.current.ok and files)
        self.act_preview.setEnabled(ready)
        self.preview_btn.setEnabled(ready)
        count = len(plan.changes) if plan else 0
        self.rename_btn.setEnabled(ready and (plan is None or count > 0))
        self.rename_btn.setText(f"Rename {count} File{'s' if count != 1 else ''}  (F2)" if plan else "Rename  (F2)")
        self.act_remove.setEnabled(bool(files))
        self.act_clear.setEnabled(bool(files))
        self.act_undo.setEnabled(len(self.history) > 0)
        self.act_edit_script.setEnabled(self.current is not None)
        if not files:
            self.summary.setText("")
        elif plan:
            self.summary.setText(plan.summary())
        else:
            self.summary.setText(f"{len(files)} file(s)" + ("" if self.current else " - select a script"))

    def open_scripts_folder(self) -> None:
        self.scripts_dir.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.scripts_dir)))

    def _open_in_editor(self, path: Path) -> None:
        if sys.platform == "win32":
            try:
                os.startfile(str(path), "edit")  # type: ignore[attr-defined]  # "open" would run the .py
                return
            except OSError:
                pass
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.parent)))
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def edit_script(self) -> None:
        if self.current:
            self._open_in_editor(self.current.path)

    def new_script(self) -> None:
        name, ok = QInputDialog.getText(self, "New Script", "Script name:")
        name = re.sub(r'[<>:"/\\|?*]', "", name).strip()
        if not ok or not name:
            return
        target = self.scripts_dir / f"{name}.py"
        if target.exists():
            QMessageBox.warning(self, "New Script", f"'{target.name}' already exists.")
            return
        template = self.scripts_dir / "_Template.py"
        text = template.read_text(encoding="utf-8") if template.exists() else 'import os\n\n\ndef rename(files):\n    return [os.path.basename(f) for f in files]\n'
        text = re.sub(r'^NAME = ".*"$', f"NAME = {name!r}".replace("'", '"'), text, count=1, flags=re.MULTILINE)
        self.scripts_dir.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        self.reload_scripts()
        for i in range(self.script_list.count()):
            if self.script_list.item(i).data(Qt.ItemDataRole.UserRole) == target.stem:
                self.script_list.setCurrentRow(i)
        self._open_in_editor(target)

    def open_script_guide(self) -> None:
        guide = paths.app_dir() / "AGENTS.md"
        if guide.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(guide)))
        else:
            QDesktopServices.openUrl(QUrl(f"{REPO_URL}/blob/main/AGENTS.md"))

    def about(self) -> None:
        QMessageBox.about(
            self,
            f"About {APP_NAME}",
            f"<h3>{APP_NAME} {__version__}</h3>"
            "<p>Batch rename files with small Python scripts.</p>"
            f"<p>Scripts folder:<br><code>{self.scripts_dir}</code></p>"
            f'<p><a href="{REPO_URL}">{REPO_URL}</a></p>',
        )

    def _restore_window_state(self) -> None:
        if self.settings["geometry"]:
            self.restoreGeometry(QByteArray.fromBase64(self.settings["geometry"].encode()))
        if self.settings["splitter"]:
            self.splitter.restoreState(QByteArray.fromBase64(self.settings["splitter"].encode()))

    def closeEvent(self, event) -> None:  # noqa: N802
        self._save_params()
        self.settings["geometry"] = bytes(self.saveGeometry().toBase64()).decode()
        self.settings["splitter"] = bytes(self.splitter.saveState().toBase64()).decode()
        if self.current:
            self.settings["last_script"] = self.current.key
        self.settings.save()
        super().closeEvent(event)
