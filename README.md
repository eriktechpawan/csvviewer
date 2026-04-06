# CSV Viewer

A high-performance desktop CSV viewer and editor built with Python, PySide6, and DuckDB. Designed to handle very large CSV files (millions of rows) efficiently on macOS Apple Silicon.

## Features

### Core
- **Open CSV files** with auto-detection of delimiter, encoding, and header row
- **Virtualized table** rendering — only visible rows are fetched from DuckDB, enabling smooth scrolling through millions of rows
- **Powerful filtering** — value, numeric, and text filters with AND/OR combinations
- **Multi-column sorting** with preserved filter state
- **Column statistics** — click any column header for count, min/max, sum, average, unique count, and top values
- **Row & column editing** — add, delete, duplicate rows; add, delete, rename columns; cell editing
- **Export** filtered/selected data to CSV with delimiter and encoding options
- **Search** across all columns or within a specific column with next/previous navigation
- **Undo/redo** for all editing operations

### Data Quality
- **Auto-detect column types** (text, integer, float, boolean, datetime)
- **Missing/null value display** with visual indicators
- **Data cleanup tools** — remove duplicates, trim whitespace, find & replace, type conversion
- **Read-only mode** to prevent accidental changes
- **Auto-backup** before overwriting files

### Usability
- **Dark mode** UI
- **Keyboard shortcuts** for common actions
- **Right-click context menus** on cells, rows, and column headers
- **Column reordering and resizing** via drag-and-drop headers
- **Hide/show columns**
- **Status bar** showing total rows, filtered rows, selected rows, columns, and file size
- **Session save/load** — preserves file path, filters, sorts, column layout
- **Recent files** list
- **Import preview dialog** with delimiter/encoding override

## Architecture

```
csvviewer/
├── app.py              # Application entry point
├── engine/
│   ├── data_engine.py  # DuckDB-backed data engine (core)
│   ├── csv_loader.py   # CSV auto-detection utilities
│   └── export.py       # Export & backup utilities
├── models/
│   └── table_model.py  # Virtualized Qt table model (chunked loading)
├── ui/
│   ├── main_window.py  # Main window (wires everything together)
│   ├── table_view.py   # Custom QTableView with smooth scrolling
│   ├── toolbar.py      # Toolbar with file/edit/view actions
│   ├── status_bar.py   # Status bar with data summary
│   ├── search_bar.py   # Search with next/previous navigation
│   ├── filter_dialog.py    # Multi-condition filter dialog
│   ├── stats_dialog.py     # Column statistics dialog
│   ├── import_dialog.py    # CSV import preview
│   ├── export_dialog.py    # Export options dialog
│   ├── cleanup_dialog.py   # Data cleanup tools
│   ├── column_menu.py      # Column header context menu
│   └── session_manager.py  # Session save/load
├── history/
│   └── undo_redo.py    # Command-pattern undo/redo
└── utils/
    ├── constants.py    # App constants and enums
    └── workers.py      # QThread workers for async operations
```

### Performance Design

- **DuckDB in-memory SQL** — CSV data is loaded once into DuckDB. All queries (filter, sort, stats, fetch) use SQL and return only the needed slice.
- **Chunked row fetching** — The table model fetches rows in chunks of 1000 from DuckDB as the user scrolls, with an LRU cache of 20 chunks.
- **No full dataset in memory** — The UI never holds all rows. Only ~20,000 rows are cached at any time.
- **Off-main-thread workers** — Long-running operations (load, export, search) can use QThread workers to keep the UI responsive.

## Setup

### Prerequisites

- Python 3.10+
- macOS (Apple Silicon recommended) or Linux

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Run

```bash
python -m csvviewer
```

Or open a specific file:

```bash
python -m csvviewer /path/to/data.csv
```

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| Ctrl+O | Open file |
| Ctrl+S | Save |
| Ctrl+Shift+S | Save As |
| Ctrl+E | Export |
| Ctrl+Z | Undo |
| Ctrl+Shift+Z | Redo |
| Ctrl+F | Filter |
| Ctrl+H | Search |
| Delete | Delete selected rows |

## Packaging for macOS

### Using PyInstaller

```bash
pip install pyinstaller

pyinstaller --name "CSV Viewer" \
    --windowed \
    --onedir \
    --icon=icon.icns \
    --target-arch universal2 \
    csvviewer/__main__.py
```

The built app will be in `dist/CSV Viewer.app`.

### Using py2app

```bash
pip install py2app
```

Create a `setup_mac.py`:

```python
from setuptools import setup

setup(
    app=['csvviewer/__main__.py'],
    options={'py2app': {
        'argv_emulation': True,
        'packages': ['PySide6', 'duckdb', 'polars', 'chardet'],
        'iconfile': 'icon.icns',
    }},
    setup_requires=['py2app'],
)
```

Then build:

```bash
python setup_mac.py py2app
```

## Requirements

- PySide6 >= 6.6.0
- duckdb >= 0.10.0
- polars >= 0.20.0
- chardet >= 5.0.0

## License

See [LICENSE](LICENSE).
