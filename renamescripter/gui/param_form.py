"""Builds input widgets from a script's PARAMS declaration."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QWidget,
)

from ..scripts import Param

_INT_LIMIT = 2_000_000_000


class ParamForm(QWidget):
    """A form with one editor per parameter. Emits ``changed`` on every edit."""

    changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._layout = QFormLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self._params: list[Param] = []
        self._editors: dict[str, QWidget] = {}

    def set_params(self, params: list[Param], values: dict[str, Any]) -> None:
        while self._layout.rowCount():
            self._layout.removeRow(0)
        self._params = list(params)
        self._editors = {}
        for p in self._params:
            editor = self._make_editor(p, values.get(p.key, p.default))
            tip = p.help or ""
            editor.setToolTip(tip)
            self._editors[p.key] = editor
            if p.type == "bool":
                self._layout.addRow(editor)
            else:
                label = QLabel(p.label)
                label.setToolTip(tip)
                self._layout.addRow(label, editor)
        if not self._params:
            note = QLabel("This script has no options.")
            note.setEnabled(False)
            self._layout.addRow(note)

    def _make_editor(self, p: Param, value: Any) -> QWidget:
        if p.type == "bool":
            w = QCheckBox(p.label)
            w.setChecked(bool(value))
            w.toggled.connect(self.changed)
        elif p.type == "int":
            w = QSpinBox()
            w.setRange(int(p.min) if p.min is not None else -_INT_LIMIT, int(p.max) if p.max is not None else _INT_LIMIT)
            w.setSingleStep(int(p.step or 1))
            w.setValue(int(value))
            w.valueChanged.connect(self.changed)
        elif p.type == "float":
            w = QDoubleSpinBox()
            w.setDecimals(4)
            w.setRange(p.min if p.min is not None else -1e12, p.max if p.max is not None else 1e12)
            w.setSingleStep(p.step or 0.1)
            w.setValue(float(value))
            w.valueChanged.connect(self.changed)
        elif p.type == "choice":
            w = QComboBox()
            w.addItems(p.choices)
            w.setCurrentText(str(value))
            w.currentTextChanged.connect(self.changed)
        else:
            w = QLineEdit(str(value))
            w.setPlaceholderText(p.placeholder)
            w.setClearButtonEnabled(True)
            w.textChanged.connect(self.changed)
        return w

    def values(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for p in self._params:
            w = self._editors[p.key]
            if isinstance(w, QCheckBox):
                result[p.key] = w.isChecked()
            elif isinstance(w, (QSpinBox, QDoubleSpinBox)):
                result[p.key] = w.value()
            elif isinstance(w, QComboBox):
                result[p.key] = w.currentText()
            elif isinstance(w, QLineEdit):
                result[p.key] = w.text()
        return result

    def focus_first(self) -> None:
        for w in self._editors.values():
            if isinstance(w, QLineEdit):
                w.setFocus()
                w.selectAll()
                return
