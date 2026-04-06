"""Export utilities for CSV data.

Provides export functionality with progress tracking.
Uses DuckDB COPY for fast export of large datasets.
"""

import os
import shutil
from typing import Optional, Callable


def create_backup(file_path: str) -> Optional[str]:
    """Create a backup of a file before overwriting.
    
    Returns the backup file path.
    """
    if not os.path.exists(file_path):
        return None
    
    backup_path = file_path + '.bak'
    counter = 1
    while os.path.exists(backup_path):
        backup_path = f"{file_path}.bak{counter}"
        counter += 1
    
    shutil.copy2(file_path, backup_path)
    return backup_path


def format_file_size(size_bytes: int) -> str:
    """Format byte count as human-readable string."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"
