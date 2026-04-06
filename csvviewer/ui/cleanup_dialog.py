"""Data cleanup tools dialog."""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout,
    QComboBox, QLineEdit, QPushButton, QLabel, QCheckBox,
    QGroupBox, QTabWidget, QWidget, QMessageBox,
)
from PySide6.QtCore import Signal


class CleanupDialog(QDialog):
    """Dialog with data cleanup tools: dedup, trim, find/replace, type convert."""

    action_requested = Signal(str, dict)

    def __init__(self, columns: list[str], parent=None):
        super().__init__(parent)
        self._columns = columns
        self.setWindowTitle("Data Cleanup Tools")
        self.setMinimumSize(500, 400)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        tabs = QTabWidget()

        # Duplicates
        dedup_tab = QWidget()
        dedup_layout = QVBoxLayout(dedup_tab)
        dedup_layout.addWidget(QLabel("Remove duplicate rows based on all columns."))
        dedup_btn = QPushButton("Remove Duplicates")
        dedup_btn.clicked.connect(self._remove_duplicates)
        dedup_layout.addWidget(dedup_btn)
        dedup_layout.addStretch()
        tabs.addTab(dedup_tab, "Duplicates")

        # Trim
        trim_tab = QWidget()
        trim_layout = QVBoxLayout(trim_tab)
        trim_layout.addWidget(
            QLabel("Trim leading/trailing whitespace from a column.")
        )
        trim_form = QFormLayout()
        self._trim_col = QComboBox()
        self._trim_col.addItems(self._columns)
        trim_form.addRow("Column:", self._trim_col)
        trim_layout.addLayout(trim_form)
        trim_btn = QPushButton("Trim Whitespace")
        trim_btn.clicked.connect(self._trim_whitespace)
        trim_layout.addWidget(trim_btn)
        trim_layout.addStretch()
        tabs.addTab(trim_tab, "Trim")

        # Find & Replace
        replace_tab = QWidget()
        replace_layout = QVBoxLayout(replace_tab)
        replace_form = QFormLayout()
        self._replace_col = QComboBox()
        self._replace_col.addItems(self._columns)
        replace_form.addRow("Column:", self._replace_col)
        self._find_input = QLineEdit()
        replace_form.addRow("Find:", self._find_input)
        self._replace_input = QLineEdit()
        replace_form.addRow("Replace:", self._replace_input)
        self._replace_case = QCheckBox("Case sensitive")
        self._replace_case.setChecked(True)
        replace_form.addRow("", self._replace_case)
        replace_layout.addLayout(replace_form)
        replace_btn = QPushButton("Find & Replace")
        replace_btn.clicked.connect(self._find_replace)
        replace_layout.addWidget(replace_btn)
        replace_layout.addStretch()
        tabs.addTab(replace_tab, "Find/Replace")

        # Convert Type
        convert_tab = QWidget()
        convert_layout = QVBoxLayout(convert_tab)
        convert_form = QFormLayout()
        self._convert_col = QComboBox()
        self._convert_col.addItems(self._columns)
        convert_form.addRow("Column:", self._convert_col)
        self._convert_type = QComboBox()
        self._convert_type.addItems(
            ["text", "integer", "float", "boolean", "datetime"]
        )
        convert_form.addRow("New Type:", self._convert_type)
        convert_layout.addLayout(convert_form)
        convert_btn = QPushButton("Convert Type")
        convert_btn.clicked.connect(self._convert_type_action)
        convert_layout.addWidget(convert_btn)
        convert_layout.addStretch()
        tabs.addTab(convert_tab, "Convert Type")

        layout.addWidget(tabs)

        self._result_label = QLabel("")
        layout.addWidget(self._result_label)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

    def _remove_duplicates(self):
        self.action_requested.emit("remove_duplicates", {})

    def _trim_whitespace(self):
        self.action_requested.emit("trim_whitespace", {
            "column": self._trim_col.currentText(),
        })

    def _find_replace(self):
        find_text = self._find_input.text()
        if not find_text:
            QMessageBox.warning(self, "Warning", "Please enter text to find.")
            return
        self.action_requested.emit("find_replace", {
            "column": self._replace_col.currentText(),
            "find": find_text,
            "replace": self._replace_input.text(),
            "case_sensitive": self._replace_case.isChecked(),
        })

    def _convert_type_action(self):
        self.action_requested.emit("convert_type", {
            "column": self._convert_col.currentText(),
            "new_type": self._convert_type.currentText(),
        })

    def set_result(self, text: str):
        self._result_label.setText(text)
