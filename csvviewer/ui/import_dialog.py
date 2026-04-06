"""CSV import dialog with preview and settings override."""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QComboBox, QLineEdit, QPushButton, QLabel, QCheckBox,
    QGroupBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QSpinBox,
)
from PySide6.QtCore import Signal
from csvviewer.engine.csv_loader import auto_detect_csv


class ImportDialog(QDialog):
    """Dialog for CSV import with preview and settings."""

    import_accepted = Signal(dict)

    def __init__(self, file_path: str, parent=None):
        super().__init__(parent)
        self._file_path = file_path
        self.setWindowTitle(f"Import CSV: {file_path.split('/')[-1]}")
        self.setMinimumSize(800, 600)
        self._detected = auto_detect_csv(file_path)
        self._setup_ui()
        self._update_preview()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        info = self._detected.get("file_info", {})
        layout.addWidget(
            QLabel(f"File: {info.get('name', '')} ({info.get('size_str', '')})")
        )

        settings_group = QGroupBox("Import Settings")
        settings_layout = QFormLayout()

        self._delimiter_combo = QComboBox()
        det = self._detected["delimiter"]
        self._delimiter_combo.addItems([
            f"Comma (,){' [detected]' if det == ',' else ''}",
            f"Semicolon (;){' [detected]' if det == ';' else ''}",
            f"Tab{' [detected]' if det == chr(9) else ''}",
            f"Pipe (|){' [detected]' if det == '|' else ''}",
            "Custom...",
        ])
        delim_map = {",": 0, ";": 1, "\t": 2, "|": 3}
        self._delimiter_combo.setCurrentIndex(delim_map.get(det, 0))
        self._delimiter_combo.currentIndexChanged.connect(self._on_settings_changed)
        settings_layout.addRow("Delimiter:", self._delimiter_combo)

        self._custom_delim = QLineEdit()
        self._custom_delim.setMaximumWidth(50)
        self._custom_delim.hide()
        self._custom_delim.textChanged.connect(self._on_settings_changed)
        settings_layout.addRow("Custom:", self._custom_delim)

        self._encoding_combo = QComboBox()
        self._encoding_combo.addItems(
            ["utf-8", "latin-1", "iso-8859-1", "cp1252", "ascii", "utf-16"]
        )
        detected_enc = self._detected.get("encoding", "utf-8")
        idx = self._encoding_combo.findText(detected_enc)
        if idx >= 0:
            self._encoding_combo.setCurrentIndex(idx)
        self._encoding_combo.currentIndexChanged.connect(self._on_settings_changed)
        settings_layout.addRow("Encoding:", self._encoding_combo)

        self._quote_combo = QComboBox()
        self._quote_combo.addItems(['"', "'", "None"])
        settings_layout.addRow("Quote Char:", self._quote_combo)

        self._header_check = QCheckBox("First row is header")
        self._header_check.setChecked(self._detected.get("has_header", True))
        self._header_check.stateChanged.connect(self._on_settings_changed)
        settings_layout.addRow("", self._header_check)

        self._skip_rows = QSpinBox()
        self._skip_rows.setRange(0, 1000)
        self._skip_rows.valueChanged.connect(self._on_settings_changed)
        settings_layout.addRow("Skip Rows:", self._skip_rows)

        settings_group.setLayout(settings_layout)
        layout.addWidget(settings_group)

        preview_group = QGroupBox("Preview (first 100 rows)")
        preview_layout = QVBoxLayout()
        self._preview_table = QTableWidget()
        self._preview_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._preview_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive
        )
        self._preview_table.horizontalHeader().setDefaultSectionSize(120)
        preview_layout.addWidget(self._preview_table)
        preview_group.setLayout(preview_layout)
        layout.addWidget(preview_group, stretch=1)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        import_btn = QPushButton("Import")
        import_btn.setDefault(True)
        import_btn.clicked.connect(self._do_import)
        btn_layout.addWidget(import_btn)
        layout.addLayout(btn_layout)

    def _get_delimiter(self) -> str:
        idx = self._delimiter_combo.currentIndex()
        delims = [",", ";", "\t", "|"]
        if idx < len(delims):
            return delims[idx]
        return self._custom_delim.text() or ","

    def _on_settings_changed(self):
        self._custom_delim.setVisible(self._delimiter_combo.currentIndex() == 4)
        self._update_preview()

    def _update_preview(self):
        try:
            import duckdb

            delimiter = self._get_delimiter()
            has_header = self._header_check.isChecked()
            conn = duckdb.connect(":memory:")
            try:
                result = conn.execute(
                    f"SELECT * FROM read_csv("
                    f"'{self._file_path.replace(chr(39), chr(39)+chr(39))}', "
                    f"header={str(has_header).lower()}, "
                    f"delim='{delimiter}', "
                    f"auto_detect=true, ignore_errors=true) LIMIT 100"
                )
                columns = [desc[0] for desc in result.description]
                rows = result.fetchall()
                self._preview_table.setColumnCount(len(columns))
                self._preview_table.setRowCount(len(rows))
                self._preview_table.setHorizontalHeaderLabels(columns)
                for i, row in enumerate(rows):
                    for j, val in enumerate(row):
                        self._preview_table.setItem(
                            i, j,
                            QTableWidgetItem(str(val) if val is not None else ""),
                        )
            finally:
                conn.close()
        except Exception as e:
            self._preview_table.setColumnCount(1)
            self._preview_table.setRowCount(1)
            self._preview_table.setItem(0, 0, QTableWidgetItem(f"Error: {e}"))

    def _do_import(self):
        settings = self.get_settings()
        self.import_accepted.emit(settings)
        self.accept()

    def get_settings(self) -> dict:
        quote = self._quote_combo.currentText()
        return {
            "file_path": self._file_path,
            "delimiter": self._get_delimiter(),
            "encoding": self._encoding_combo.currentText(),
            "has_header": self._header_check.isChecked(),
            "quote_char": quote if quote != "None" else '"',
            "skip_rows": self._skip_rows.value(),
        }
