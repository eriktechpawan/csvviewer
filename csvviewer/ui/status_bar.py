"""Status bar showing row counts and file info."""

from PySide6.QtWidgets import QStatusBar, QLabel, QWidget, QHBoxLayout
from PySide6.QtCore import Qt


class CSVStatusBar(QStatusBar):
    """Status bar displaying data summary information.

    Shows: total rows, filtered rows, selected rows, visible columns, file size
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self._total_label = QLabel("Rows: 0")
        self._filtered_label = QLabel("Filtered: 0")
        self._selected_label = QLabel("Selected: 0")
        self._columns_label = QLabel("Columns: 0")
        self._file_label = QLabel("")
        self._status_label = QLabel("Ready")

        for label in [self._total_label, self._filtered_label,
                      self._selected_label, self._columns_label,
                      self._file_label]:
            self.addPermanentWidget(label)

        self.addWidget(self._status_label)

    def update_counts(self, total: int = 0, filtered: int = 0,
                      selected: int = 0, columns: int = 0,
                      file_size: str = ""):
        self._total_label.setText(f"Total: {total:,}")
        self._filtered_label.setText(f"Filtered: {filtered:,}")
        self._selected_label.setText(f"Selected: {selected:,}")
        self._columns_label.setText(f"Columns: {columns}")
        if file_size:
            self._file_label.setText(f"Size: {file_size}")

    def set_status(self, text: str):
        self._status_label.setText(text)

    def set_file_info(self, name: str, size_str: str):
        self._file_label.setText(f"{name} ({size_str})")
