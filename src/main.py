import sys

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ai_worker import OllamaWorker
from database import init_db, lookup_eijiro
from flow_layout import FlowLayout  # Our new layout!

# Internal imports
from processor import TextProcessor

DARK_STYLE = """
    QMainWindow, QWidget { background-color: #121212; color: #e0e0e0; font-family: 'Meiryo', 'Segoe UI'; }
    QTextEdit {
        background-color: #1e1e1e;
        border: 1px solid #333;
        color: #e0e0e0;
        border-radius: 6px;
        padding: 10px;
        font-size: 14px;
    }
    QScrollArea { border: none; background-color: transparent; }
    QPushButton#AnalyzeBtn {
        background-color: #3d5afe;
        color: white;
        border-radius: 6px;
        padding: 12px;
        font-weight: bold;
        font-size: 14px;
    }
    QPushButton#AnalyzeBtn:hover { background-color: #536dfe; }

    QFrame#TokenCard {
        border: 1px solid #2a2a2a;
        border-radius: 6px;
        background-color: #1e1e1e;
    }
    QFrame#TokenCard:hover { border: 1px solid #3d5afe; background-color: #252525; }
    QLabel#Romaji { color: #777; font-size: 10px; }
    QLabel#Kana { color: #3d5afe; font-size: 12px; font-weight: bold; }
    QLabel#Surface { font-size: 20px; font-weight: 500; margin-top: 2px; }
"""


class TokenWidget(QFrame):
    clicked = pyqtSignal(dict)

    def __init__(self, token_data):
        super().__init__()
        self.setObjectName("TokenCard")
        self.data = token_data
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 6)
        layout.setSpacing(0)

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

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedWidth(
            max(
                80,
                self.surface_lbl.fontMetrics()
                .boundingRect(token_data["surface"])
                .width()
                + 30,
            )
        )

    def mousePressEvent(self, event):
        self.clicked.emit(self.data)


class YomikataApp(QMainWindow):
    def __init__(self):
        super().__init__()
        init_db()
        self.processor = TextProcessor()
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Yomikata Japanese Assistant")
        self.resize(1200, 850)
        self.setStyleSheet(DARK_STYLE)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)

        # --- LEFT SIDE (Reading & Input) ---
        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(15, 15, 15, 15)

        # 1. Top: Reading Area (The Output)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.matrix_container = QWidget()
        self.matrix_container.setStyleSheet("background-color: transparent;")

        # Use our NEW wrapping layout
        self.matrix_layout = FlowLayout(self.matrix_container, spacing=10)

        self.scroll.setWidget(self.matrix_container)

        # 2. Bottom: Input Area
        input_container = QVBoxLayout()
        self.input_area = QTextEdit()
        self.input_area.setPlaceholderText("Paste Japanese text here...")
        self.input_area.setMaximumHeight(150)

        self.analyze_btn = QPushButton("Analyze Text (Ctrl+Enter)")
        self.analyze_btn.setObjectName("AnalyzeBtn")
        self.analyze_btn.clicked.connect(self.analyze_text)

        input_container.addWidget(self.input_area)
        input_container.addWidget(self.analyze_btn)

        # Build Left Layout: Scroll (Top), Input (Bottom)
        left_layout.addWidget(self.scroll, stretch=1)
        left_layout.addLayout(input_container)

        # --- RIGHT SIDE (Dictionary & AI) ---
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)

        self.dict_display = QTextEdit()
        self.dict_display.setReadOnly(True)

        self.ai_btn = QPushButton("Ask AI Sensei (Ollama)")
        self.ai_btn.clicked.connect(self.ask_ai)
        self.ai_btn.setEnabled(False)
        self.ai_btn.setMinimumHeight(40)

        right_layout.addWidget(QLabel("<b>DICTIONARY REVEAL</b>"))
        right_layout.addWidget(self.dict_display)
        right_layout.addWidget(self.ai_btn)

        self.splitter.addWidget(left_container)
        self.splitter.addWidget(right_container)
        self.splitter.setStretchFactor(0, 3)
        self.splitter.setStretchFactor(1, 1)

        self.setCentralWidget(self.splitter)

        # Shortcut for Ctrl+Enter
        self.input_area.installEventFilter(self)

    def eventFilter(self, obj, event):
        if obj is self.input_area and event.type() == event.Type.KeyPress:
            if (
                event.key() == Qt.Key.Key_Return
                and event.modifiers() == Qt.Modifier.CONTROL
            ):
                self.analyze_text()
                return True
        return super().eventFilter(obj, event)

    def analyze_text(self):
        text = self.input_area.toPlainText().strip()
        if not text:
            return

        # Clear existing widgets from flow layout
        while self.matrix_layout.count():
            item = self.matrix_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        tokens = self.processor.tokenize(text)
        for token in tokens:
            card = TokenWidget(token)
            card.clicked.connect(self.handle_token_click)
            self.matrix_layout.addWidget(card)

    def handle_token_click(self, data):
        self.selected_token = data
        self.ai_btn.setEnabled(True)

        definition = lookup_eijiro(data["lemma"])
        if not definition:
            definition = "<i>No Eijiro entry found.</i>"

        header = f"<h2 style='margin-bottom:0;'>{data['surface']}</h2>"
        header += f"<p style='color:#3d5afe;'>{data['kana']} | {data['romaji']}</p>"
        header += f"<b>Lemma:</b> {data['lemma']} | <b>POS:</b> {data['pos']}<hr>"

        self.dict_display.setHtml(
            header
            + f"<div style='font-size:13px;'>{definition.replace('\n', '<br>')}</div>"
        )

    def ask_ai(self):
        if not hasattr(self, "selected_token"):
            return

        # AI Logic (OllamaWorker call) goes here as before...
        pass


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = YomikataApp()
    window.show()
    sys.exit(app.exec())
