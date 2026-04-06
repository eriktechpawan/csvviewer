"""Edit history management with undo/redo support.

This module implements a command-pattern based undo/redo system for tracking
all editing operations performed on CSV data. Each edit is captured as an
``EditCommand`` containing the information needed to reverse or replay it,
and an ``EditHistory`` manager maintains the undo and redo stacks.
"""

from dataclasses import dataclass, field
from typing import Any, Optional, Callable
from enum import Enum, auto


class EditType(Enum):
    """Enumeration of all supported edit operation types."""

    CELL_EDIT = auto()
    ROW_ADD = auto()
    ROW_DELETE = auto()
    ROW_DUPLICATE = auto()
    COLUMN_ADD = auto()
    COLUMN_DELETE = auto()
    COLUMN_RENAME = auto()
    BULK_EDIT = auto()
    FILL_DOWN = auto()
    REPLACE = auto()
    TRIM_WHITESPACE = auto()
    REMOVE_DUPLICATES = auto()
    TYPE_CONVERT = auto()


@dataclass
class EditCommand:
    """Represents a single undoable edit operation.

    Attributes:
        edit_type: The category of edit that was performed.
        description: A human-readable summary shown in undo/redo menus.
        undo_data: Arbitrary data needed to reverse the operation.
        redo_data: Arbitrary data needed to replay the operation.
    """

    edit_type: EditType
    description: str
    undo_data: dict = field(default_factory=dict)
    redo_data: dict = field(default_factory=dict)


class EditHistory:
    """Manages undo/redo stacks for all editing operations.

    The history keeps two stacks: one for undo and one for redo.  When a new
    edit is pushed the redo stack is cleared (a new edit after undoing
    invalidates the previous future).  The undo stack is capped at
    ``max_history`` entries to bound memory usage.

    An optional *on_change* callback is invoked whenever the stacks are
    mutated so that the UI can refresh undo/redo button states.

    Attributes:
        _undo_stack: Stack of commands that can be undone.
        _redo_stack: Stack of commands that can be redone.
        _max_history: Maximum number of undo entries retained.
        _modified: Whether the data has unsaved modifications.
        _on_change: Optional callback fired on every stack mutation.
    """

    def __init__(self, max_history: int = 100) -> None:
        """Initialise an empty edit history.

        Args:
            max_history: Maximum number of undo steps to keep.  When this
                limit is exceeded the oldest entry is discarded.
        """
        self._undo_stack: list[EditCommand] = []
        self._redo_stack: list[EditCommand] = []
        self._max_history = max_history
        self._modified = False
        self._on_change: Optional[Callable] = None

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def can_undo(self) -> bool:
        """Return ``True`` if there is at least one undoable command."""
        return len(self._undo_stack) > 0

    @property
    def can_redo(self) -> bool:
        """Return ``True`` if there is at least one redoable command."""
        return len(self._redo_stack) > 0

    @property
    def is_modified(self) -> bool:
        """Return ``True`` if data has been modified since last save."""
        return self._modified

    @property
    def undo_text(self) -> str:
        """Human-readable label for the next undo action."""
        if self._undo_stack:
            return f"Undo {self._undo_stack[-1].description}"
        return "Undo"

    @property
    def redo_text(self) -> str:
        """Human-readable label for the next redo action."""
        if self._redo_stack:
            return f"Redo {self._redo_stack[-1].description}"
        return "Redo"

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def set_on_change(self, callback: Callable) -> None:
        """Register a callback invoked whenever the history stacks change.

        Args:
            callback: A callable with no required arguments.
        """
        self._on_change = callback

    # ------------------------------------------------------------------
    # Stack operations
    # ------------------------------------------------------------------

    def push(self, command: EditCommand) -> None:
        """Record a new edit command.

        The command is placed on the undo stack and the redo stack is
        cleared because a new edit after an undo creates a new timeline.
        If the undo stack exceeds ``max_history`` the oldest entry is
        discarded.

        Args:
            command: The edit command to record.
        """
        self._undo_stack.append(command)
        self._redo_stack.clear()
        if len(self._undo_stack) > self._max_history:
            self._undo_stack.pop(0)
        self._modified = True
        if self._on_change:
            self._on_change()

    def undo(self) -> Optional[EditCommand]:
        """Undo the most recent edit.

        The command is moved from the undo stack to the redo stack.

        Returns:
            The ``EditCommand`` that should be reversed, or ``None`` if the
            undo stack is empty.
        """
        if not self.can_undo:
            return None
        command = self._undo_stack.pop()
        self._redo_stack.append(command)
        self._modified = bool(self._undo_stack)
        if self._on_change:
            self._on_change()
        return command

    def redo(self) -> Optional[EditCommand]:
        """Redo the most recently undone edit.

        The command is moved from the redo stack back to the undo stack.

        Returns:
            The ``EditCommand`` that should be replayed, or ``None`` if the
            redo stack is empty.
        """
        if not self.can_redo:
            return None
        command = self._redo_stack.pop()
        self._undo_stack.append(command)
        self._modified = True
        if self._on_change:
            self._on_change()
        return command

    def clear(self) -> None:
        """Discard all undo and redo history and reset the modified flag."""
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._modified = False
        if self._on_change:
            self._on_change()

    def mark_saved(self) -> None:
        """Mark the current state as saved, clearing the modified flag."""
        self._modified = False
