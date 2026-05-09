import logging

from PyQt6.QtCore import QTime
from PyQt6.QtWidgets import QTextEdit


class UIHandler(logging.Handler):
    """Custom logging handler to route logs to a QTextEdit viewer."""
    def __init__(self, log_viewer: QTextEdit):
        super().__init__()
        self.log_viewer = log_viewer

    def emit(self, record: logging.LogRecord) -> None:
        timestamp = QTime.currentTime().toString("HH:mm:ss")
        msg = self.format(record)
        self.log_viewer.append(f"[{timestamp}] {msg}")
