"""Session save/load for preserving application state."""

import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Dict, Mapping, MutableMapping, Optional, Union

from csvviewer.utils.constants import SESSION_FILE_EXTENSION


SessionPath = Union[str, Path]


def _normalize_session_path(session_path: SessionPath) -> Path:
    """Ensure the parent directory exists and return a resolved ``Path``."""
    path = Path(session_path).expanduser()
    if not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
    return path


def save_session(session_data: Mapping[str, Any], session_path: SessionPath) -> Path:
    """Persist JSON-serializable session data to disk.

    The write is performed atomically by writing to a temporary file in
    the destination directory and then replacing the target file.
    """
    path = _normalize_session_path(session_path)

    with NamedTemporaryFile(
        "w", encoding="utf-8", dir=str(path.parent), delete=False
    ) as tmp_file:
        json.dump(dict(session_data), tmp_file, indent=2, sort_keys=True, default=str)
        tmp_file.write("\n")
        temp_path = Path(tmp_file.name)

    temp_path.replace(path)
    return path


def load_session(
    session_path: SessionPath, default: Optional[MutableMapping[str, Any]] = None
) -> Dict[str, Any]:
    """Load session data from disk.

    Returns a shallow copy of *default* if the file does not exist.
    Raises ``ValueError`` if the file exists but does not contain a
    JSON object.
    """
    path = Path(session_path).expanduser()
    if not path.exists():
        return dict(default or {})

    with path.open("r", encoding="utf-8") as session_file:
        data = json.load(session_file)

    if not isinstance(data, dict):
        raise ValueError("Session file must contain a JSON object.")

    return data


def clear_session(session_path: SessionPath) -> None:
    """Remove a persisted session file if it exists."""
    path = Path(session_path).expanduser()
    try:
        path.unlink()
    except FileNotFoundError:
        pass


class SessionManager:
    """File-based session manager for saving and loading UI state.

    Also manages a recent-files list stored in
    ``~/.csvviewer/recent_files.json``.
    """

    def __init__(self, session_path: Optional[SessionPath] = None):
        self._config_dir = os.path.expanduser("~/.csvviewer")
        os.makedirs(self._config_dir, exist_ok=True)
        self._session_path = Path(session_path) if session_path else None
        self._recent_files: list[str] = []
        self._load_recent_files()

    # --- Session persistence ---

    def save(self, session_data: Mapping[str, Any],
             session_path: Optional[SessionPath] = None) -> Path:
        """Save session data.  Uses *session_path* or the path given at init."""
        path = session_path or self._session_path
        if not path:
            raise ValueError("No session path specified.")
        return save_session(session_data, path)

    def load(
        self,
        session_path: Optional[SessionPath] = None,
        default: Optional[MutableMapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Load session data."""
        path = session_path or self._session_path
        if not path:
            return dict(default or {})
        return load_session(path, default=default)

    def clear(self, session_path: Optional[SessionPath] = None) -> None:
        """Remove a session file."""
        path = session_path or self._session_path
        if path:
            clear_session(path)

    # --- Recent files ---

    def add_recent_file(self, file_path: str):
        """Add a file to the recent-files list."""
        if file_path in self._recent_files:
            self._recent_files.remove(file_path)
        self._recent_files.insert(0, file_path)
        self._recent_files = self._recent_files[:10]
        self._save_recent_files()

    def get_recent_files(self) -> list[str]:
        """Return a copy of the recent-files list."""
        return list(self._recent_files)

    def _load_recent_files(self):
        path = os.path.join(self._config_dir, "recent_files.json")
        try:
            with open(path, "r") as f:
                self._recent_files = json.load(f)
        except Exception:
            self._recent_files = []

    def _save_recent_files(self):
        path = os.path.join(self._config_dir, "recent_files.json")
        try:
            with open(path, "w") as f:
                json.dump(self._recent_files, f)
        except Exception:
            pass
