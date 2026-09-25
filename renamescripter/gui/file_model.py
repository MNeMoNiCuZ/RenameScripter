"""Table model showing each file with its proposed new name."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QPersistentModelIndex, Qt
from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication

from ..files import natural_key
from ..plan import Plan, PlanItem, Status

COL_STATUS, COL_OLD, COL_NEW, COL_FOLDER = range(4)
HEADERS = ("", "Current name", "New name", "Folder")
_STATUS_GLYPH = {Status.OK: "●", Status.ERROR: "✖", Status.UNCHANGED: ""}


def _is_dark() -> bool:
    return QApplication.palette().color(QPalette.ColorRole.Window).lightness() < 128


class FileTableModel(QAbstractTableModel):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.files: list[Path] = []
        self.plan: Plan | None = None

    # --- data management -------------------------------------------------
    def set_files(self, files: list[Path]) -> None:
        self.beginResetModel()
        self.files = list(files)
        self.plan = None
        self.endResetModel()

    def set_plan(self, plan: Plan | None) -> None:
        if plan is not None and [i.src for i in plan.items] != self.files:
            plan = None  # stale plan for a different file list
        self.plan = plan
        if self.files:
            self.dataChanged.emit(self.index(0, 0), self.index(len(self.files) - 1, len(HEADERS) - 1))

    def item(self, row: int) -> PlanItem | None:
        if self.plan and 0 <= row < len(self.plan.items):
            return self.plan.items[row]
        return None

    # --- Qt model API ----------------------------------------------------
    def rowCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.files)

    def columnCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(HEADERS)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return HEADERS[section]
        return None

    def data(self, index: QModelIndex | QPersistentModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        row, col = index.row(), index.column()
        path = self.files[row]
        item = self.item(row)
        status = item.status if item else Status.UNCHANGED

        if role == Qt.ItemDataRole.DisplayRole:
            if col == COL_STATUS:
                return _STATUS_GLYPH[status]
            if col == COL_OLD:
                return path.name
            if col == COL_NEW:
                return (item.new_name or "") if item else ""
            if col == COL_FOLDER:
                return str(path.parent)
        elif role == Qt.ItemDataRole.ToolTipRole:
            if item and item.message:
                return item.message
            if col == COL_FOLDER or col == COL_OLD:
                return str(path)
        elif role == Qt.ItemDataRole.ForegroundRole:
            dark = _is_dark()
            if status is Status.ERROR and col in (COL_STATUS, COL_NEW):
                return QColor("#ff7b72" if dark else "#c62828")
            if status is Status.OK and col in (COL_STATUS, COL_NEW):
                return QColor("#7ee787" if dark else "#1b7f3b")
            if col == COL_FOLDER:
                return QApplication.palette().color(QPalette.ColorRole.PlaceholderText)
        elif role == Qt.ItemDataRole.FontRole and col == COL_NEW and status is Status.OK:
            font = QFont()
            font.setBold(True)
            return font
        elif role == Qt.ItemDataRole.TextAlignmentRole and col == COL_STATUS:
            return Qt.AlignmentFlag.AlignCenter
        return None

    def sort(self, column: int, order: Qt.SortOrder = Qt.SortOrder.AscendingOrder) -> None:
        """Sorting reorders the underlying list (order matters to e.g. numbering scripts)."""
        if column == COL_FOLDER:
            key = lambda p: (natural_key(str(p.parent)), natural_key(p.name))  # noqa: E731
        else:
            key = lambda p: natural_key(p.name)  # noqa: E731
        self.layoutAboutToBeChanged.emit()
        self.files.sort(key=key, reverse=order == Qt.SortOrder.DescendingOrder)
        self.plan = None
        self.layoutChanged.emit()
