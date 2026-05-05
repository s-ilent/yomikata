
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtCore import pyqtSignal as QtSignal
from PyQt6.QtGui import QCursor, QFont, QFontMetrics, QPainter
from PyQt6.QtWidgets import (
    QFrame,
    QLabel,
    QStyle,
    QStyleOption,
    QVBoxLayout,
)

from database import import_dictionary_file, import_yomitan_zip
from style import CATPPUCCIN_MOCHA as CAT


class ImportWorker(QThread):
    progress = QtSignal(int)
    finished = QtSignal(int)
    error = QtSignal(str)

    def __init__(self, source_path, target_db_path, import_format="Text (Eijiro)"):
        super().__init__()
        self.source_path = source_path
        self.target_db_path = target_db_path
        self.import_format = import_format

    def run(self):
        try:
            import sys
            debug_logs = []
            def debug_cb(msg):
                debug_logs.append(msg)
                print(f"IMPORT: {msg}", file=sys.stderr)

            if self.import_format == "Yomitan (ZIP)":
                count = import_yomitan_zip(
                    self.source_path,
                    self.target_db_path,
                    lambda p, t: self.progress.emit(int((p/t)*100)) if t > 0 else None
                )
            else:
                count = import_dictionary_file(
                    self.source_path,
                    self.target_db_path,
                    lambda p: self.progress.emit(p % 101), # Simple progress for now
                    debug_cb
                )

            self.finished.emit(count)
            # Send debug logs to parent if possible
            if self.parent() and hasattr(self.parent(), "debug_logs"):
                self.parent().debug_logs.extend(debug_logs)
        except Exception as e:
            self.error.emit(str(e))


class PunctuationWidget(QLabel):
    """Small, non-clickable widget for 、。！？ etc."""

    def __init__(self, text):
        super().__init__(text)
        self.setStyleSheet(
            f"font-size: 20px; color: {CAT['foreground']}; padding: 0px 5px; margin-top: 15px;"
        )
        self.setAlignment(Qt.AlignmentFlag.AlignBottom)


class TokenWidget(QFrame):
    clicked = pyqtSignal(dict, bool)  # Added bool for Ctrl-click status

    def __init__(self, token_data):
        super().__init__()
        self.setObjectName("TokenCard")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.data = token_data
        self.is_selected = False  # Tracking state

        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 4, 2, 4) # Reduced margins
        layout.setSpacing(0)

        # Labels
        self.romaji_lbl = QLabel(token_data["romaji"])
        self.romaji_lbl.setObjectName("Romaji")
        self.romaji_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.kana_lbl = QLabel(token_data["kana"])
        self.kana_lbl.setObjectName("Kana")
        self.kana_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.surface_lbl = QLabel(token_data["surface"])
        self.surface_lbl.setObjectName("Surface")
        self.surface_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(self.romaji_lbl)
        layout.addWidget(self.kana_lbl)
        layout.addWidget(self.surface_lbl)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        # Accurate width calculation matching CSS exactly
        f_romaji = QFont(); f_romaji.setPixelSize(10)
        f_kana = QFont(); f_kana.setPixelSize(12); f_kana.setBold(True)
        f_surface = QFont(); f_surface.setPixelSize(20); f_surface.setWeight(QFont.Weight.Medium)

        w_romaji = QFontMetrics(f_romaji).horizontalAdvance(token_data["romaji"])
        w_kana = QFontMetrics(f_kana).horizontalAdvance(token_data["kana"])
        w_surface = QFontMetrics(f_surface).horizontalAdvance(token_data["surface"])

        # Reduced padding (total horizontal padding: 8px)
        width = max(w_romaji, w_kana, w_surface) + 8
        self.setFixedWidth(max(20, width))

    def set_highlight(self, state):
        self.is_selected = state
        self.setProperty("selected", state)
        self.style().unpolish(self)
        self.style().polish(self)

    def paintEvent(self, event):
        opt = QStyleOption()
        opt.initFrom(self)
        p = QPainter(self)
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_Widget, opt, p, self)

    def mousePressEvent(self, event):
        # Check if Control key is held
        ctrl_held = event.modifiers() & Qt.KeyboardModifier.ControlModifier
        self.clicked.emit(self.data, bool(ctrl_held))
