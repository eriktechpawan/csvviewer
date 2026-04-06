"""Main toolbar with common actions."""

from PySide6.QtWidgets import QToolBar, QWidget, QHBoxLayout, QLabel
from PySide6.QtGui import QAction
from PySide6.QtCore import Signal


class MainToolBar(QToolBar):
    """Application toolbar with file, edit, and view actions."""

    open_file = Signal()
    save_file = Signal()
    save_as = Signal()
    export = Signal()
    undo = Signal()
    redo = Signal()
    add_row = Signal()
    delete_rows = Signal()
    add_column = Signal()
    toggle_filter = Signal()
    toggle_search = Signal()
    toggle_read_only = Signal(bool)
    cleanup_tools = Signal()

    def __init__(self, parent=None):
        super().__init__("Main Toolbar", parent)
        self.setMovable(False)
        self._create_actions()

    def _create_actions(self):
        # File actions
        self._open_action = QAction("📂 Open", self)
        self._open_action.setShortcut("Ctrl+O")
        self._open_action.triggered.connect(self.open_file)
        self.addAction(self._open_action)

        self._save_action = QAction("💾 Save", self)
        self._save_action.setShortcut("Ctrl+S")
        self._save_action.triggered.connect(self.save_file)
        self.addAction(self._save_action)

        self._save_as_action = QAction("📄 Save As", self)
        self._save_as_action.setShortcut("Ctrl+Shift+S")
        self._save_as_action.triggered.connect(self.save_as)
        self.addAction(self._save_as_action)

        self._export_action = QAction("📤 Export", self)
        self._export_action.setShortcut("Ctrl+E")
        self._export_action.triggered.connect(self.export)
        self.addAction(self._export_action)

        self.addSeparator()

        # Edit actions
        self._undo_action = QAction("↩ Undo", self)
        self._undo_action.setShortcut("Ctrl+Z")
        self._undo_action.triggered.connect(self.undo)
        self.addAction(self._undo_action)

        self._redo_action = QAction("↪ Redo", self)
        self._redo_action.setShortcut("Ctrl+Shift+Z")
        self._redo_action.triggered.connect(self.redo)
        self.addAction(self._redo_action)

        self.addSeparator()

        # Row/Column actions
        self._add_row_action = QAction("➕ Add Row", self)
        self._add_row_action.triggered.connect(self.add_row)
        self.addAction(self._add_row_action)

        self._delete_rows_action = QAction("🗑 Delete Rows", self)
        self._delete_rows_action.setShortcut("Delete")
        self._delete_rows_action.triggered.connect(self.delete_rows)
        self.addAction(self._delete_rows_action)

        self._add_col_action = QAction("📊 Add Column", self)
        self._add_col_action.triggered.connect(self.add_column)
        self.addAction(self._add_col_action)

        self.addSeparator()

        # View actions
        self._filter_action = QAction("🔍 Filter", self)
        self._filter_action.setShortcut("Ctrl+F")
        self._filter_action.triggered.connect(self.toggle_filter)
        self.addAction(self._filter_action)

        self._search_action = QAction("🔎 Search", self)
        self._search_action.setShortcut("Ctrl+H")
        self._search_action.triggered.connect(self.toggle_search)
        self.addAction(self._search_action)

        self.addSeparator()

        # Tools
        self._cleanup_action = QAction("🧹 Cleanup", self)
        self._cleanup_action.triggered.connect(self.cleanup_tools)
        self.addAction(self._cleanup_action)

        self._read_only_action = QAction("🔒 Read Only", self)
        self._read_only_action.setCheckable(True)
        self._read_only_action.toggled.connect(self.toggle_read_only)
        self.addAction(self._read_only_action)

    def update_undo_redo(self, can_undo: bool, can_redo: bool,
                         undo_text: str = "Undo", redo_text: str = "Redo"):
        self._undo_action.setEnabled(can_undo)
        self._redo_action.setEnabled(can_redo)
        self._undo_action.setText(f"↩ {undo_text}")
        self._redo_action.setText(f"↪ {redo_text}")

    def set_read_only(self, read_only: bool):
        self._read_only_action.setChecked(read_only)
