"""Custom table view with smooth scrolling and context menus."""

from PySide6.QtWidgets import QTableView, QHeaderView, QAbstractItemView
from PySide6.QtCore import Qt, Signal


class CSVTableView(QTableView):
    """Customized table view for CSV data display.

    Features:
    - Smooth pixel-by-pixel scrolling
    - Resizable and reorderable columns
    - Right-click context menus
    - Row/column selection tracking
    """

    cell_right_clicked = Signal(int, int)  # row, col
    header_right_clicked = Signal(int)  # col
    selection_changed_signal = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_view()

    def _setup_view(self):
        # Smooth scrolling
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)

        # Selection
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)

        # Headers
        h_header = self.horizontalHeader()
        h_header.setSectionsMovable(True)
        h_header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        h_header.setDefaultSectionSize(120)
        h_header.setMinimumSectionSize(50)
        h_header.setStretchLastSection(True)
        h_header.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        h_header.customContextMenuRequested.connect(self._on_header_context_menu)

        v_header = self.verticalHeader()
        v_header.setDefaultSectionSize(25)
        v_header.setMinimumSectionSize(20)

        # Grid
        self.setShowGrid(True)
        self.setGridStyle(Qt.PenStyle.SolidLine)
        self.setAlternatingRowColors(True)

        # Context menu
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_context_menu)

        # Word wrap off for performance
        self.setWordWrap(False)

    def _on_context_menu(self, pos):
        index = self.indexAt(pos)
        if index.isValid():
            self.cell_right_clicked.emit(index.row(), index.column())

    def _on_header_context_menu(self, pos):
        col = self.horizontalHeader().logicalIndexAt(pos)
        if col >= 0:
            self.header_right_clicked.emit(col)

    def selectionChanged(self, selected, deselected):
        super().selectionChanged(selected, deselected)
        self.selection_changed_signal.emit()

    def get_selected_rows(self) -> list[int]:
        """Get unique selected row indices."""
        return list(set(idx.row() for idx in self.selectionModel().selectedIndexes()))

    def get_selected_columns(self) -> list[int]:
        """Get unique selected column indices."""
        return list(set(idx.column() for idx in self.selectionModel().selectedIndexes()))

    def freeze_column(self, col: int):
        """Freeze a column (make it always visible on left)."""
        self.horizontalHeader().moveSection(
            self.horizontalHeader().visualIndex(col), 0
        )
