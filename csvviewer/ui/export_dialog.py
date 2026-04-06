"""Export dialog for saving filtered/selected data."""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QComboBox, QLineEdit, QPushButton, QLabel, QCheckBox,
    QGroupBox, QFileDialog, QProgressBar,
)
from PySide6.QtCore import Signal


class ExportDialog(QDialog):
    """Dialog for exporting CSV data with options."""

    export_requested = Signal(dict)

    def __init__(self, total_rows: int = 0, filtered_rows: int = 0,
                 selected_rows: int = 0, columns: list[str] | None = None,
                 parent=None):
        super().__init__(parent)
        self._total = total_rows
        self._filtered = filtered_rows
        self._selected = selected_rows
        self._columns = columns or []
        self.setWindowTitle("Export Data")
        self.setMinimumWidth(500)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        scope_group = QGroupBox("Export Scope")
        scope_layout = QVBoxLayout()
        self._all_radio = QCheckBox(f"All filtered rows ({self._filtered:,})")
        self._all_radio.setChecked(True)
        scope_layout.addWidget(self._all_radio)
        self._selected_radio = QCheckBox(
            f"Selected rows only ({self._selected:,})"
        )
        scope_layout.addWidget(self._selected_radio)
        self._visible_cols_check = QCheckBox("Visible columns only")
        self._visible_cols_check.setChecked(True)
        scope_layout.addWidget(self._visible_cols_check)
        scope_group.setLayout(scope_layout)
        layout.addWidget(scope_group)

        format_group = QGroupBox("Format")
        format_layout = QFormLayout()
        self._delimiter_combo = QComboBox()
        self._delimiter_combo.addItems(
            ["Comma (,)", "Semicolon (;)", "Tab", "Pipe (|)"]
        )
        format_layout.addRow("Delimiter:", self._delimiter_combo)
        self._encoding_combo = QComboBox()
        self._encoding_combo.addItems(["utf-8", "latin-1", "cp1252", "utf-16"])
        format_layout.addRow("Encoding:", self._encoding_combo)
        format_group.setLayout(format_layout)
        layout.addWidget(format_group)

        file_layout = QHBoxLayout()
        self._output_path = QLineEdit()
        self._output_path.setPlaceholderText("Select output file...")
        file_layout.addWidget(self._output_path, stretch=1)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse)
        file_layout.addWidget(browse_btn)
        layout.addLayout(file_layout)

        self._progress = QProgressBar()
        self._progress.hide()
        layout.addWidget(self._progress)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        export_btn = QPushButton("Export")
        export_btn.setDefault(True)
        export_btn.clicked.connect(self._do_export)
        btn_layout.addWidget(export_btn)
        layout.addLayout(btn_layout)

    def _browse(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export CSV", "",
            "CSV Files (*.csv);;TSV Files (*.tsv);;All Files (*)",
        )
        if path:
            self._output_path.setText(path)

    def _do_export(self):
        path = self._output_path.text().strip()
        if not path:
            return
        delims = [",", ";", "\t", "|"]
        self.export_requested.emit({
            "output_path": path,
            "delimiter": delims[self._delimiter_combo.currentIndex()],
            "encoding": self._encoding_combo.currentText(),
            "selected_only": self._selected_radio.isChecked(),
            "visible_columns_only": self._visible_cols_check.isChecked(),
        })
        self.accept()

    def set_progress(self, value: int):
        self._progress.show()
        self._progress.setValue(value)
