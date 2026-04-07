"""Search bar widget for global and column search."""

from PySide6.QtWidgets import (QWidget, QHBoxLayout, QLineEdit, QPushButton,
                                QComboBox, QCheckBox, QLabel)
from PySide6.QtCore import Signal


class SearchBar(QWidget):
    """Search bar with next/previous navigation."""

    search_requested = Signal(str, str, bool)  # query, column, case_sensitive
    next_match = Signal()
    prev_match = Signal()
    search_closed = Signal()

    def __init__(self, columns: list[str] = None, parent=None):
        super().__init__(parent)
        self._setup_ui(columns or [])

    def _setup_ui(self, columns):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 2, 5, 2)

        layout.addWidget(QLabel("Search:"))

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Type to search...")
        self._search_input.returnPressed.connect(self._do_search)
        layout.addWidget(self._search_input, stretch=1)

        self._column_combo = QComboBox()
        self._column_combo.addItem("All Columns", "")
        for col in columns:
            self._column_combo.addItem(col, col)
        self._column_combo.setMinimumWidth(150)
        layout.addWidget(self._column_combo)

        self._case_check = QCheckBox("Case sensitive")
        layout.addWidget(self._case_check)

        self._search_btn = QPushButton("Search")
        self._search_btn.clicked.connect(self._do_search)
        layout.addWidget(self._search_btn)

        self._prev_btn = QPushButton("◀ Prev")
        self._prev_btn.clicked.connect(self.prev_match)
        layout.addWidget(self._prev_btn)

        self._next_btn = QPushButton("Next ▶")
        self._next_btn.clicked.connect(self.next_match)
        layout.addWidget(self._next_btn)

        self._result_label = QLabel("")
        layout.addWidget(self._result_label)

        self._close_btn = QPushButton("✕")
        self._close_btn.setMaximumWidth(30)
        self._close_btn.clicked.connect(self._close)
        layout.addWidget(self._close_btn)

    def _do_search(self):
        query = self._search_input.text().strip()
        if query:
            column = self._column_combo.currentData() or ""
            case = self._case_check.isChecked()
            self.search_requested.emit(query, column, case)

    def _close(self):
        self.hide()
        self.search_closed.emit()

    def update_columns(self, columns: list[str]):
        self._column_combo.clear()
        self._column_combo.addItem("All Columns", "")
        for col in columns:
            self._column_combo.addItem(col, col)

    def set_result_count(self, count: int, current: int = 0):
        if count == 0:
            self._result_label.setText("No matches")
        else:
            self._result_label.setText(f"{current}/{count} matches")

    def focus_search(self):
        self._search_input.setFocus()
        self._search_input.selectAll()
