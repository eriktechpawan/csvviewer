"""DuckDB-based data engine for efficient CSV data operations.

Architecture:
- CSV data is loaded into a DuckDB in-memory table
- All queries (filter, sort, fetch rows) use SQL
- Only the visible slice of rows is ever returned to the UI
- Edits are applied to the DuckDB table directly
- A hidden __row_id column tracks original row order
"""

import duckdb
import os
import re
from typing import Optional, Any

from csvviewer.utils.constants import ColumnType


class DataEngine:
    """DuckDB-backed engine for efficient CSV data operations.

    Designed to handle very large files (millions of rows) without
    loading the entire dataset into memory for display. All filtering,
    sorting, statistics, and data retrieval happen via SQL queries that
    return only the needed slice.
    """

    TABLE_NAME = "csv_data"

    def __init__(self):
        """Initialize the DataEngine with default state."""
        self._conn: Optional[duckdb.DuckDBPyConnection] = None
        self._file_path: Optional[str] = None
        self._file_size: int = 0
        self._columns: list[str] = []
        self._column_types: dict[str, ColumnType] = {}
        self._total_rows: int = 0
        self._filters: list[dict] = []
        self._sort_columns: list[tuple[str, str]] = []
        self._hidden_columns: set[str] = set()
        self._column_order: list[str] = []
        self._read_only: bool = False
        self._next_row_id: int = 0
        self._filter_logic: str = "AND"  # "AND" or "OR"

    def connect(self):
        """Initialize a fresh DuckDB in-memory connection."""
        if self._conn:
            self._conn.close()
        self._conn = duckdb.connect(":memory:")

    def close(self):
        """Close the DuckDB connection and release resources."""
        if self._conn:
            self._conn.close()
            self._conn = None

    def load_csv(
        self,
        file_path: str,
        delimiter: str = ",",
        encoding: str = "utf-8",
        has_header: bool = True,
        quote_char: str = '"',
        skip_rows: int = 0,
        progress_callback=None,
    ) -> dict:
        """Load a CSV file into DuckDB.

        Returns a dict with keys: columns, types, total_rows, file_size,
        file_path, warnings.

        Performance note: DuckDB's ``read_csv`` is highly optimised and
        uses parallel reading internally.  For files with millions of rows
        this is significantly faster than pandas or manual parsing.
        """
        self.connect()
        self._file_path = file_path
        self._file_size = os.path.getsize(file_path)

        # Reset per-file state so stale filters/sorts from a previous
        # file don't persist
        self._filters.clear()
        self._sort_columns.clear()
        self._hidden_columns.clear()
        self._column_types.clear()
        self._filter_logic = "AND"

        if progress_callback:
            progress_callback(10)

        options: dict[str, Any] = {
            "header": has_header,
            "delim": delimiter,
            "quote": quote_char,
            "auto_detect": True,
            "ignore_errors": True,
            "skip": skip_rows,
            "encoding": encoding,
        }

        opt_parts: list[str] = []
        for k, v in options.items():
            if isinstance(v, bool):
                opt_parts.append(f"{k}={str(v).lower()}")
            elif isinstance(v, int):
                opt_parts.append(f"{k}={v}")
            elif isinstance(v, str):
                opt_parts.append(f"{k}='{v}'")

        opt_str = ", ".join(opt_parts)

        escaped_path = file_path.replace("'", "''")
        query = (
            f"CREATE TABLE {self.TABLE_NAME} AS "
            f"SELECT row_number() OVER () - 1 AS __row_id, * "
            f"FROM read_csv('{escaped_path}', {opt_str})"
        )

        try:
            self._conn.execute(query)
        except Exception:
            # Fallback: try with more permissive settings
            self._conn.execute(
                f"CREATE TABLE {self.TABLE_NAME} AS "
                f"SELECT row_number() OVER () - 1 AS __row_id, * "
                f"FROM read_csv('{escaped_path}', "
                f"header={str(has_header).lower()}, "
                f"delim='{delimiter}', "
                f"auto_detect=true, "
                f"ignore_errors=true)"
            )

        if progress_callback:
            progress_callback(60)

        # Retrieve column metadata (excluding __row_id)
        col_info = self._conn.execute(
            f"SELECT column_name, data_type "
            f"FROM information_schema.columns "
            f"WHERE table_name = '{self.TABLE_NAME}' "
            f"AND column_name != '__row_id' "
            f"ORDER BY ordinal_position"
        ).fetchall()

        self._columns = [c[0] for c in col_info]
        self._column_order = list(self._columns)

        for col_name, dtype in col_info:
            self._column_types[col_name] = self._map_duckdb_type(dtype)

        self._total_rows = self._conn.execute(
            f"SELECT COUNT(*) FROM {self.TABLE_NAME}"
        ).fetchone()[0]

        self._next_row_id = self._total_rows

        if progress_callback:
            progress_callback(100)

        warnings: list[str] = []

        return {
            "columns": self._columns,
            "types": dict(self._column_types),
            "total_rows": self._total_rows,
            "file_size": self._file_size,
            "file_path": file_path,
            "warnings": warnings,
        }

    # ------------------------------------------------------------------
    # Type helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _map_duckdb_type(dtype: str) -> ColumnType:
        """Map a DuckDB data type string to the application ColumnType enum."""
        dtype_upper = dtype.upper()
        if any(
            t in dtype_upper
            for t in ("INT", "BIGINT", "SMALLINT", "TINYINT", "HUGEINT")
        ):
            return ColumnType.INTEGER
        if any(
            t in dtype_upper
            for t in ("FLOAT", "DOUBLE", "DECIMAL", "NUMERIC", "REAL")
        ):
            return ColumnType.FLOAT
        if "BOOL" in dtype_upper:
            return ColumnType.BOOLEAN
        if any(t in dtype_upper for t in ("DATE", "TIME", "TIMESTAMP")):
            return ColumnType.DATETIME
        return ColumnType.TEXT

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def columns(self) -> list[str]:
        """All columns in current order."""
        return list(self._column_order)

    @property
    def visible_columns(self) -> list[str]:
        """Columns that are not hidden, in current order."""
        return [c for c in self._column_order if c not in self._hidden_columns]

    @property
    def total_rows(self) -> int:
        """Total (unfiltered) row count."""
        return self._total_rows

    @property
    def file_path(self) -> Optional[str]:
        """Path of the currently loaded CSV file."""
        return self._file_path

    @property
    def file_size(self) -> int:
        """Size in bytes of the loaded file."""
        return self._file_size

    @property
    def is_loaded(self) -> bool:
        """Whether data has been loaded successfully."""
        return self._conn is not None and self._file_path is not None

    @property
    def read_only(self) -> bool:
        """Whether the data is in read-only mode."""
        return self._read_only

    @read_only.setter
    def read_only(self, value: bool):
        self._read_only = value

    # ------------------------------------------------------------------
    # SQL clause builders
    # ------------------------------------------------------------------

    def _validate_column(self, col: str) -> bool:
        """Validate that a column name exists in the loaded schema."""
        return col in self._columns

    def _safe_identifier(self, name: str) -> str:
        """Escape a SQL identifier to prevent injection."""
        return '"' + name.replace('"', '""') + '"'

    def _build_where_clause(self) -> str:
        """Build a SQL WHERE clause from the currently active filters.

        Column names are validated against the loaded schema to prevent
        SQL injection from user-controlled session data.
        """
        if not self._filters:
            return ""

        clauses: list[str] = []
        for f in self._filters:
            col = f["column"]
            if not self._validate_column(col):
                continue  # Skip filters referencing unknown columns
            op = f["operator"]
            value = f.get("value")
            value2 = f.get("value2")
            case_sensitive = f.get("case_sensitive", True)

            safe_col = self._safe_identifier(col)
            qcol = safe_col
            if not case_sensitive:
                qcol = f'LOWER(CAST({safe_col} AS VARCHAR))'
                if isinstance(value, str):
                    value = value.lower()

            clause = self._filter_to_sql(qcol, op, value, value2, col)
            if clause:
                clauses.append(clause)

        if not clauses:
            return ""

        # Use per-filter connector if available, falling back to global logic
        logic = getattr(self, '_filter_logic', 'AND')

        # If filters carry per-filter connector info, use it
        connectors = []
        for f in self._filters:
            connectors.append(f.get("connector", logic))

        # Build expression: first clause has no preceding connector
        parts = [clauses[0]]
        for i in range(1, len(clauses)):
            conn = connectors[i] if i < len(connectors) else logic
            if conn not in ("AND", "OR"):
                conn = logic
            parts.append(f" {conn} ")
            parts.append(clauses[i])

        return "WHERE " + "".join(parts)

    @staticmethod
    def _sql_escape(v: str) -> str:
        """Escape a string value for safe inclusion in SQL literals."""
        return v.replace("'", "''")

    def _filter_to_sql(
        self, qcol: str, op: str, value: Any, value2: Any, raw_col: str
    ) -> str:
        """Convert a single filter specification to a SQL clause."""
        safe_raw = self._safe_identifier(raw_col)

        def sql_val(v: Any) -> str:
            if v is None:
                return "NULL"
            if isinstance(v, (int, float)):
                return str(v)
            return f"'{DataEngine._sql_escape(str(v))}'"

        # --- Value filters ---
        if op == "EQUALS":
            return f"{qcol} = {sql_val(value)}"
        if op == "NOT_EQUALS":
            return f"{qcol} != {sql_val(value)}"
        if op == "IN_LIST":
            vals = ", ".join(sql_val(v) for v in value)
            return f"{qcol} IN ({vals})"
        if op == "NOT_IN_LIST":
            vals = ", ".join(sql_val(v) for v in value)
            return f"{qcol} NOT IN ({vals})"
        if op == "IS_EMPTY":
            return (
                f'(CAST({safe_raw} AS VARCHAR) = \'\' '
                f'OR {safe_raw} IS NULL)'
            )
        if op == "NOT_EMPTY":
            return (
                f'(CAST({safe_raw} AS VARCHAR) != \'\' '
                f'AND {safe_raw} IS NOT NULL)'
            )
        if op == "IS_NULL":
            return f'{safe_raw} IS NULL'
        if op == "NOT_NULL":
            return f'{safe_raw} IS NOT NULL'

        # --- Numeric filters ---
        if op == "GT":
            return f"{qcol} > {sql_val(value)}"
        if op == "GTE":
            return f"{qcol} >= {sql_val(value)}"
        if op == "LT":
            return f"{qcol} < {sql_val(value)}"
        if op == "LTE":
            return f"{qcol} <= {sql_val(value)}"
        if op == "BETWEEN":
            return f"{qcol} BETWEEN {sql_val(value)} AND {sql_val(value2)}"
        if op == "OUTSIDE_RANGE":
            return f"({qcol} < {sql_val(value)} OR {qcol} > {sql_val(value2)})"
        if op == "IS_ZERO":
            return f"{qcol} = 0"
        if op == "NON_ZERO":
            return f"{qcol} != 0"
        if op == "POSITIVE":
            return f"{qcol} > 0"
        if op == "NEGATIVE":
            return f"{qcol} < 0"

        # --- Text filters ---
        if op == "CONTAINS":
            return (
                f"{qcol} LIKE '%{DataEngine._sql_escape(str(value))}%'"
            )
        if op == "NOT_CONTAINS":
            return (
                f"{qcol} NOT LIKE '%{DataEngine._sql_escape(str(value))}%'"
            )
        if op == "STARTS_WITH":
            return f"{qcol} LIKE '{DataEngine._sql_escape(str(value))}%'"
        if op == "ENDS_WITH":
            return f"{qcol} LIKE '%{DataEngine._sql_escape(str(value))}'"
        if op == "EXACT_MATCH":
            return f"{qcol} = {sql_val(value)}"
        if op == "REGEX":
            return (
                f"regexp_matches(CAST(\"{raw_col}\" AS VARCHAR), "
                f"'{DataEngine._sql_escape(str(value))}')"
            )

        return ""

    def _build_order_clause(self) -> str:
        """Build a SQL ORDER BY clause from the current sort specification.

        Column names are validated against the schema.
        """
        if not self._sort_columns:
            return "ORDER BY __row_id"
        parts = []
        for col, direction in self._sort_columns:
            if not self._validate_column(col):
                continue
            safe_dir = "ASC" if direction.upper() == "ASC" else "DESC"
            parts.append(f'{self._safe_identifier(col)} {safe_dir}')
        if not parts:
            return "ORDER BY __row_id"
        return "ORDER BY " + ", ".join(parts)

    # ------------------------------------------------------------------
    # Querying
    # ------------------------------------------------------------------

    def get_filtered_row_count(self) -> int:
        """Return the number of rows matching the current filters."""
        where = self._build_where_clause()
        result = self._conn.execute(
            f"SELECT COUNT(*) FROM {self.TABLE_NAME} {where}"
        ).fetchone()
        return result[0]

    def fetch_rows(self, offset: int, limit: int) -> list[list]:
        """Fetch a slice of rows for display.

        This is the core virtualisation query.  Only *limit* rows at the
        given *offset* are retrieved.  The UI calls this method as the
        user scrolls through the table.
        """
        cols = ", ".join(self._safe_identifier(c) for c in self.visible_columns)
        if not cols:
            # All columns hidden — return only row IDs
            cols = "1"
        where = self._build_where_clause()
        order = self._build_order_clause()

        query = (
            f"SELECT __row_id, {cols} "
            f"FROM {self.TABLE_NAME} "
            f"{where} {order} "
            f"LIMIT {int(limit)} OFFSET {int(offset)}"
        )

        result = self._conn.execute(query).fetchall()
        return [list(row) for row in result]

    def fetch_all_row_ids(self) -> list[int]:
        """Return all ``__row_id`` values matching the current filters.

        Useful for selection tracking when the user selects "all rows".
        """
        where = self._build_where_clause()
        order = self._build_order_clause()
        result = self._conn.execute(
            f"SELECT __row_id FROM {self.TABLE_NAME} {where} {order}"
        ).fetchall()
        return [r[0] for r in result]

    # ------------------------------------------------------------------
    # Filters
    # ------------------------------------------------------------------

    def set_filters(self, filters: list[dict], logic: str = "AND"):
        """Set the active filters, replacing any existing ones.

        Each filter dict must contain at minimum *column* and *operator*
        keys.  Optional keys: *value*, *value2*, *case_sensitive*.
        *logic* controls combination: ``"AND"`` or ``"OR"``.
        """
        self._filters = list(filters)
        self._filter_logic = logic if logic in ("AND", "OR") else "AND"

    def add_filter(
        self,
        column: str,
        operator: str,
        value: Any = None,
        value2: Any = None,
        case_sensitive: bool = True,
    ):
        """Append a single filter to the active filter list."""
        self._filters.append(
            {
                "column": column,
                "operator": operator,
                "value": value,
                "value2": value2,
                "case_sensitive": case_sensitive,
            }
        )

    def clear_filters(self):
        """Remove all active filters."""
        self._filters.clear()

    def get_filters(self) -> list[dict]:
        """Return a copy of the current filter list."""
        return list(self._filters)

    # ------------------------------------------------------------------
    # Sorting
    # ------------------------------------------------------------------

    def set_sort(self, columns: list[tuple[str, str]]):
        """Set sort columns.  Each tuple is ``(column_name, 'ASC'|'DESC')``."""
        self._sort_columns = list(columns)

    def clear_sort(self):
        """Remove all sort specifications, reverting to original row order."""
        self._sort_columns.clear()

    def get_sort(self) -> list[tuple[str, str]]:
        """Return a copy of the current sort specification."""
        return list(self._sort_columns)

    # ------------------------------------------------------------------
    # Column visibility
    # ------------------------------------------------------------------

    def hide_column(self, column: str):
        """Hide *column* from the visible column list."""
        self._hidden_columns.add(column)

    def show_column(self, column: str):
        """Un-hide *column*, making it visible again."""
        self._hidden_columns.discard(column)

    def set_hidden_columns(self, columns: set[str]):
        """Replace the set of hidden columns."""
        self._hidden_columns = set(columns)

    def get_hidden_columns(self) -> set[str]:
        """Return a copy of the hidden-columns set."""
        return set(self._hidden_columns)

    # ------------------------------------------------------------------
    # Column ordering
    # ------------------------------------------------------------------

    def reorder_columns(self, new_order: list[str]):
        """Set a custom column display order."""
        self._column_order = list(new_order)

    # ------------------------------------------------------------------
    # Column statistics
    # ------------------------------------------------------------------

    def get_column_stats(self, column: str) -> dict:
        """Compute statistics for *column* against the currently filtered data.

        Returns a dict containing counts, numeric aggregates (when
        applicable), and the top-10 most frequent values.
        """
        where = self._build_where_clause()
        col = self._safe_identifier(column)
        col_type = self._column_types.get(column, ColumnType.TEXT)

        stats: dict[str, Any] = {
            "column_name": column,
            "detected_type": col_type.value,
            "total_rows": self.get_filtered_row_count(),
        }

        # Non-null, null, unique counts
        result = self._conn.execute(
            f"SELECT "
            f"COUNT(*) AS total, "
            f"COUNT({col}) AS non_null, "
            f"COUNT(*) - COUNT({col}) AS null_count, "
            f"COUNT(DISTINCT {col}) AS unique_count "
            f"FROM {self.TABLE_NAME} {where}"
        ).fetchone()

        stats["non_null_count"] = result[1]
        stats["null_count"] = result[2]
        stats["unique_count"] = result[3]

        # Numeric aggregates
        if col_type in (ColumnType.INTEGER, ColumnType.FLOAT):
            try:
                num_result = self._conn.execute(
                    f"SELECT MIN({col}), MAX({col}), SUM({col}), AVG({col}) "
                    f"FROM {self.TABLE_NAME} {where}"
                ).fetchone()
                stats["min"] = num_result[0]
                stats["max"] = num_result[1]
                stats["sum"] = num_result[2]
                stats["average"] = num_result[3]
            except Exception:
                pass
        else:
            try:
                mm = self._conn.execute(
                    f"SELECT MIN({col}), MAX({col}) FROM {self.TABLE_NAME} {where}"
                ).fetchone()
                stats["min"] = mm[0]
                stats["max"] = mm[1]
            except Exception:
                pass

        # Top-10 most frequent values
        try:
            null_filter = f"AND {col} IS NOT NULL" if where else f"WHERE {col} IS NOT NULL"
            top = self._conn.execute(
                f"SELECT CAST({col} AS VARCHAR) AS val, COUNT(*) AS cnt "
                f"FROM {self.TABLE_NAME} {where} {null_filter} "
                f"GROUP BY {col} ORDER BY cnt DESC LIMIT 10"
            ).fetchall()
            stats["top_values"] = [(str(r[0]), r[1]) for r in top]
        except Exception:
            stats["top_values"] = []

        return stats

    def get_column_sum(self, column: str) -> Optional[float]:
        """Return the sum of a numeric *column* on the filtered data."""
        where = self._build_where_clause()
        try:
            result = self._conn.execute(
                f'SELECT SUM("{column}") FROM {self.TABLE_NAME} {where}'
            ).fetchone()
            return result[0]
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Editing
    # ------------------------------------------------------------------

    def update_cell(self, row_id: int, column: str, value: Any) -> dict:
        """Update a single cell identified by *row_id* and *column*.

        Returns a dict with ``old_value``, ``new_value``, ``row_id``, and
        ``column`` (useful for building undo records).
        """
        old = self._conn.execute(
            f'SELECT "{column}" FROM {self.TABLE_NAME} WHERE __row_id = $1',
            [row_id],
        ).fetchone()
        old_value = old[0] if old else None

        if value is None:
            self._conn.execute(
                f'UPDATE {self.TABLE_NAME} SET "{column}" = NULL WHERE __row_id = $1',
                [row_id],
            )
        else:
            self._conn.execute(
                f'UPDATE {self.TABLE_NAME} SET "{column}" = $1 WHERE __row_id = $2',
                [value, row_id],
            )

        return {
            "old_value": old_value,
            "new_value": value,
            "row_id": row_id,
            "column": column,
        }

    def add_row(self, values: Optional[dict] = None) -> int:
        """Add a new row, optionally populated with *values*.

        Returns the ``__row_id`` assigned to the new row.
        """
        new_id = self._next_row_id
        self._next_row_id += 1

        if values:
            cols = ["__row_id"] + [self._safe_identifier(c) for c in values.keys()]
            placeholders = ", ".join(
                ["$" + str(i + 1) for i in range(len(values) + 1)]
            )
            params = [new_id] + list(values.values())
            col_str = ", ".join(cols)
            self._conn.execute(
                f"INSERT INTO {self.TABLE_NAME} ({col_str}) VALUES ({placeholders})",
                params,
            )
        else:
            self._conn.execute(
                f"INSERT INTO {self.TABLE_NAME} (__row_id) VALUES ($1)",
                [new_id],
            )

        self._total_rows += 1
        return new_id

    def delete_rows(self, row_ids: list[int]) -> list[dict]:
        """Delete rows by ``__row_id``.

        Returns a list of dicts containing the deleted row data so that
        the operation can be undone.
        """
        if not row_ids:
            return []

        id_placeholders = ", ".join(["$" + str(i + 1) for i in range(len(row_ids))])
        cols = ", ".join(self._safe_identifier(c) for c in self._columns)

        # Fetch data for undo before deleting
        rows = self._conn.execute(
            f"SELECT __row_id, {cols} FROM {self.TABLE_NAME} "
            f"WHERE __row_id IN ({id_placeholders})",
            row_ids,
        ).fetchall()

        deleted_data: list[dict] = []
        for row in rows:
            row_dict: dict[str, Any] = {"__row_id": row[0]}
            for i, col in enumerate(self._columns):
                row_dict[col] = row[i + 1]
            deleted_data.append(row_dict)

        self._conn.execute(
            f"DELETE FROM {self.TABLE_NAME} WHERE __row_id IN ({id_placeholders})",
            row_ids,
        )

        self._total_rows -= len(deleted_data)
        return deleted_data

    def restore_rows(self, rows_data: list[dict]):
        """Restore previously deleted rows (undo support)."""
        for row_dict in rows_data:
            cols = list(row_dict.keys())
            col_str = ", ".join(
                self._safe_identifier(c) if c != "__row_id" else c for c in cols
            )
            placeholders = ", ".join(
                ["$" + str(i + 1) for i in range(len(cols))]
            )
            self._conn.execute(
                f"INSERT INTO {self.TABLE_NAME} ({col_str}) VALUES ({placeholders})",
                list(row_dict.values()),
            )
        self._total_rows += len(rows_data)

    def duplicate_rows(self, row_ids: list[int]) -> list[int]:
        """Duplicate the specified rows.  Returns the new ``__row_id`` values."""
        new_ids: list[int] = []
        cols = ", ".join(self._safe_identifier(c) for c in self._columns)

        for rid in row_ids:
            row = self._conn.execute(
                f"SELECT {cols} FROM {self.TABLE_NAME} WHERE __row_id = $1",
                [rid],
            ).fetchone()
            if row:
                new_id = self._next_row_id
                self._next_row_id += 1
                all_cols = "__row_id, " + cols
                placeholders = ", ".join(
                    ["$" + str(i + 1) for i in range(len(self._columns) + 1)]
                )
                self._conn.execute(
                    f"INSERT INTO {self.TABLE_NAME} ({all_cols}) VALUES ({placeholders})",
                    [new_id] + list(row),
                )
                new_ids.append(new_id)
                self._total_rows += 1

        return new_ids

    def add_column(self, name: str, default_value: Any = None) -> bool:
        """Add a new VARCHAR column with an optional default value."""
        try:
            self._conn.execute(
                f'ALTER TABLE {self.TABLE_NAME} ADD COLUMN "{name}" VARCHAR'
            )
            if default_value is not None:
                self._conn.execute(
                    f'UPDATE {self.TABLE_NAME} SET "{name}" = $1',
                    [str(default_value)],
                )
            self._columns.append(name)
            self._column_order.append(name)
            self._column_types[name] = ColumnType.TEXT
            return True
        except Exception:
            return False

    def delete_column(self, name: str) -> dict:
        """Delete a column.  Returns column metadata and data for undo."""
        # Fetch column data before dropping
        col_data = self._conn.execute(
            f'SELECT __row_id, "{name}" FROM {self.TABLE_NAME}'
        ).fetchall()

        col_type = self._column_types.get(name, ColumnType.TEXT)
        col_idx = (
            self._column_order.index(name) if name in self._column_order else -1
        )

        self._conn.execute(
            f'ALTER TABLE {self.TABLE_NAME} DROP COLUMN "{name}"'
        )

        self._columns.remove(name)
        if name in self._column_order:
            self._column_order.remove(name)
        self._column_types.pop(name, None)
        self._hidden_columns.discard(name)

        return {
            "name": name,
            "type": col_type,
            "index": col_idx,
            "data": col_data,
        }

    def rename_column(self, old_name: str, new_name: str) -> bool:
        """Rename a column from *old_name* to *new_name*."""
        try:
            self._conn.execute(
                f'ALTER TABLE {self.TABLE_NAME} '
                f'RENAME COLUMN "{old_name}" TO "{new_name}"'
            )
            idx = self._columns.index(old_name)
            self._columns[idx] = new_name
            if old_name in self._column_order:
                oidx = self._column_order.index(old_name)
                self._column_order[oidx] = new_name
            if old_name in self._column_types:
                self._column_types[new_name] = self._column_types.pop(old_name)
            if old_name in self._hidden_columns:
                self._hidden_columns.discard(old_name)
                self._hidden_columns.add(new_name)
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Data cleanup
    # ------------------------------------------------------------------

    def remove_duplicates(self) -> int:
        """Remove duplicate rows (keeping the one with the lowest ``__row_id``).

        Returns the number of rows removed.
        """
        cols = ", ".join(self._safe_identifier(c) for c in self._columns)
        before = self._total_rows

        self._conn.execute(
            f"CREATE TABLE _temp_dedup AS "
            f"SELECT * FROM ("
            f"  SELECT *, ROW_NUMBER() OVER (PARTITION BY {cols} ORDER BY __row_id) AS _rn "
            f"  FROM {self.TABLE_NAME}"
            f") WHERE _rn = 1"
        )
        self._conn.execute(f"DROP TABLE {self.TABLE_NAME}")
        self._conn.execute(
            f"ALTER TABLE _temp_dedup RENAME TO {self.TABLE_NAME}"
        )
        try:
            self._conn.execute(
                f"ALTER TABLE {self.TABLE_NAME} DROP COLUMN _rn"
            )
        except Exception:
            pass

        self._total_rows = self._conn.execute(
            f"SELECT COUNT(*) FROM {self.TABLE_NAME}"
        ).fetchone()[0]

        return before - self._total_rows

    def trim_whitespace(self, column: str) -> int:
        """Trim leading/trailing whitespace in *column*.

        Returns the number of rows affected.
        """
        safe_col = self._safe_identifier(column)
        result = self._conn.execute(
            f"SELECT COUNT(*) FROM {self.TABLE_NAME} "
            f'WHERE CAST({safe_col} AS VARCHAR) != TRIM(CAST({safe_col} AS VARCHAR))'
        ).fetchone()
        affected = result[0]

        if affected > 0:
            self._conn.execute(
                f'UPDATE {self.TABLE_NAME} '
                f'SET {safe_col} = TRIM(CAST({safe_col} AS VARCHAR))'
            )

        return affected

    def find_replace(
        self,
        column: str,
        find: str,
        replace: str,
        case_sensitive: bool = True,
    ) -> int:
        """Find and replace text in *column*.

        Returns the number of rows that contained at least one match.
        """
        safe_col = self._safe_identifier(column)
        escaped_find = self._sql_escape(find)
        escaped_replace = self._sql_escape(replace)

        if case_sensitive:
            count = self._conn.execute(
                f"SELECT COUNT(*) FROM {self.TABLE_NAME} "
                f"WHERE CAST({safe_col} AS VARCHAR) LIKE '%{escaped_find}%'"
            ).fetchone()[0]

            self._conn.execute(
                f'UPDATE {self.TABLE_NAME} '
                f'SET {safe_col} = REPLACE(CAST({safe_col} AS VARCHAR), '
                f"'{escaped_find}', '{escaped_replace}')"
            )
        else:
            count = self._conn.execute(
                f"SELECT COUNT(*) FROM {self.TABLE_NAME} "
                f"WHERE LOWER(CAST({safe_col} AS VARCHAR)) "
                f"LIKE '%{escaped_find.lower()}%'"
            ).fetchone()[0]

            # Escape regex metacharacters so the find string is treated
            # literally in the regexp_replace call.
            regex_escaped_find = self._sql_escape(re.escape(find))

            self._conn.execute(
                f'UPDATE {self.TABLE_NAME} '
                f'SET {safe_col} = regexp_replace(CAST({safe_col} AS VARCHAR), '
                f"'(?i){regex_escaped_find}', '{escaped_replace}', 'g')"
            )

        return count

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        column: Optional[str] = None,
        case_sensitive: bool = False,
    ) -> list[tuple[int, str, Any]]:
        """Search for *query* text across visible columns.

        Returns a list of ``(row_id, column_name, cell_value)`` tuples.
        Results are capped at 1000 matches for performance.
        """
        where = self._build_where_clause()
        results: list[tuple[int, str, Any]] = []
        escaped_query = self._sql_escape(query)

        search_cols = [column] if column else self.visible_columns

        for col in search_cols:
            if case_sensitive:
                cond = (
                    f"CAST(\"{col}\" AS VARCHAR) LIKE '%{escaped_query}%'"
                )
            else:
                cond = (
                    f"LOWER(CAST(\"{col}\" AS VARCHAR)) "
                    f"LIKE '%{escaped_query.lower()}%'"
                )

            if where:
                full_where = f"{where} AND {cond}"
            else:
                full_where = f"WHERE {cond}"

            rows = self._conn.execute(
                f'SELECT __row_id, "{col}" '
                f"FROM {self.TABLE_NAME} {full_where} "
                f"LIMIT 1000"
            ).fetchall()

            for row in rows:
                results.append((row[0], col, row[1]))

            if len(results) >= 1000:
                break

        return results[:1000]

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def export_csv(
        self,
        output_path: str,
        delimiter: str = ",",
        encoding: str = "utf-8",
        selected_row_ids: Optional[list[int]] = None,
        columns: Optional[list[str]] = None,
        progress_callback=None,
    ) -> int:
        """Export data to a CSV file.

        Uses DuckDB's ``COPY`` for maximum export speed on large datasets.
        Returns the number of rows exported.
        """
        cols = columns or self.visible_columns
        col_str = ", ".join(self._safe_identifier(c) for c in cols)

        where = self._build_where_clause()

        if selected_row_ids:
            # Use a temporary table for large ID sets to avoid SQL length limits
            self._conn.execute(
                "CREATE TEMPORARY TABLE IF NOT EXISTS _export_ids "
                "(id BIGINT)"
            )
            self._conn.execute("DELETE FROM _export_ids")
            # Insert IDs in batches
            batch_size = 1000
            for i in range(0, len(selected_row_ids), batch_size):
                batch = selected_row_ids[i:i + batch_size]
                values = ", ".join(f"({int(r)})" for r in batch)
                self._conn.execute(
                    f"INSERT INTO _export_ids VALUES {values}"
                )
            extra = f"__row_id IN (SELECT id FROM _export_ids)"
            if where:
                where += f" AND {extra}"
            else:
                where = f"WHERE {extra}"

        order = self._build_order_clause()

        if progress_callback:
            progress_callback(10)

        inner_query = (
            f"SELECT {col_str} FROM {self.TABLE_NAME} {where} {order}"
        )
        escaped_output = output_path.replace("'", "''")
        self._conn.execute(
            f"COPY ({inner_query}) TO '{escaped_output}' "
            f"(HEADER, DELIM '{delimiter}')"
        )

        if progress_callback:
            progress_callback(90)

        count = self._conn.execute(
            f"SELECT COUNT(*) FROM {self.TABLE_NAME} {where}"
        ).fetchone()[0]

        if progress_callback:
            progress_callback(100)

        return count

    # ------------------------------------------------------------------
    # Type overrides
    # ------------------------------------------------------------------

    def override_column_type(self, column: str, new_type: ColumnType) -> bool:
        """Override the detected type of *column* (affects filtering/stats)."""
        self._column_types[column] = new_type
        return True

    def get_column_type(self, column: str) -> ColumnType:
        """Return the current ``ColumnType`` for *column*."""
        return self._column_types.get(column, ColumnType.TEXT)

    # ------------------------------------------------------------------
    # Preview (lightweight, no full load)
    # ------------------------------------------------------------------

    def preview_csv(
        self,
        file_path: str,
        delimiter: str = ",",
        has_header: bool = True,
        max_rows: int = 100,
    ) -> dict:
        """Preview a CSV file without fully loading it into the engine.

        Returns a dict with ``columns``, ``rows``, and ``row_count``.
        """
        conn = duckdb.connect(":memory:")
        escaped_path = file_path.replace("'", "''")
        try:
            result = conn.execute(
                f"SELECT * FROM read_csv('{escaped_path}', "
                f"header={str(has_header).lower()}, "
                f"delim='{delimiter}', "
                f"auto_detect=true, "
                f"ignore_errors=true) "
                f"LIMIT {int(max_rows)}"
            )
            columns = [desc[0] for desc in result.description]
            rows = result.fetchall()
            return {
                "columns": columns,
                "rows": [list(r) for r in rows],
                "row_count": len(rows),
            }
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Session state
    # ------------------------------------------------------------------

    def get_session_state(self) -> dict:
        """Serialise the current engine state for session saving."""
        return {
            "file_path": self._file_path,
            "filters": self._filters,
            "sort_columns": self._sort_columns,
            "hidden_columns": list(self._hidden_columns),
            "column_order": self._column_order,
            "column_types": {
                k: v.value for k, v in self._column_types.items()
            },
            "read_only": self._read_only,
        }

    def restore_session_state(self, state: dict):
        """Restore engine state from a previously saved session dict."""
        self._filters = state.get("filters", [])
        self._sort_columns = [
            tuple(s) for s in state.get("sort_columns", [])
        ]
        self._hidden_columns = set(state.get("hidden_columns", []))
        self._column_order = state.get("column_order", list(self._columns))
        self._read_only = state.get("read_only", False)
        type_overrides = state.get("column_types", {})
        for col, t in type_overrides.items():
            if col in self._column_types:
                try:
                    self._column_types[col] = ColumnType(t)
                except ValueError:
                    pass
