"""Column header context menu with sort, filter, stats, and visibility."""

from PySide6.QtWidgets import QMenu, QInputDialog, QMessageBox
from PySide6.QtCore import Signal, QObject


class ColumnMenuHandler(QObject):
    """Handles column header right-click context menu actions."""

    sort_ascending = Signal(str)
    sort_descending = Signal(str)
    filter_column = Signal(str)
    show_stats = Signal(str)
    hide_column = Signal(str)
    rename_column = Signal(str, str)  # old_name, new_name
    delete_column = Signal(str)
    freeze_column = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

    def show_menu(self, column_name: str, pos, parent_widget):
        """Show context menu for a column header."""
        menu = QMenu(parent_widget)

        sort_asc = menu.addAction("↑ Sort Ascending")
        sort_desc = menu.addAction("↓ Sort Descending")
        menu.addSeparator()
        filter_action = menu.addAction(f"🔍 Filter by '{column_name}'")
        menu.addSeparator()
        stats_action = menu.addAction("📊 Column Statistics")
        menu.addSeparator()
        rename_action = menu.addAction("✏️ Rename Column")
        hide_action = menu.addAction("👁 Hide Column")
        freeze_action = menu.addAction("📌 Freeze Column")
        delete_action = menu.addAction("🗑 Delete Column")

        action = menu.exec(parent_widget.mapToGlobal(pos))

        if action == sort_asc:
            self.sort_ascending.emit(column_name)
        elif action == sort_desc:
            self.sort_descending.emit(column_name)
        elif action == filter_action:
            self.filter_column.emit(column_name)
        elif action == stats_action:
            self.show_stats.emit(column_name)
        elif action == rename_action:
            new_name, ok = QInputDialog.getText(
                parent_widget, "Rename Column",
                f"New name for '{column_name}':", text=column_name,
            )
            if ok and new_name and new_name != column_name:
                self.rename_column.emit(column_name, new_name)
        elif action == hide_action:
            self.hide_column.emit(column_name)
        elif action == freeze_action:
            self.freeze_column.emit(column_name)
        elif action == delete_action:
            reply = QMessageBox.question(
                parent_widget, "Delete Column",
                f"Are you sure you want to delete column '{column_name}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.delete_column.emit(column_name)
