"""Application-wide constants for CSV Viewer."""

from enum import Enum

# Application metadata
APP_NAME = "CSV Viewer"
APP_VERSION = "1.0.0"

# Data loading
DEFAULT_CHUNK_SIZE = 10000
MAX_PREVIEW_ROWS = 100

# Session / recent files
SESSION_FILE_EXTENSION = ".csvproj"
RECENT_FILES_MAX = 10


class ColumnType(Enum):
    """Supported column data types."""
    TEXT = "text"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    DATETIME = "datetime"


class ValueFilterOp(Enum):
    """Filter operators for value-based comparisons."""
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    IN_LIST = "in_list"
    NOT_IN_LIST = "not_in_list"
    IS_EMPTY = "is_empty"
    NOT_EMPTY = "not_empty"
    IS_NULL = "is_null"
    NOT_NULL = "not_null"


class NumericFilterOp(Enum):
    """Filter operators for numeric comparisons."""
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
    BETWEEN = "between"
    OUTSIDE_RANGE = "outside_range"
    IS_ZERO = "is_zero"
    NON_ZERO = "non_zero"
    POSITIVE = "positive"
    NEGATIVE = "negative"


class TextFilterOp(Enum):
    """Filter operators for text comparisons."""
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    EXACT_MATCH = "exact_match"
    REGEX = "regex"


FILTER_OPERATORS = {
    "value": {op.name: op.value for op in ValueFilterOp},
    "numeric": {op.name: op.value for op in NumericFilterOp},
    "text": {op.name: op.value for op in TextFilterOp},
}

# Keyboard shortcut mappings (platform-aware modifier is handled by Qt)
KEYBOARD_SHORTCUTS = {
    "open_file": "Ctrl+O",
    "save": "Ctrl+S",
    "save_as": "Ctrl+Shift+S",
    "export": "Ctrl+E",
    "close": "Ctrl+W",
    "quit": "Ctrl+Q",
    "undo": "Ctrl+Z",
    "redo": "Ctrl+Shift+Z",
    "copy": "Ctrl+C",
    "paste": "Ctrl+V",
    "cut": "Ctrl+X",
    "select_all": "Ctrl+A",
    "find": "Ctrl+F",
    "find_replace": "Ctrl+H",
    "goto_row": "Ctrl+G",
    "filter": "Ctrl+L",
    "clear_filters": "Ctrl+Shift+L",
    "column_stats": "Ctrl+I",
    "new_window": "Ctrl+N",
    "zoom_in": "Ctrl+=",
    "zoom_out": "Ctrl+-",
    "zoom_reset": "Ctrl+0",
    "delete_row": "Del",
    "insert_row": "Ctrl+Shift+N",
}
