import re
import sys

import markdown
import qtawesome as qta
from PyQt6.QtCore import QDateTime, QPoint, QRect, QSettings, QSize, Qt, pyqtSignal
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
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTabWidget,
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
        self.setWindowTitle("Settings & Debug")
        self.resize(600, 500)
        self.settings = QSettings("Yomikata", "Settings")

        main_layout = QVBoxLayout(self)
        self.tabs = QTabWidget()

        # --- TAB 1: Configuration ---
        config_tab = QWidget()
        config_layout = QFormLayout(config_tab)

        self.ai_provider = QComboBox()
        self.ai_provider.addItems(["Ollama", "OpenAI / Compatible"])
        self.ai_provider.setCurrentText(self.settings.value("ai_provider", "Ollama"))

        self.api_url = QLineEdit(
            self.settings.value("api_url", "http://localhost:11434")
        )
        self.api_key = QLineEdit(self.settings.value("api_key", ""))
        self.ai_model = QLineEdit(self.settings.value("ai_model", "llama3"))

        config_layout.addRow("AI Provider:", self.ai_provider)
        config_layout.addRow("API URL:", self.api_url)
        config_layout.addRow("API Key:", self.api_key)
        config_layout.addRow("Model Name:", self.ai_model)

        self.tabs.addTab(config_tab, "AI Configuration")

        # --- TAB 2: Debug Logs ---
        debug_tab = QWidget()
        debug_layout = QVBoxLayout(debug_tab)

        self.log_viewer = QTextEdit()
        self.log_viewer.setReadOnly(True)
        self.log_viewer.setPlaceholderText("No logs yet...")
        self.log_viewer.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)

        # Access the logs from the main app (the parent)
        if parent and hasattr(parent, "debug_logs"):
            self.log_viewer.setPlainText("\n".join(parent.debug_logs))
            # Auto-scroll to bottom
            self.log_viewer.verticalScrollBar().setValue(
                self.log_viewer.verticalScrollBar().maximum()
            )

        clear_btn = QPushButton("Clear Logs")
        clear_btn.clicked.connect(self.clear_debug_logs)

        debug_layout.addWidget(self.log_viewer)
        debug_layout.addWidget(clear_btn)
        self.tabs.addTab(debug_tab, "Debug Logs")

        main_layout.addWidget(self.tabs)

        # Bottom Buttons
        btn_box = QHBoxLayout()
        save_btn = QPushButton("Save Settings")
        save_btn.clicked.connect(self.save_settings)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_box.addWidget(save_btn)
        btn_box.addWidget(cancel_btn)
        main_layout.addLayout(btn_box)

    def clear_debug_logs(self):
        if self.parent() and hasattr(self.parent(), "debug_logs"):
            self.parent().debug_logs = []
        self.log_viewer.clear()

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
    clicked = pyqtSignal(dict, bool)  # Added bool for Ctrl-click status

    def __init__(self, token_data):
        super().__init__()
        self.setObjectName("TokenCard")
        self.data = token_data
        self.is_selected = False  # Tracking state

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(0)

        # Labels as before...
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

        fm = self.surface_lbl.fontMetrics()
        width = fm.boundingRect(token_data["surface"]).width() + 20
        self.setFixedWidth(max(40, width))

    def set_highlight(self, state):
        self.is_selected = state
        if state:
            self.setStyleSheet(
                "QFrame#TokenCard { border: 2px solid #3d5afe; background-color: #2a2a2a; }"
            )
        else:
            self.setStyleSheet("")  # Reverts to stylesheet default

    def mousePressEvent(self, event):
        # Check if Control key is held
        ctrl_held = event.modifiers() & Qt.KeyboardModifier.ControlModifier
        self.clicked.emit(self.data, bool(ctrl_held))


class YomikataApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.selection_list = []  # List of selected token dicts
        self.debug_logs = []  # Store logs for the settings menu
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
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Indeterminate "pulser"
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet(
            "QProgressBar::chunk { background-color: #3d5afe; }"
        )
        self.progress_bar.setFixedHeight(4)

        right_layout.addWidget(QLabel("<b>DICTIONARY REVEAL</b>"))
        right_layout.addWidget(self.dict_display)
        right_layout.addLayout(ai_controls_layout)
        right_layout.addWidget(self.save_ai_btn)
        right_layout.addWidget(self.progress_bar)

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

    def open_settings(self):
        dialog = SettingsDialog(self)
        if dialog.exec():
            # You could add logic here to refresh the AIWorker
            # or update the UI based on new settings
            print("Settings saved!")

    def save_ai_to_dict(self):
        """Modified to save the COMBINED phrase, not just one word."""
        if self.selection_list and hasattr(self, "last_ai_response"):
            # Join all selected surfaces (e.g. "わかっ" + "た" = "わかった")
            combined_surface = "".join([t["surface"] for t in self.selection_list])

            save_to_personal_dict(combined_surface, self.last_ai_response)

            self.dict_display.append(
                f"<br><i style='color:#4caf50;'>✓ Saved '{combined_surface}' to personal dictionary!</i>"
            )
            self.save_ai_btn.setVisible(False)

    def log_debug(self, message):
        timestamp = QDateTime.currentDateTime().toString("hh:mm:ss")
        self.debug_logs.append(f"[{timestamp}] {message}")
        print(f"DEBUG: [{timestamp}] {message}")

    def handle_token_click(self, data, ctrl_held):
        # Find the widget that sent the signal
        sender = self.sender()

        if not ctrl_held:
            # Clear previous selection if Ctrl isn't held
            for i in range(self.matrix_layout.count()):
                w = self.matrix_layout.itemAt(i).widget()
                if isinstance(w, TokenWidget):
                    w.set_highlight(False)
            self.selection_list = [data]
            sender.set_highlight(True)
        else:
            # Toggle selection in multi-mode
            if data in self.selection_list:
                self.selection_list.remove(data)
                sender.set_highlight(False)
            else:
                self.selection_list.append(data)
                sender.set_highlight(True)

        self.update_dictionary_view()

    def update_dictionary_view(self):
        if not self.selection_list:
            return

        # Sort selection by their order in the text (optional but recommended)
        # For now, we just join them
        combined_surface = "".join([t["surface"] for t in self.selection_list])
        combined_lemma = "".join([t["lemma"] for t in self.selection_list])

        self.ai_btn.setEnabled(True)
        self.save_ai_btn.setVisible(False)

        # Lookup logic... (Eijiro lookup for the combined string)
        definition = lookup_word(combined_surface, combined_lemma)

        header = f"<h2>{combined_surface}</h2><hr>"
        self.dict_display.setHtml(header + self.format_definition(definition))

    def ask_ai(self):
        if not self.selection_list:
            return

        # Create a detailed breakdown for the AI
        details = [
            f"Token: {t['surface']} (Reading: {t['kana']}, POS: {t['pos']})"
            for t in self.selection_list
        ]
        combined_text = "".join([t["surface"] for t in self.selection_list])

        prompt = (
            f"You are a Japanese linguistic expert. Analyze this specific phrase: '{combined_text}'\n"
            f"Context: {self.input_area.toPlainText()}\n"
            f"Grammar Components:\n" + "\n".join(details) + "\n\n"
            "Please explain:\n"
            "1. The meaning of the combined phrase.\n"
            "2. How the individual tokens conjugate or connect (e.g., stem + auxiliary).\n"
            "3. Any specific nuance in this context.\n"
            "Use Markdown for formatting."
        )

        self.log_debug(f"AI Prompt Sent: {prompt}")
        self.progress_bar.setVisible(True)
        self.ai_btn.setEnabled(False)

        self.worker = AIWorker(prompt)
        self.worker.finished.connect(self.on_ai_response)
        self.worker.error.connect(self.on_ai_error)
        self.worker.start()

    def on_ai_response(self, response):
        self.log_debug(f"AI Response Received:\n{response}")
        self.progress_bar.setVisible(False)
        self.ai_btn.setEnabled(True)
        self.last_ai_response = response

        # Convert Markdown to HTML
        html_content = markdown.markdown(response)

        # Add some basic CSS to the HTML to make it look nice in the dark theme
        styled_html = f"""
        <style>
            b, strong {{ color: #536dfe; }}
            li {{ margin-bottom: 5px; }}
            code {{ background-color: #333; padding: 2px; }}
        </style>
        {html_content}
        """
        self.dict_display.append("<br><hr>")
        self.dict_display.append(styled_html)
        self.save_ai_btn.setVisible(True)

    def on_ai_error(self, err):
        self.log_debug(f"AI ERROR: {err}")
        self.progress_bar.setVisible(False)
        self.ai_btn.setEnabled(True)
        self.dict_display.append(f"<p style='color:red;'>{err}</p>")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = YomikataApp()
    window.show()
    sys.exit(app.exec())
