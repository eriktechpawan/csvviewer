"""Main application window for CSV Viewer.

Wires together all UI components, data engine, and edit history.
"""

import os

from PySide6.QtWidgets import (
    QMainWindow, QVBoxLayout, QWidget, QFileDialog,
    QMessageBox, QInputDialog, QMenu, QApplication,
)
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QKeySequence

from csvviewer.engine.data_engine import DataEngine
from csvviewer.engine.csv_loader import get_file_info
from csvviewer.engine.export import create_backup, format_file_size
from csvviewer.models.table_model import VirtualTableModel
from csvviewer.ui.table_view import CSVTableView
from csvviewer.ui.toolbar import MainToolBar
from csvviewer.ui.status_bar import CSVStatusBar
from csvviewer.ui.search_bar import SearchBar
from csvviewer.ui.filter_dialog import FilterDialog
from csvviewer.ui.stats_dialog import ColumnStatsDialog
from csvviewer.ui.import_dialog import ImportDialog
from csvviewer.ui.export_dialog import ExportDialog
from csvviewer.ui.column_menu import ColumnMenuHandler
from csvviewer.ui.cleanup_dialog import CleanupDialog
from csvviewer.ui.session_manager import SessionManager
from csvviewer.history.undo_redo import EditHistory, EditCommand, EditType
from csvviewer.utils.constants import APP_NAME, APP_VERSION, ColumnType


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} {APP_VERSION}")
        self.setMinimumSize(1200, 800)
        self.resize(1400, 900)

        # Core components
        self._engine = DataEngine()
        self._history = EditHistory()
        self._session_mgr = SessionManager()

        # Search state
        self._search_results: list = []
        self._search_index: int = 0

        # Setup
        self._setup_ui()
        self._setup_connections()
        self._setup_menus()
        self._update_ui_state()
        self._history.set_on_change(self._on_history_changed)

    # ------------------------------------------------------------------
    # UI setup
    # ------------------------------------------------------------------

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self._toolbar = MainToolBar(self)
        self.addToolBar(self._toolbar)

        self._search_bar = SearchBar(parent=self)
        self._search_bar.hide()
        main_layout.addWidget(self._search_bar)

        self._model = VirtualTableModel(self._engine)
        self._table_view = CSVTableView(self)
        self._table_view.setModel(self._model)
        main_layout.addWidget(self._table_view, stretch=1)

        self._status_bar = CSVStatusBar(self)
        self.setStatusBar(self._status_bar)

        self._col_menu = ColumnMenuHandler(self)

    def _setup_connections(self):
        # Toolbar
        self._toolbar.open_file.connect(self._open_file)
        self._toolbar.save_file.connect(self._save_file)
        self._toolbar.save_as.connect(self._save_as)
        self._toolbar.export.connect(self._export)
        self._toolbar.undo.connect(self._undo)
        self._toolbar.redo.connect(self._redo)
        self._toolbar.add_row.connect(self._add_row)
        self._toolbar.delete_rows.connect(self._delete_selected_rows)
        self._toolbar.add_column.connect(self._add_column)
        self._toolbar.toggle_filter.connect(self._show_filter_dialog)
        self._toolbar.toggle_search.connect(self._toggle_search)
        self._toolbar.toggle_read_only.connect(self._toggle_read_only)
        self._toolbar.cleanup_tools.connect(self._show_cleanup_dialog)

        # Table view
        self._table_view.cell_right_clicked.connect(self._on_cell_right_click)
        self._table_view.header_right_clicked.connect(self._on_header_right_click)
        self._table_view.selection_changed_signal.connect(self._update_selection_count)

        # Column menu
        self._col_menu.sort_ascending.connect(lambda c: self._sort_column(c, "ASC"))
        self._col_menu.sort_descending.connect(lambda c: self._sort_column(c, "DESC"))
        self._col_menu.filter_column.connect(self._filter_by_column)
        self._col_menu.show_stats.connect(self._show_column_stats)
        self._col_menu.hide_column.connect(self._hide_column)
        self._col_menu.rename_column.connect(self._rename_column)
        self._col_menu.delete_column.connect(self._delete_column)
        self._col_menu.freeze_column.connect(self._freeze_column)

        # Search
        self._search_bar.search_requested.connect(self._do_search)
        self._search_bar.next_match.connect(self._next_search_match)
        self._search_bar.prev_match.connect(self._prev_search_match)
        self._search_bar.search_closed.connect(self._clear_search)

        # Model
        self._model.data_changed_signal.connect(self._update_status)

    def _setup_menus(self):
        menu_bar = self.menuBar()

        # File
        file_menu = menu_bar.addMenu("File")
        file_menu.addAction("Open...", self._open_file, QKeySequence("Ctrl+O"))
        file_menu.addAction("Save", self._save_file, QKeySequence("Ctrl+S"))
        file_menu.addAction("Save As...", self._save_as, QKeySequence("Ctrl+Shift+S"))
        file_menu.addSeparator()
        file_menu.addAction("Export...", self._export, QKeySequence("Ctrl+E"))
        file_menu.addSeparator()
        self._recent_menu = file_menu.addMenu("Recent Files")
        self._update_recent_files_menu()
        file_menu.addSeparator()
        file_menu.addAction("Load Session...", self._load_session)
        file_menu.addAction("Save Session...", self._save_session)

        # Edit
        edit_menu = menu_bar.addMenu("Edit")
        edit_menu.addAction("Undo", self._undo, QKeySequence("Ctrl+Z"))
        edit_menu.addAction("Redo", self._redo, QKeySequence("Ctrl+Shift+Z"))
        edit_menu.addSeparator()
        edit_menu.addAction("Add Row", self._add_row)
        edit_menu.addAction("Delete Selected Rows", self._delete_selected_rows,
                            QKeySequence("Delete"))
        edit_menu.addAction("Duplicate Selected Rows", self._duplicate_selected_rows)
        edit_menu.addSeparator()
        edit_menu.addAction("Add Column...", self._add_column)
        edit_menu.addSeparator()
        edit_menu.addAction("Fill Down", self._fill_down)

        # View
        view_menu = menu_bar.addMenu("View")
        view_menu.addAction("Filter...", self._show_filter_dialog,
                            QKeySequence("Ctrl+F"))
        view_menu.addAction("Clear Filters", self._clear_filters)
        view_menu.addSeparator()
        view_menu.addAction("Search", self._toggle_search, QKeySequence("Ctrl+H"))
        view_menu.addSeparator()
        view_menu.addAction("Show All Columns", self._show_all_columns)
        view_menu.addSeparator()
        self._read_only_action = view_menu.addAction("Read Only Mode")
        self._read_only_action.setCheckable(True)
        self._read_only_action.toggled.connect(self._toggle_read_only)

        # Tools
        tools_menu = menu_bar.addMenu("Tools")
        tools_menu.addAction("Data Cleanup...", self._show_cleanup_dialog)
        tools_menu.addSeparator()
        tools_menu.addAction("Clear Sort", self._clear_sort)

    # ------------------------------------------------------------------
    # File operations
    # ------------------------------------------------------------------

    def _open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open CSV File", "",
            "CSV Files (*.csv *.tsv *.txt);;All Files (*)",
        )
        if path:
            self.open_file(path)

    def open_file(self, path: str, settings: dict | None = None):
        """Public API — open a CSV file, optionally with import settings."""
        if not os.path.exists(path):
            QMessageBox.warning(self, "Error", f"File not found: {path}")
            return

        if settings is None:
            dialog = ImportDialog(path, self)
            if dialog.exec() != ImportDialog.DialogCode.Accepted:
                return
            settings = dialog.get_settings()

        self._status_bar.set_status("Loading file...")
        QApplication.processEvents()

        try:
            result = self._engine.load_csv(
                file_path=settings.get("file_path", path),
                delimiter=settings.get("delimiter", ","),
                encoding=settings.get("encoding", "utf-8"),
                has_header=settings.get("has_header", True),
                quote_char=settings.get("quote_char", '"'),
                skip_rows=settings.get("skip_rows", 0),
            )

            self._model.refresh()
            self._search_bar.update_columns(result["columns"])

            file_info = get_file_info(path)
            self.setWindowTitle(
                f"{APP_NAME} - {file_info['name']} ({file_info['size_str']})"
            )

            self._session_mgr.add_recent_file(path)
            self._update_recent_files_menu()
            self._history.clear()
            self._status_bar.set_file_info(file_info["name"], file_info["size_str"])
            self._update_status()
            self._update_ui_state()
            self._status_bar.set_status(f"Loaded {result['total_rows']:,} rows")

            if result.get("warnings"):
                QMessageBox.warning(
                    self, "Import Warnings", "\n".join(result["warnings"])
                )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load file:\n{e}")
            self._status_bar.set_status("Error loading file")

    def _save_file(self):
        if not self._engine.is_loaded:
            return
        path = self._engine.file_path
        if not path:
            self._save_as()
            return

        reply = QMessageBox.question(
            self, "Save File",
            f"Overwrite {os.path.basename(path)}?\nA backup will be created.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        backup = create_backup(path)
        try:
            old_filters = self._engine.get_filters()
            self._engine.clear_filters()
            count = self._engine.export_csv(path)
            self._engine.set_filters(old_filters)
            self._history.mark_saved()
            msg = f"Saved {count:,} rows"
            if backup:
                msg += f" (backup: {os.path.basename(backup)})"
            self._status_bar.set_status(msg)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save:\n{e}")

    def _save_as(self):
        if not self._engine.is_loaded:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save As", "",
            "CSV Files (*.csv);;TSV Files (*.tsv);;All Files (*)",
        )
        if not path:
            return
        try:
            old_filters = self._engine.get_filters()
            self._engine.clear_filters()
            count = self._engine.export_csv(path)
            self._engine.set_filters(old_filters)
            self._history.mark_saved()
            self._status_bar.set_status(
                f"Saved {count:,} rows to {os.path.basename(path)}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save:\n{e}")

    def _export(self):
        if not self._engine.is_loaded:
            return
        selected = self._get_selected_row_ids()
        dialog = ExportDialog(
            total_rows=self._engine.total_rows,
            filtered_rows=self._engine.get_filtered_row_count(),
            selected_rows=len(selected),
            columns=self._engine.visible_columns,
            parent=self,
        )
        dialog.export_requested.connect(self._do_export)
        dialog.exec()

    def _do_export(self, settings: dict):
        try:
            selected_ids = (
                self._get_selected_row_ids()
                if settings.get("selected_only") else None
            )
            columns = (
                self._engine.visible_columns
                if settings.get("visible_columns_only") else None
            )
            count = self._engine.export_csv(
                output_path=settings["output_path"],
                delimiter=settings.get("delimiter", ","),
                selected_row_ids=selected_ids,
                columns=columns,
            )
            self._status_bar.set_status(f"Exported {count:,} rows")
            QMessageBox.information(
                self, "Export Complete",
                f"Exported {count:,} rows to {settings['output_path']}",
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Export failed:\n{e}")

    # ------------------------------------------------------------------
    # Editing
    # ------------------------------------------------------------------

    def _add_row(self):
        if not self._engine.is_loaded or self._engine.read_only:
            return
        new_id = self._engine.add_row()
        self._history.push(EditCommand(
            edit_type=EditType.ROW_ADD,
            description="Add Row",
            undo_data={"row_ids": [new_id]},
            redo_data={},
        ))
        self._model.refresh()
        self._update_status()

    def _delete_selected_rows(self):
        if not self._engine.is_loaded or self._engine.read_only:
            return
        row_ids = self._get_selected_row_ids()
        if not row_ids:
            return
        reply = QMessageBox.question(
            self, "Delete Rows",
            f"Delete {len(row_ids)} selected row(s)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        deleted = self._engine.delete_rows(row_ids)
        self._history.push(EditCommand(
            edit_type=EditType.ROW_DELETE,
            description=f"Delete {len(deleted)} Row(s)",
            undo_data={"rows": deleted},
            redo_data={"row_ids": row_ids},
        ))
        self._model.refresh()
        self._update_status()

    def _duplicate_selected_rows(self):
        if not self._engine.is_loaded or self._engine.read_only:
            return
        row_ids = self._get_selected_row_ids()
        if not row_ids:
            return
        new_ids = self._engine.duplicate_rows(row_ids)
        self._history.push(EditCommand(
            edit_type=EditType.ROW_DUPLICATE,
            description=f"Duplicate {len(new_ids)} Row(s)",
            undo_data={"row_ids": new_ids},
            redo_data={"source_ids": row_ids},
        ))
        self._model.refresh()
        self._update_status()

    def _add_column(self):
        if not self._engine.is_loaded or self._engine.read_only:
            return
        name, ok = QInputDialog.getText(self, "Add Column", "Column name:")
        if not ok or not name:
            return
        if self._engine.add_column(name):
            self._history.push(EditCommand(
                edit_type=EditType.COLUMN_ADD,
                description=f"Add Column '{name}'",
                undo_data={"name": name},
                redo_data={"name": name},
            ))
            self._model.refresh()
            self._search_bar.update_columns(self._engine.visible_columns)
            self._update_status()
        else:
            QMessageBox.warning(self, "Error", f"Could not add column '{name}'")

    def _delete_column(self, column_name: str):
        if self._engine.read_only:
            return
        col_data = self._engine.delete_column(column_name)
        self._history.push(EditCommand(
            edit_type=EditType.COLUMN_DELETE,
            description=f"Delete Column '{column_name}'",
            undo_data=col_data,
            redo_data={"name": column_name},
        ))
        self._model.refresh()
        self._search_bar.update_columns(self._engine.visible_columns)
        self._update_status()

    def _rename_column(self, old_name: str, new_name: str):
        if self._engine.read_only:
            return
        if self._engine.rename_column(old_name, new_name):
            self._history.push(EditCommand(
                edit_type=EditType.COLUMN_RENAME,
                description=f"Rename '{old_name}' to '{new_name}'",
                undo_data={"old_name": new_name, "new_name": old_name},
                redo_data={"old_name": old_name, "new_name": new_name},
            ))
            self._model.refresh()
            self._search_bar.update_columns(self._engine.visible_columns)

    def _fill_down(self):
        if not self._engine.is_loaded or self._engine.read_only:
            return
        indexes = self._table_view.selectionModel().selectedIndexes()
        if len(indexes) < 2:
            return
        first = indexes[0]
        value = self._model.data(first, Qt.ItemDataRole.EditRole)
        col_name = self._model.get_column_name(first.column())
        if not col_name:
            return
        for idx in indexes[1:]:
            if idx.column() == first.column():
                row_id = self._model.get_row_id(idx.row())
                if row_id is not None:
                    self._engine.update_cell(row_id, col_name, value)
        self._model.invalidate_cache()
        self._model.refresh()

    # ------------------------------------------------------------------
    # Undo / Redo
    # ------------------------------------------------------------------

    def _undo(self):
        cmd = self._history.undo()
        if cmd:
            self._apply_undo(cmd)

    def _redo(self):
        cmd = self._history.redo()
        if cmd:
            self._apply_redo(cmd)

    def _apply_undo(self, cmd: EditCommand):
        if cmd.edit_type == EditType.ROW_ADD:
            self._engine.delete_rows(cmd.undo_data["row_ids"])
        elif cmd.edit_type == EditType.ROW_DELETE:
            self._engine.restore_rows(cmd.undo_data["rows"])
        elif cmd.edit_type == EditType.ROW_DUPLICATE:
            self._engine.delete_rows(cmd.undo_data["row_ids"])
        elif cmd.edit_type == EditType.COLUMN_ADD:
            self._engine.delete_column(cmd.undo_data["name"])
        elif cmd.edit_type == EditType.COLUMN_DELETE:
            data = cmd.undo_data
            self._engine.add_column(data["name"])
            for row_id, val in data["data"]:
                if val is not None:
                    self._engine.update_cell(row_id, data["name"], val)
        elif cmd.edit_type == EditType.COLUMN_RENAME:
            self._engine.rename_column(
                cmd.undo_data["old_name"], cmd.undo_data["new_name"]
            )
        elif cmd.edit_type == EditType.CELL_EDIT:
            self._engine.update_cell(
                cmd.undo_data["row_id"],
                cmd.undo_data["column"],
                cmd.undo_data["old_value"],
            )
        self._model.refresh()
        self._search_bar.update_columns(self._engine.visible_columns)
        self._update_status()

    def _apply_redo(self, cmd: EditCommand):
        if cmd.edit_type == EditType.ROW_ADD:
            self._engine.add_row()
        elif cmd.edit_type == EditType.ROW_DELETE:
            self._engine.delete_rows(cmd.redo_data["row_ids"])
        elif cmd.edit_type == EditType.ROW_DUPLICATE:
            self._engine.duplicate_rows(cmd.redo_data["source_ids"])
        elif cmd.edit_type == EditType.COLUMN_ADD:
            self._engine.add_column(cmd.redo_data["name"])
        elif cmd.edit_type == EditType.COLUMN_DELETE:
            self._engine.delete_column(cmd.redo_data["name"])
        elif cmd.edit_type == EditType.COLUMN_RENAME:
            self._engine.rename_column(
                cmd.redo_data["old_name"], cmd.redo_data["new_name"]
            )
        elif cmd.edit_type == EditType.CELL_EDIT:
            self._engine.update_cell(
                cmd.redo_data["row_id"],
                cmd.redo_data["column"],
                cmd.redo_data["new_value"],
            )
        self._model.refresh()
        self._search_bar.update_columns(self._engine.visible_columns)
        self._update_status()

    def _on_history_changed(self):
        self._toolbar.update_undo_redo(
            self._history.can_undo,
            self._history.can_redo,
            self._history.undo_text,
            self._history.redo_text,
        )

    # ------------------------------------------------------------------
    # Filtering
    # ------------------------------------------------------------------

    def _show_filter_dialog(self):
        if not self._engine.is_loaded:
            return
        dialog = FilterDialog(
            columns=self._engine.visible_columns,
            column_types={
                c: self._engine.get_column_type(c) for c in self._engine.columns
            },
            current_filters=self._engine.get_filters(),
            parent=self,
        )
        dialog.filters_applied.connect(self._apply_filters)
        dialog.exec()

    def _apply_filters(self, filters: list, logic: str = "AND"):
        self._engine.set_filters(filters, logic)
        self._model.refresh()
        self._update_status()
        count = self._engine.get_filtered_row_count()
        self._status_bar.set_status(f"Filter applied: {count:,} rows match")

    def _filter_by_column(self, column_name: str):
        if not self._engine.is_loaded:
            return
        dialog = FilterDialog(
            columns=self._engine.visible_columns,
            column_types={
                c: self._engine.get_column_type(c) for c in self._engine.columns
            },
            current_filters=[{"column": column_name, "operator": "NOT_EMPTY"}],
            parent=self,
        )
        dialog.filters_applied.connect(self._apply_filters)
        dialog.exec()

    def _clear_filters(self):
        self._engine.clear_filters()
        self._model.refresh()
        self._update_status()
        self._status_bar.set_status("Filters cleared")

    # ------------------------------------------------------------------
    # Sorting
    # ------------------------------------------------------------------

    def _sort_column(self, column_name: str, direction: str):
        self._engine.set_sort([(column_name, direction)])
        self._model.refresh()
        self._status_bar.set_status(f"Sorted by {column_name} {direction}")

    def _clear_sort(self):
        self._engine.clear_sort()
        self._model.refresh()
        self._status_bar.set_status("Sort cleared")

    # ------------------------------------------------------------------
    # Column operations
    # ------------------------------------------------------------------

    def _hide_column(self, column_name: str):
        self._engine.hide_column(column_name)
        self._model.refresh()
        self._update_status()

    def _show_all_columns(self):
        self._engine.set_hidden_columns(set())
        self._model.refresh()
        self._update_status()

    def _freeze_column(self, column_name: str):
        cols = self._engine.columns
        if column_name in cols:
            cols.remove(column_name)
            cols.insert(0, column_name)
            self._engine.reorder_columns(cols)
            self._model.refresh()

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def _show_column_stats(self, column_name: str):
        if not self._engine.is_loaded:
            return
        try:
            stats = self._engine.get_column_stats(column_name)
            ColumnStatsDialog(stats, self).exec()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not compute stats:\n{e}")

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def _toggle_search(self):
        if self._search_bar.isVisible():
            self._search_bar.hide()
            self._clear_search()
        else:
            self._search_bar.show()
            self._search_bar.focus_search()

    def _do_search(self, query: str, column: str, case_sensitive: bool):
        if not self._engine.is_loaded:
            return
        col = column or None
        results = self._engine.search(query, col, case_sensitive)
        self._search_results = results
        self._search_index = 0
        self._search_bar.set_result_count(len(results), 1 if results else 0)
        if results:
            self._go_to_search_result(0)
        self._status_bar.set_status(f"Found {len(results)} matches")

    def _next_search_match(self):
        if not self._search_results:
            return
        self._search_index = (self._search_index + 1) % len(self._search_results)
        self._go_to_search_result(self._search_index)
        self._search_bar.set_result_count(
            len(self._search_results), self._search_index + 1
        )

    def _prev_search_match(self):
        if not self._search_results:
            return
        self._search_index = (self._search_index - 1) % len(self._search_results)
        self._go_to_search_result(self._search_index)
        self._search_bar.set_result_count(
            len(self._search_results), self._search_index + 1
        )

    def _go_to_search_result(self, idx: int):
        if idx >= len(self._search_results):
            return
        row_id, col_name, _ = self._search_results[idx]
        try:
            cols = self._engine.visible_columns
            col_idx = cols.index(col_name) if col_name in cols else 0
            filtered_ids = self._engine.fetch_all_row_ids()
            if row_id in filtered_ids:
                display_row = filtered_ids.index(row_id)
                index = self._model.index(display_row, col_idx)
                self._table_view.scrollTo(index)
                self._table_view.setCurrentIndex(index)
        except Exception:
            pass

    def _clear_search(self):
        self._search_results = []
        self._search_index = 0
        self._model.clear_search_matches()

    # ------------------------------------------------------------------
    # Context menus
    # ------------------------------------------------------------------

    def _on_cell_right_click(self, row: int, col: int):
        menu = QMenu(self)
        menu.addAction("Copy Cell Value", lambda: self._copy_cell(row, col))
        if not self._engine.read_only:
            menu.addAction(
                "Edit Cell",
                lambda: self._table_view.edit(self._model.index(row, col)),
            )
            menu.addSeparator()
            menu.addAction("Add Row Below", self._add_row)
            menu.addAction("Delete Row", self._delete_selected_rows)
            menu.addAction("Duplicate Row", self._duplicate_selected_rows)
        menu.addSeparator()
        col_name = self._model.get_column_name(col)
        if col_name:
            menu.addAction(
                f"Filter: {col_name}",
                lambda: self._filter_by_column(col_name),
            )
            menu.addAction(
                f"Stats: {col_name}",
                lambda: self._show_column_stats(col_name),
            )
        menu.exec(
            self._table_view.viewport().mapToGlobal(
                self._table_view.visualRect(self._model.index(row, col)).center()
            )
        )

    def _on_header_right_click(self, col: int):
        col_name = self._model.get_column_name(col)
        if col_name:
            pos = self._table_view.horizontalHeader().sectionPosition(col)
            self._col_menu.show_menu(
                col_name,
                QPoint(pos, 0),
                self._table_view.horizontalHeader(),
            )

    def _copy_cell(self, row: int, col: int):
        value = self._model.data(self._model.index(row, col))
        if value:
            QApplication.clipboard().setText(str(value))

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def _show_cleanup_dialog(self):
        if not self._engine.is_loaded:
            return
        dialog = CleanupDialog(self._engine.columns, self)
        dialog.action_requested.connect(self._do_cleanup)
        dialog.exec()

    def _do_cleanup(self, action: str, params: dict):
        try:
            if action == "remove_duplicates":
                count = self._engine.remove_duplicates()
                self._status_bar.set_status(f"Removed {count} duplicate rows")
                self._history.push(EditCommand(
                    edit_type=EditType.REMOVE_DUPLICATES,
                    description=f"Remove {count} Duplicates",
                    undo_data={}, redo_data={},
                ))
            elif action == "trim_whitespace":
                count = self._engine.trim_whitespace(params["column"])
                self._status_bar.set_status(
                    f"Trimmed {count} cells in {params['column']}"
                )
                self._history.push(EditCommand(
                    edit_type=EditType.TRIM_WHITESPACE,
                    description=f"Trim {params['column']}",
                    undo_data={}, redo_data={},
                ))
            elif action == "find_replace":
                count = self._engine.find_replace(
                    params["column"], params["find"], params["replace"],
                    params.get("case_sensitive", True),
                )
                self._status_bar.set_status(f"Replaced {count} occurrences")
                self._history.push(EditCommand(
                    edit_type=EditType.REPLACE,
                    description=f"Replace in {params['column']}",
                    undo_data={}, redo_data={},
                ))
            elif action == "convert_type":
                type_map = {
                    "text": ColumnType.TEXT,
                    "integer": ColumnType.INTEGER,
                    "float": ColumnType.FLOAT,
                    "boolean": ColumnType.BOOLEAN,
                    "datetime": ColumnType.DATETIME,
                }
                new_type = type_map.get(params["new_type"], ColumnType.TEXT)
                self._engine.override_column_type(params["column"], new_type)
                self._status_bar.set_status(
                    f"Changed {params['column']} type to {params['new_type']}"
                )
            self._model.refresh()
            self._update_status()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Cleanup failed:\n{e}")

    # ------------------------------------------------------------------
    # Session
    # ------------------------------------------------------------------

    def _save_session(self):
        if not self._engine.is_loaded:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Session", "",
            "CSV Viewer Sessions (*.csvproj);;All Files (*)",
        )
        if not path:
            return
        state = self._engine.get_session_state()
        widths = {}
        for i, col in enumerate(self._engine.visible_columns):
            widths[col] = self._table_view.columnWidth(i)
        state["column_widths"] = widths
        session_path = self._session_mgr.save(state, path)
        self._status_bar.set_status(
            f"Session saved to {os.path.basename(str(session_path))}"
        )

    def _load_session(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Session", "",
            "CSV Viewer Sessions (*.csvproj);;All Files (*)",
        )
        if not path:
            return
        data = self._session_mgr.load(path)
        if not data:
            QMessageBox.warning(self, "Error", "Failed to load session file.")
            return
        file_path = data.get("file_path", "")
        if not file_path or not os.path.exists(file_path):
            QMessageBox.warning(self, "Error", f"CSV file not found: {file_path}")
            return
        self.open_file(file_path, {
            "file_path": file_path,
            "delimiter": ",",
            "encoding": "utf-8",
            "has_header": True,
        })
        self._engine.restore_session_state(data)
        widths = data.get("column_widths", {})
        for i, col in enumerate(self._engine.visible_columns):
            if col in widths:
                self._table_view.setColumnWidth(i, widths[col])
        self._model.refresh()
        self._update_status()
        self._status_bar.set_status("Session restored")

    # ------------------------------------------------------------------
    # Read-only mode
    # ------------------------------------------------------------------

    def _toggle_read_only(self, checked: bool):
        self._engine.read_only = checked
        self._toolbar.set_read_only(checked)
        self._read_only_action.setChecked(checked)
        self._model.refresh()
        self._status_bar.set_status(
            "Read-only mode enabled" if checked else "Read-only mode disabled"
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_selected_row_ids(self) -> list[int]:
        display_rows = self._table_view.get_selected_rows()
        row_ids = []
        for dr in display_rows:
            rid = self._model.get_row_id(dr)
            if rid is not None:
                row_ids.append(rid)
        return row_ids

    def _update_status(self):
        if not self._engine.is_loaded:
            self._status_bar.update_counts()
            return
        filtered = self._engine.get_filtered_row_count()
        selected = len(self._table_view.get_selected_rows())
        self._status_bar.update_counts(
            total=self._engine.total_rows,
            filtered=filtered,
            selected=selected,
            columns=len(self._engine.visible_columns),
            file_size=(
                format_file_size(self._engine.file_size)
                if self._engine.file_size else ""
            ),
        )

    def _update_selection_count(self):
        if not self._engine.is_loaded:
            return
        selected = len(self._table_view.get_selected_rows())
        self._status_bar._selected_label.setText(f"Selected: {selected:,}")

    def _update_ui_state(self):
        self._on_history_changed()

    def _update_recent_files_menu(self):
        self._recent_menu.clear()
        for path in self._session_mgr.get_recent_files():
            name = os.path.basename(path)
            action = self._recent_menu.addAction(name)
            action.setData(path)
            action.triggered.connect(
                lambda checked, p=path: self.open_file(p)
            )

    def closeEvent(self, event):
        if self._history.is_modified:
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                "You have unsaved changes. Are you sure you want to quit?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        self._engine.close()
        event.accept()
