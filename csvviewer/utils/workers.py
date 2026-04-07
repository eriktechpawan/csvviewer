"""QThread-based workers for asynchronous operations."""

import traceback

from PySide6.QtCore import QObject, QRunnable, QThread, Signal, Slot


class WorkerSignals(QObject):
    """Signals available from a running worker."""
    finished = Signal()
    error = Signal(str)
    result = Signal(object)
    progress = Signal(int)


class Worker(QRunnable):
    """Generic worker that runs an arbitrary function in QThreadPool.

    Usage::

        worker = Worker(long_running_fn, arg1, arg2, key=val)
        worker.signals.result.connect(handle_result)
        worker.signals.error.connect(handle_error)
        QThreadPool.globalInstance().start(worker)
    """

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()
        self._cancelled = False

    @Slot()
    def run(self):
        try:
            result = self.fn(
                *self.args,
                **self.kwargs,
            )
            if not self._cancelled:
                self.signals.result.emit(result)
        except Exception:
            if not self._cancelled:
                self.signals.error.emit(traceback.format_exc())
        finally:
            self.signals.finished.emit()

    def cancel(self):
        """Request cancellation of this worker."""
        self._cancelled = True

    @property
    def is_cancelled(self):
        return self._cancelled


class _CancellableThread(QThread):
    """Base class for QThread workers with progress and cancellation."""

    progress = Signal(int)
    finished_with_result = Signal(object)
    error = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cancelled = False

    def cancel(self):
        """Request cancellation. Subclasses should check ``is_cancelled``."""
        self._cancelled = True

    @property
    def is_cancelled(self):
        return self._cancelled


class DataLoadWorker(_CancellableThread):
    """Worker thread for loading CSV files.

    Parameters
    ----------
    file_path : str
        Path to the CSV file to load.
    load_fn : callable
        Function that performs the actual loading. It receives
        ``(file_path, progress_callback)`` where *progress_callback*
        is called with an int 0-100.
    """

    def __init__(self, file_path: str, load_fn, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.load_fn = load_fn

    def run(self):
        try:
            result = self.load_fn(self.file_path, progress_callback=self._emit_progress)
            if not self._cancelled:
                self.finished_with_result.emit(result)
        except Exception:
            if not self._cancelled:
                self.error.emit(traceback.format_exc())

    def _emit_progress(self, value: int):
        if not self._cancelled:
            self.progress.emit(value)


class FilterWorker(_CancellableThread):
    """Worker thread for running filter operations on large datasets.

    Parameters
    ----------
    filter_fn : callable
        Function that performs filtering. It receives
        ``(data, filter_params, progress_callback)`` and returns
        the filtered result.
    data : object
        The dataset to filter (e.g. a Polars DataFrame).
    filter_params : dict
        Parameters describing the filter to apply.
    """

    def __init__(self, filter_fn, data, filter_params: dict, parent=None):
        super().__init__(parent)
        self.filter_fn = filter_fn
        self.data = data
        self.filter_params = filter_params

    def run(self):
        try:
            result = self.filter_fn(
                self.data, self.filter_params, self._emit_progress,
            )
            if not self._cancelled:
                self.finished_with_result.emit(result)
        except Exception:
            if not self._cancelled:
                self.error.emit(traceback.format_exc())

    def _emit_progress(self, value: int):
        if not self._cancelled:
            self.progress.emit(value)


class ExportWorker(_CancellableThread):
    """Worker thread for export operations with progress reporting.

    Parameters
    ----------
    export_fn : callable
        Function that performs the export. It receives
        ``(data, export_path, export_params, progress_callback)``
        and returns the path of the exported file.
    data : object
        The dataset to export.
    export_path : str
        Destination file path.
    export_params : dict
        Additional export configuration.
    """

    def __init__(self, export_fn, data, export_path: str,
                 export_params: dict | None = None, parent=None):
        super().__init__(parent)
        self.export_fn = export_fn
        self.data = data
        self.export_path = export_path
        self.export_params = export_params or {}

    def run(self):
        try:
            result = self.export_fn(
                self.data, self.export_path, self.export_params,
                self._emit_progress,
            )
            if not self._cancelled:
                self.finished_with_result.emit(result)
        except Exception:
            if not self._cancelled:
                self.error.emit(traceback.format_exc())

    def _emit_progress(self, value: int):
        if not self._cancelled:
            self.progress.emit(value)


class SearchWorker(_CancellableThread):
    """Worker thread for global search operations.

    Parameters
    ----------
    search_fn : callable
        Function that performs the search. It receives
        ``(data, query, search_params, progress_callback)``
        and returns matching results.
    data : object
        The dataset to search in.
    query : str
        The search query string.
    search_params : dict
        Additional search options (e.g. case sensitivity, regex).
    """

    def __init__(self, search_fn, data, query: str,
                 search_params: dict | None = None, parent=None):
        super().__init__(parent)
        self.search_fn = search_fn
        self.data = data
        self.query = query
        self.search_params = search_params or {}

    def run(self):
        try:
            result = self.search_fn(
                self.data, self.query, self.search_params,
                self._emit_progress,
            )
            if not self._cancelled:
                self.finished_with_result.emit(result)
        except Exception:
            if not self._cancelled:
                self.error.emit(traceback.format_exc())

    def _emit_progress(self, value: int):
        if not self._cancelled:
            self.progress.emit(value)
