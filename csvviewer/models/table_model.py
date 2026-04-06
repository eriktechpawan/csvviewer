"""Virtualized table model for displaying CSV data.

Performance architecture:
- The model reports the full filtered row count to Qt
- But only fetches rows in chunks from DuckDB as needed
- Uses a cache to avoid re-fetching recently viewed data
- This allows smooth scrolling through millions of rows
"""

from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex, Signal
from PySide6.QtGui import QColor, QFont
from typing import Any, Optional
from collections import OrderedDict


# Cache size: number of chunks to keep in memory
CACHE_MAX_CHUNKS = 20
CHUNK_SIZE = 1000  # Rows per chunk
NULL_DISPLAY = "∅"  # Symbol shown in cells with null values


class VirtualTableModel(QAbstractTableModel):
    """Qt table model with virtualized row loading.

    Instead of holding all data in memory, this model:
    1. Reports total filtered rows via rowCount()
    2. Fetches rows in chunks of CHUNK_SIZE from DataEngine
    3. Caches recently accessed chunks (LRU)
    4. The view only requests data for visible rows
    """

    data_changed_signal = Signal()

    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self._engine = engine
        self._row_count = 0
        self._columns: list[str] = []
        self._chunk_cache: OrderedDict[int, list[list[Any]]] = OrderedDict()
        self._row_id_map: dict[int, int] = {}  # display_row -> __row_id
        self._selected_rows: set[int] = set()  # Set of __row_id
        self._search_matches: set[tuple[int, int]] = set()  # (row, col) of search matches
        self._null_color = QColor(255, 230, 230)  # Light red for null/empty
        self._match_color = QColor(255, 255, 150)  # Yellow for search matches

    def refresh(self):
        """Refresh the model after data/filter changes."""
        self.beginResetModel()
        self._chunk_cache.clear()
        self._row_id_map.clear()
        if self._engine.is_loaded:
            self._row_count = self._engine.get_filtered_row_count()
            self._columns = self._engine.visible_columns
        else:
            self._row_count = 0
            self._columns = []
        self.endResetModel()
        self.data_changed_signal.emit()

    def rowCount(self, parent=QModelIndex()):
        """Return the total number of filtered rows."""
        if parent.isValid():
            return 0
        return self._row_count

    def columnCount(self, parent=QModelIndex()):
        """Return the number of visible columns."""
        if parent.isValid():
            return 0
        return len(self._columns)

    def _get_chunk_index(self, row: int) -> int:
        """Return the chunk index that contains the given display row."""
        return row // CHUNK_SIZE

    def _ensure_chunk_loaded(self, chunk_idx: int):
        """Load a chunk from the engine if not already cached.

        Uses LRU eviction: the least-recently-used chunk is dropped
        when the cache exceeds CACHE_MAX_CHUNKS entries.
        """
        if chunk_idx in self._chunk_cache:
            # Move to end (most recently used)
            self._chunk_cache.move_to_end(chunk_idx)
            return

        offset = chunk_idx * CHUNK_SIZE
        rows = self._engine.fetch_rows(offset, CHUNK_SIZE)

        # Store in cache
        self._chunk_cache[chunk_idx] = rows

        # Update row_id map — __row_id is the first element of each row
        for i, row in enumerate(rows):
            display_row = offset + i
            self._row_id_map[display_row] = row[0]

        # Evict oldest chunks if cache is full
        while len(self._chunk_cache) > CACHE_MAX_CHUNKS:
            oldest_key, _ = self._chunk_cache.popitem(last=False)
            # Clean up row_id_map for evicted chunk
            evict_start = oldest_key * CHUNK_SIZE
            for j in range(CHUNK_SIZE):
                self._row_id_map.pop(evict_start + j, None)

    def _get_row_data(self, row: int) -> Optional[list]:
        """Get the raw data list for a specific display row.

        Returns None if the row is out of range for the loaded chunk.
        """
        chunk_idx = self._get_chunk_index(row)
        self._ensure_chunk_loaded(chunk_idx)

        chunk = self._chunk_cache.get(chunk_idx)
        if chunk is None:
            return None

        row_in_chunk = row % CHUNK_SIZE
        if row_in_chunk >= len(chunk):
            return None

        return chunk[row_in_chunk]

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        """Return data for the given index and role.

        Handles:
        - DisplayRole: string value (∅ for nulls)
        - EditRole: string value (empty string for nulls)
        - BackgroundRole: highlight nulls and search matches
        - FontRole: italic for null values
        - TextAlignmentRole: right-align numeric columns
        """
        if not index.isValid():
            return None

        row = index.row()
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole or role == Qt.ItemDataRole.EditRole:
            row_data = self._get_row_data(row)
            if row_data is None:
                return None
            # +1 because first element is __row_id
            if col + 1 >= len(row_data):
                return None
            value = row_data[col + 1]
            if value is None:
                return "" if role == Qt.ItemDataRole.EditRole else NULL_DISPLAY
            return str(value)

        elif role == Qt.ItemDataRole.BackgroundRole:
            # Highlight null/empty cells
            row_data = self._get_row_data(row)
            if row_data and col + 1 < len(row_data):
                if row_data[col + 1] is None:
                    return self._null_color
            # Highlight search matches
            if (row, col) in self._search_matches:
                return self._match_color
            return None

        elif role == Qt.ItemDataRole.FontRole:
            row_data = self._get_row_data(row)
            if row_data and col + 1 < len(row_data) and row_data[col + 1] is None:
                font = QFont()
                font.setItalic(True)
                return font
            return None

        elif role == Qt.ItemDataRole.TextAlignmentRole:
            # Right-align numeric columns
            if col < len(self._columns):
                from csvviewer.utils.constants import ColumnType

                col_type = self._engine.get_column_type(self._columns[col])
                if col_type in (ColumnType.INTEGER, ColumnType.FLOAT):
                    return int(
                        Qt.AlignmentFlag.AlignRight
                        | Qt.AlignmentFlag.AlignVCenter
                    )
            return int(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            )

        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        """Return header labels.

        Horizontal headers show column names; vertical headers show
        1-based row numbers.
        """
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:
                if 0 <= section < len(self._columns):
                    return self._columns[section]
            elif orientation == Qt.Orientation.Vertical:
                return str(section + 1)  # 1-based row numbers
        return None

    def flags(self, index: QModelIndex):
        """Return item flags — editable when not in read-only mode."""
        flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        if not self._engine.read_only:
            flags |= Qt.ItemFlag.ItemIsEditable
        return flags

    def setData(self, index: QModelIndex, value, role=Qt.ItemDataRole.EditRole):
        """Handle cell edits. Returns True if the update succeeded."""
        if role != Qt.ItemDataRole.EditRole:
            return False
        if self._engine.read_only:
            return False

        row = index.row()
        col = index.column()

        row_id = self.get_row_id(row)
        if row_id is None:
            return False

        col_name = self._columns[col]

        # Convert empty string to None
        if value == "" or value == NULL_DISPLAY:
            value = None

        self._engine.update_cell(row_id, col_name, value)

        # Invalidate cache for this chunk
        chunk_idx = self._get_chunk_index(row)
        self._chunk_cache.pop(chunk_idx, None)

        self.dataChanged.emit(index, index)
        return True

    def get_row_id(self, display_row: int) -> Optional[int]:
        """Get the __row_id for a display row, loading the chunk if needed."""
        self._ensure_chunk_loaded(self._get_chunk_index(display_row))
        return self._row_id_map.get(display_row)

    def get_column_name(self, col_index: int) -> Optional[str]:
        """Return the column name for a given column index."""
        if 0 <= col_index < len(self._columns):
            return self._columns[col_index]
        return None

    def set_search_matches(self, matches: set[tuple[int, int]]):
        """Set search match highlights and notify the view."""
        self._search_matches = matches
        # Emit dataChanged for the whole model
        if self._row_count > 0 and len(self._columns) > 0:
            top = self.index(0, 0)
            bottom = self.index(self._row_count - 1, len(self._columns) - 1)
            self.dataChanged.emit(top, bottom)

    def clear_search_matches(self):
        """Remove all search match highlights."""
        self.set_search_matches(set())

    @property
    def selected_row_ids(self) -> set[int]:
        """Return the set of currently selected __row_id values."""
        return self._selected_rows

    def set_selected_rows(self, row_ids: set[int]):
        """Update the set of selected row IDs."""
        self._selected_rows = row_ids

    def invalidate_cache(self):
        """Clear all cached chunk data and row ID mappings."""
        self._chunk_cache.clear()
        self._row_id_map.clear()
