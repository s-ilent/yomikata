import re
import sys

import qtawesome as qta
from PyQt6.QtCore import QSettings, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ai_worker import AIWorker
from database import init_db, lookup_word, save_to_personal_dict
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


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.settings = QSettings("Yomikata", "Settings")

        layout = QFormLayout(self)

        self.ai_provider = QComboBox()
        self.ai_provider.addItems(["Ollama", "OpenAI / Compatible"])
        self.ai_provider.setCurrentText(self.settings.value("ai_provider", "Ollama"))

        self.api_url = QLineEdit(
            self.settings.value("api_url", "http://localhost:11434")
        )
        self.api_key = QLineEdit(self.settings.value("api_key", ""))
        self.ai_model = QLineEdit(self.settings.value("ai_model", "llama3"))

        layout.addRow("AI Provider:", self.ai_provider)
        layout.addRow("API URL:", self.api_url)
        layout.addRow("API Key:", self.api_key)
        layout.addRow("Model Name:", self.ai_model)

        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.save_settings)
        layout.addRow(save_btn)

    def save_settings(self):
        self.settings.setValue("ai_provider", self.ai_provider.currentText())
        self.settings.setValue("api_url", self.api_url.text())
        self.settings.setValue("api_key", self.api_key.text())
        self.settings.setValue("ai_model", self.ai_model.text())
        self.accept()


class PunctuationWidget(QLabel):
    """Small, non-clickable widget for 、。！？ etc."""

    def __init__(self, text):
        super().__init__(text)
        self.setStyleSheet(
            "font-size: 20px; color: #555; padding: 0px; margin-top: 15px;"
        )
        self.setAlignment(Qt.AlignmentFlag.AlignBottom)


class TokenWidget(QFrame):
    clicked = pyqtSignal(dict)

    def __init__(self, token_data):
        super().__init__()
        self.setObjectName("TokenCard")
        self.data = token_data
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)  # Reduced margins
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

        # FIXED: Dynamic width based on content, but with a smaller minimum
        fm = self.surface_lbl.fontMetrics()
        width = fm.boundingRect(token_data["surface"]).width() + 15
        self.setMinimumWidth(max(30, width))  # Min size reduced to 30px

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

        # --- AI and Settings Buttons ---
        ai_controls_layout = QHBoxLayout()

        # Main AI Button
        self.ai_btn = QPushButton(" Ask AI Sensei")  # Added a space for icon padding
        self.ai_btn.setIcon(qta.icon("fa5s.robot", color="white"))  # Robot icon!
        self.ai_btn.clicked.connect(self.ask_ai)
        self.ai_btn.setEnabled(False)
        self.ai_btn.setMinimumHeight(40)
        self.ai_btn.setObjectName("AnalyzeBtn")  # Reusing the blue style

        # Settings Button (The Gear)
        self.settings_btn = QPushButton()
        self.settings_btn.setIcon(qta.icon("fa5s.cog", color="#e0e0e0"))
        self.settings_btn.setFixedSize(40, 40)  # Keep it square
        self.settings_btn.setToolTip("Settings")
        self.settings_btn.clicked.connect(self.open_settings)
        self.settings_btn.setStyleSheet("""
            QPushButton {
                background-color: #2a2a2a;
                border: 1px solid #444;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #333; border: 1px solid #555; }
        """)

        ai_controls_layout.addWidget(self.ai_btn, stretch=4)  # Takes up most space
        ai_controls_layout.addWidget(self.settings_btn, stretch=1)  # The little gear

        self.save_ai_btn = QPushButton("Save AI Explanation to Personal Dict")
        self.save_ai_btn.setIcon(qta.icon("fa5s.save", color="white"))
        self.save_ai_btn.clicked.connect(self.save_ai_to_dict)
        self.save_ai_btn.setVisible(False)  # Hide it until AI responds
        self.save_ai_btn.setStyleSheet(
            "background-color: #2e7d32; color: white; padding: 8px;"
        )

        right_layout.addWidget(QLabel("<b>DICTIONARY REVEAL</b>"))
        right_layout.addWidget(self.dict_display)
        right_layout.addLayout(ai_controls_layout)
        right_layout.addWidget(self.save_ai_btn)

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

    def format_definition(self, text):
        """Adds line breaks before special symbols ●, ◆, ■, and numbering like 1."""
        if not text:
            return ""
        # Break before symbols
        text = re.sub(r"([●◆■])", r"<br>\1", text)
        # Break before bracketed numbers (e.g., 【1】 or (1))
        text = re.sub(r"([（\(【]\d+[】\)\)])", r"<br>\1", text)
        return text

    def analyze_text(self):
        text = self.input_area.toPlainText().strip()
        if not text:
            return

        while self.matrix_layout.count():
            item = self.matrix_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        tokens = self.processor.tokenize(text)
        punct_chars = "、。「」！？（）()., "

        for token in tokens:
            # Check if it's punctuation or whitespace
            if token["surface"] in punct_chars or "記号" in token["pos"]:
                widget = PunctuationWidget(token["surface"])
                self.matrix_layout.addWidget(widget)
            else:
                card = TokenWidget(token)
                card.clicked.connect(self.handle_token_click)
                self.matrix_layout.addWidget(card)

    def handle_token_click(self, data):
        self.selected_token = data
        self.ai_btn.setEnabled(True)

        raw_definition = lookup_word(data["surface"], data["lemma"])
        formatted_definition = self.format_definition(raw_definition)

        header = f"<h2 style='margin:0;'>{data['surface']}</h2>"
        header += (
            f"<p style='color:#3d5afe; margin:0;'>{data['kana']} | {data['romaji']}</p>"
        )
        header += f"<small>POS: {data['pos']}</small><hr>"

        self.dict_display.setHtml(
            header + f"<div style='font-size:13px;'>{formatted_definition}</div>"
        )

    def open_settings(self):
        dialog = SettingsDialog(self)
        if dialog.exec():
            # You could add logic here to refresh the AIWorker
            # or update the UI based on new settings
            print("Settings saved!")

    def ask_ai(self):
        if not hasattr(self, "selected_token"):
            return

        word = self.selected_token["surface"]
        context = self.input_area.toPlainText()

        # Construct a targeted prompt
        prompt = (
            f"You are a Japanese language expert. Context: '{context}'\n"
            f"Please explain the specific word/grammar point: '{word}'.\n"
            "Provide a concise definition, its role in this sentence, and any nuance. "
            "Respond in English, but keep the tone helpful for a student."
        )

        self.dict_display.append("<br><hr><b>AI Sensei is thinking...</b><br>")
        self.ai_btn.setEnabled(False)

        self.worker = AIWorker(prompt)
        self.worker.finished.connect(self.on_ai_response)
        self.worker.error.connect(
            lambda err: self.dict_display.append(
                f"<span style='color:red;'>Error: {err}</span>"
            )
        )
        self.worker.start()

    def on_ai_response(self, response):
        self.ai_btn.setEnabled(True)
        # Store the latest AI response in a temporary variable so we can save it
        self.last_ai_response = response

        # Append to display
        formatted_response = response.replace("\n", "<br>")
        self.dict_display.append(f"<b>AI Sensei:</b><br>{formatted_response}")

        # Show a "Save this to my dictionary" button if it's not already there
        if not hasattr(self, "save_ai_btn"):
            self.save_ai_btn = QPushButton("Save AI Explanation to Personal Dict")
            self.save_ai_btn.clicked.connect(self.save_ai_to_dict)
            self.layout().itemAt(0).widget().layout().addWidget(
                self.save_ai_btn
            )  # Add to sidebar

    def save_ai_to_dict(self):
        if hasattr(self, "selected_token") and hasattr(self, "last_ai_response"):
            word = self.selected_token["surface"]
            # We save it as a custom definition
            save_to_personal_dict(word, self.last_ai_response)
            self.dict_display.append("<br><i>Saved to personal dictionary!</i>")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = YomikataApp()
    window.show()
    sys.exit(app.exec())
