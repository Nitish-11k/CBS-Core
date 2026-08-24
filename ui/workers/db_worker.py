"""
Background workers module.
Provides QThread/QRunnable classes for long-running DB/export tasks.
"""
from PySide6.QtCore import QThread, Signal
from typing import Callable, Any
import traceback

class WorkerThread(QThread):
    """
    A generic QThread worker that takes a function and its arguments.
    Emits signals on success, error, and completion.
    """
    result_ready = Signal(object)
    error_occurred = Signal(str)
    finished = Signal()

    def __init__(self, func: Callable, *args, **kwargs):
        super().__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs

    def run(self):
        try:
            result = self.func(*self.args, **self.kwargs)
            self.result_ready.emit(result)
        except Exception as e:
            err_msg = f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}"
            self.error_occurred.emit(err_msg)
        finally:
            self.finished.emit()
