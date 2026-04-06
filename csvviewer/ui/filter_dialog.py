"""Filter dialog for CSV data filtering.

Supports value, numeric, and text filters with AND/OR combinations.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout,
    QComboBox, QLineEdit, QPushButton, QLabel, QCheckBox,
    QGroupBox, QScrollArea, QWidget, QRadioButton, QButtonGroup,
)
from PySide6.QtCore import Signal
from csvviewer.utils.constants import ColumnType


class FilterRow(QWidget):
    """A single filter condition row."""

    removed = Signal(object)  # self

    def __init__(self, columns: list[str], column_types: dict, parent=None):
        super().__init__(parent)
        self._columns = columns
        self._column_types = column_types
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)

        # Column selector
        self._col_combo = QComboBox()
        self._col_combo.addItems(self._columns)
        self._col_combo.currentTextChanged.connect(self._on_column_changed)
        self._col_combo.setMinimumWidth(120)
        layout.addWidget(self._col_combo)

        # Operator selector
        self._op_combo = QComboBox()
        self._op_combo.setMinimumWidth(140)
        self._op_combo.currentTextChanged.connect(self._on_op_changed)
        layout.addWidget(self._op_combo)

        # Value input 1
        self._value1 = QLineEdit()
        self._value1.setPlaceholderText("Value")
        self._value1.setMinimumWidth(100)
        layout.addWidget(self._value1)

        # Value input 2 (for BETWEEN etc.)
        self._value2 = QLineEdit()
        self._value2.setPlaceholderText("Value 2")
        self._value2.setMinimumWidth(100)
        self._value2.hide()
        layout.addWidget(self._value2)

        # Case sensitive checkbox (for text filters)
        self._case_check = QCheckBox("Case")
        self._case_check.setChecked(True)
        self._case_check.hide()
        layout.addWidget(self._case_check)

        # Remove button
        self._remove_btn = QPushButton("✕")
        self._remove_btn.setMaximumWidth(30)
        self._remove_btn.clicked.connect(lambda: self.removed.emit(self))
        layout.addWidget(self._remove_btn)

        # Initialize operators
        self._on_column_changed(self._col_combo.currentText())

    def _on_column_changed(self, col_name: str):
        """Update operators based on column type."""
        col_type = self._column_types.get(col_name, ColumnType.TEXT)
        self._op_combo.clear()

        # Always show value filters
        value_ops = [
            ("Equals", "EQUALS"), ("Not Equals", "NOT_EQUALS"),
            ("Is Empty", "IS_EMPTY"), ("Not Empty", "NOT_EMPTY"),
            ("Is Null", "IS_NULL"), ("Not Null", "NOT_NULL"),
        ]

        for label, op in value_ops:
            self._op_combo.addItem(label, op)

        # Numeric filters for numeric types
        if col_type in (ColumnType.INTEGER, ColumnType.FLOAT):
            numeric_ops = [
                ("Greater Than", "GT"), ("Greater or Equal", "GTE"),
                ("Less Than", "LT"), ("Less or Equal", "LTE"),
                ("Between", "BETWEEN"), ("Outside Range", "OUTSIDE_RANGE"),
                ("Is Zero", "IS_ZERO"), ("Non-Zero", "NON_ZERO"),
                ("Positive", "POSITIVE"), ("Negative", "NEGATIVE"),
            ]
            for label, op in numeric_ops:
                self._op_combo.addItem(label, op)

        # Text filters
        text_ops = [
            ("Contains", "CONTAINS"), ("Not Contains", "NOT_CONTAINS"),
            ("Starts With", "STARTS_WITH"), ("Ends With", "ENDS_WITH"),
            ("Exact Match", "EXACT_MATCH"), ("Regex", "REGEX"),
        ]
        for label, op in text_ops:
            self._op_combo.addItem(label, op)

    def _on_op_changed(self, op_text: str):
        """Show/hide value inputs based on operator."""
        op = self._op_combo.currentData()

        # Operators that need no value
        no_value_ops = {'IS_EMPTY', 'NOT_EMPTY', 'IS_NULL', 'NOT_NULL',
                        'IS_ZERO', 'NON_ZERO', 'POSITIVE', 'NEGATIVE'}
        # Operators that need two values
        two_value_ops = {'BETWEEN', 'OUTSIDE_RANGE'}
        # Text operators (show case checkbox)
        text_ops = {'CONTAINS', 'NOT_CONTAINS', 'STARTS_WITH', 'ENDS_WITH',
                    'EXACT_MATCH', 'REGEX'}

        if op in no_value_ops:
            self._value1.hide()
            self._value2.hide()
        elif op in two_value_ops:
            self._value1.show()
            self._value2.show()
            self._value1.setPlaceholderText("Min")
            self._value2.setPlaceholderText("Max")
        else:
            self._value1.show()
            self._value2.hide()
            self._value1.setPlaceholderText("Value")

        self._case_check.setVisible(op in text_ops)

    def get_filter(self) -> dict:
        """Get filter specification as dict."""
        op = self._op_combo.currentData()
        value = self._value1.text().strip()
        value2 = self._value2.text().strip()

        # Try to convert to number for numeric ops
        numeric_ops = {'GT', 'GTE', 'LT', 'LTE', 'BETWEEN', 'OUTSIDE_RANGE',
                       'EQUALS', 'NOT_EQUALS'}
        col_type = self._column_types.get(
            self._col_combo.currentText(), ColumnType.TEXT
        )

        if op in numeric_ops and col_type in (ColumnType.INTEGER, ColumnType.FLOAT):
            try:
                value = float(value) if value else None
                if value2:
                    value2 = float(value2)
            except ValueError:
                pass

        return {
            'column': self._col_combo.currentText(),
            'operator': op,
            'value': value if value else None,
            'value2': value2 if value2 else None,
            'case_sensitive': self._case_check.isChecked(),
        }

    def set_filter(self, f: dict):
        """Set filter from dict."""
        idx = self._col_combo.findText(f.get('column', ''))
        if idx >= 0:
            self._col_combo.setCurrentIndex(idx)

        op = f.get('operator', 'EQUALS')
        for i in range(self._op_combo.count()):
            if self._op_combo.itemData(i) == op:
                self._op_combo.setCurrentIndex(i)
                break

        if f.get('value') is not None:
            self._value1.setText(str(f['value']))
        if f.get('value2') is not None:
            self._value2.setText(str(f['value2']))

        self._case_check.setChecked(f.get('case_sensitive', True))


class FilterDialog(QDialog):
    """Main filter dialog with multiple conditions."""

    filters_applied = Signal(list, str)  # (list of filter dicts, logic: "AND"/"OR")

    def __init__(self, columns: list[str], column_types: dict,
                 current_filters: list = None, parent=None):
        super().__init__(parent)
        self._columns = columns
        self._column_types = column_types
        self._filter_rows: list[FilterRow] = []
        self.setWindowTitle("Filter Data")
        self.setMinimumSize(700, 400)
        self._setup_ui()

        # Restore current filters
        if current_filters:
            for f in current_filters:
                self._add_filter_row(f)
        else:
            self._add_filter_row()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Logic selector (AND/OR)
        logic_layout = QHBoxLayout()
        logic_layout.addWidget(QLabel("Combine filters with:"))
        self._and_radio = QRadioButton("AND")
        self._and_radio.setChecked(True)
        self._or_radio = QRadioButton("OR")
        logic_group = QButtonGroup(self)
        logic_group.addButton(self._and_radio)
        logic_group.addButton(self._or_radio)
        logic_layout.addWidget(self._and_radio)
        logic_layout.addWidget(self._or_radio)
        logic_layout.addStretch()
        layout.addLayout(logic_layout)

        # Scrollable filter rows
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self._filters_widget = QWidget()
        self._filters_layout = QVBoxLayout(self._filters_widget)
        self._filters_layout.setContentsMargins(0, 0, 0, 0)
        self._filters_layout.addStretch()
        scroll.setWidget(self._filters_widget)
        layout.addWidget(scroll, stretch=1)

        # Add filter button
        add_btn = QPushButton("+ Add Filter")
        add_btn.clicked.connect(lambda: self._add_filter_row())
        layout.addWidget(add_btn)

        # Buttons
        btn_layout = QHBoxLayout()

        clear_btn = QPushButton("Clear All")
        clear_btn.clicked.connect(self._clear_all)
        btn_layout.addWidget(clear_btn)

        btn_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        apply_btn = QPushButton("Apply")
        apply_btn.setDefault(True)
        apply_btn.clicked.connect(self._apply)
        btn_layout.addWidget(apply_btn)

        layout.addLayout(btn_layout)

    def _add_filter_row(self, filter_data: dict = None):
        row = FilterRow(self._columns, self._column_types, self)
        row.removed.connect(self._remove_filter_row)
        if filter_data:
            row.set_filter(filter_data)

        # Insert before the stretch
        self._filters_layout.insertWidget(
            self._filters_layout.count() - 1, row
        )
        self._filter_rows.append(row)

    def _remove_filter_row(self, row: FilterRow):
        self._filter_rows.remove(row)
        self._filters_layout.removeWidget(row)
        row.deleteLater()

    def _clear_all(self):
        for row in list(self._filter_rows):
            self._remove_filter_row(row)
        self._add_filter_row()

    def _apply(self):
        filters = [row.get_filter() for row in self._filter_rows]
        # Remove filters with no meaningful operator
        filters = [f for f in filters if f.get('operator')]
        logic = self.get_logic()
        self.filters_applied.emit(filters, logic)
        self.accept()

    def get_filters(self) -> list[dict]:
        """Return current filter specifications."""
        return [row.get_filter() for row in self._filter_rows]

    def get_logic(self) -> str:
        """Return the current filter combination logic ('AND' or 'OR')."""
        return "AND" if self._and_radio.isChecked() else "OR"
