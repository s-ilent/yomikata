import re
import sys

import markdown
import qtawesome as qta
from PyQt6.QtCore import QDateTime, QSettings, Qt
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ai_worker import AIWorker
from database import DatabaseManager, init_db, lookup_word, save_to_personal_dict
from flow_layout import FlowLayout
from processor import TextProcessor
from style import DARK_STYLE
from widgets import PunctuationWidget, SettingsDialog, TokenWidget


class YomikataApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.selection_list = []  # List of selected token dicts
        self.debug_logs = []  # Store logs for the settings menu
        self.db = DatabaseManager()
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
            # Join all selected surfaces (e.g. "わかっ" + "た" = "ようになった")
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

        combined_surface = "".join([t["surface"] for t in self.selection_list])
        combined_kana = "".join([t["kana"] for t in self.selection_list])
        combined_romaji = "".join([t["romaji"] for t in self.selection_list])

        # Pull details from the first token if single, or combine if multi
        pos_list = ", ".join(set([t["pos"] for t in self.selection_list]))
        lemma_list = " + ".join(set([t["lemma"] for t in self.selection_list]))

        # RICH MARKDOWN HEADER
        markdown_text = f"""
# {combined_surface}
**Reading:** `{combined_kana}` | `{combined_romaji}`
**Lemma:** _{lemma_list}_ | **Type:** {pos_list}

---
"""
        # Fetch dictionary content
        extra_dicts = QSettings("Yomikata", "Settings").value("extra_dictionaries", [])
        raw_defs = lookup_word(combined_surface, lemma_list, extra_dicts)
        markdown_text += self.format_definition(raw_defs)

        # Render
        html = markdown.markdown(markdown_text, extensions=["extra"])
        self.dict_display.setHtml(self.apply_custom_css(html))
        self.ai_btn.setEnabled(True)

    def apply_custom_css(self, html):
        return f"""
        <style>
            h1 {{ color: #536dfe; font-size: 28px; margin-bottom: 0; }}
            h3 {{ color: #ff4081; border-bottom: 1px solid #333; padding-bottom: 5px; }}
            code {{ background-color: #2a2a2a; color: #ff4081; padding: 2px 4px; border-radius: 4px; }}
            strong {{ color: #e0e0e0; }}
            hr {{ border: 0; border-top: 1px solid #333; }}
        </style>
        {html}
        """

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