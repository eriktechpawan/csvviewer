"""Column statistics dialog.

Shows detailed statistics for a column including type, counts,
min/max, sum, average, and top values.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QPushButton, QGroupBox, QTableWidget,
    QTableWidgetItem, QHeaderView
)
from PySide6.QtCore import Qt


class ColumnStatsDialog(QDialog):
    """Dialog displaying statistics for a specific column."""

    def __init__(self, stats: dict, parent=None):
        super().__init__(parent)
        self._stats = stats
        self.setWindowTitle(f"Statistics: {stats.get('column_name', '')}")
        self.setMinimumSize(400, 500)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Basic info
        info_group = QGroupBox("Column Info")
        info_layout = QFormLayout()

        info_layout.addRow("Name:", QLabel(str(self._stats.get('column_name', ''))))
        info_layout.addRow("Type:", QLabel(str(self._stats.get('detected_type', ''))))
        info_layout.addRow("Total Rows:", QLabel(f"{self._stats.get('total_rows', 0):,}"))
        info_layout.addRow("Non-Null:", QLabel(f"{self._stats.get('non_null_count', 0):,}"))
        info_layout.addRow("Null:", QLabel(f"{self._stats.get('null_count', 0):,}"))
        info_layout.addRow("Unique:", QLabel(f"{self._stats.get('unique_count', 0):,}"))

        info_group.setLayout(info_layout)
        layout.addWidget(info_group)

        # Numeric stats (if available)
        if 'sum' in self._stats or 'average' in self._stats:
            num_group = QGroupBox("Numeric Statistics")
            num_layout = QFormLayout()

            if 'min' in self._stats:
                num_layout.addRow("Min:", QLabel(str(self._stats['min'])))
            if 'max' in self._stats:
                num_layout.addRow("Max:", QLabel(str(self._stats['max'])))
            if 'sum' in self._stats:
                sum_val = self._stats['sum']
                num_layout.addRow("Sum:", QLabel(
                    f"{sum_val:,.2f}" if isinstance(sum_val, float) else str(sum_val)
                ))
            if 'average' in self._stats:
                avg_val = self._stats['average']
                num_layout.addRow("Average:", QLabel(
                    f"{avg_val:,.4f}" if isinstance(avg_val, float) else str(avg_val)
                ))

            num_group.setLayout(num_layout)
            layout.addWidget(num_group)
        elif 'min' in self._stats:
            range_group = QGroupBox("Range")
            range_layout = QFormLayout()
            range_layout.addRow("Min:", QLabel(str(self._stats.get('min', ''))))
            range_layout.addRow("Max:", QLabel(str(self._stats.get('max', ''))))
            range_group.setLayout(range_layout)
            layout.addWidget(range_group)

        # Top values
        top_values = self._stats.get('top_values', [])
        if top_values:
            top_group = QGroupBox("Top Values (by frequency)")
            top_layout = QVBoxLayout()

            table = QTableWidget(len(top_values), 2)
            table.setHorizontalHeaderLabels(["Value", "Count"])
            table.horizontalHeader().setSectionResizeMode(
                0, QHeaderView.ResizeMode.Stretch
            )
            table.horizontalHeader().setSectionResizeMode(
                1, QHeaderView.ResizeMode.ResizeToContents
            )
            table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

            for i, (val, cnt) in enumerate(top_values):
                table.setItem(i, 0, QTableWidgetItem(str(val)))
                table.setItem(i, 1, QTableWidgetItem(f"{cnt:,}"))

            top_layout.addWidget(table)
            top_group.setLayout(top_layout)
            layout.addWidget(top_group)

        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)
