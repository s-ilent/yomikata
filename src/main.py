import os
import re
import sys

import markdown
import qtawesome as qta
from PyQt6.QtCore import QDateTime, QSettings, Qt
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtGui import QFontDatabase
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
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
from database import (
    DatabaseManager,
    get_personal_note,
    get_history,
    lookup_word,
    save_history,
    save_to_personal_dict,
    search_definitions,
)
from flow_layout import FlowLayout
from processor import TextProcessor
from style import build_stylesheet, get_font_size, CATPPUCCIN_MOCHA as CAT
from widgets import PunctuationWidget, SettingsDialog, TokenWidget

# AI Prompt Templates
AI_TEMPLATES = {
    "Grammar Breakdown": (
        "You are a Japanese linguistic expert. Analyze this specific phrase: '{text}'\n"
        "Context: {context}\n"
        "Grammar Components:\n{components}\n\n"
        "Please explain:\n"
        "1. The meaning of the combined phrase.\n"
        "2. How the individual tokens conjugate or connect (e.g., stem + auxiliary).\n"
        "3. Any specific nuance in this context.\n"
        "Use Markdown for formatting."
    ),
    "Example Sentences": (
        "You are a Japanese language expert. Provide example sentences using: '{text}'\n"
        "Context from user's text: {context}\n\n"
        "Please provide:\n"
        "1. 3-5 example sentences using this word/phrase in different contexts.\n"
        "2. For each sentence, provide: Japanese, romaji reading, and English translation.\n"
        "3. Briefly explain the grammar pattern used in each example.\n"
        "Use Markdown for formatting."
    ),
    "Etymology": (
        "You are a Japanese language historian. Analyze the etymology of: '{text}'\n"
        "Part of speech: {pos}\n\n"
        "Please explain:\n"
        "1. The kanji composition (if any) and their individual meanings.\n"
        "2. Historical origin and how the word evolved.\n"
        "3. Any interesting linguistic notes about this word.\n"
        "4. Related words or compounds that share the same kanji/roots.\n"
        "Use Markdown for formatting."
    ),
    "Conjugation": (
        "You are a Japanese grammar expert. Provide a complete conjugation table for: '{text}'\n"
        "Part of speech: {pos}\n\n"
        "Please provide:\n"
        "1. All basic conjugations: dictionary, past, negative, polite (ます), te-form, potential, passive, causative, conditional.\n"
        "2. For verbs: include masu-stem, te-stem, ra-stem variations.\n"
        "3. Explain any irregular conjugations.\n"
        "Use Markdown tables for the conjugation chart."
    ),
    "Compare/Contrast": (
        "You are a Japanese language expert. Compare and contrast: '{text}'\n"
        "Context: {context}\n"
        "Part of speech: {pos}\n\n"
        "Please explain:\n"
        "1. What this word/phrase means and its key characteristics.\n"
        "2. Common synonyms and how they differ in usage.\n"
        "3. Words that are often confused with this one and why.\n"
        "4. Tips for distinguishing between them.\n"
        "Use Markdown for formatting."
    ),
}


class YomikataApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.selection_list = []  # List of selected token dicts
        self.debug_logs = []  # Store logs for the settings menu
        self.db = DatabaseManager()
        self.processor = TextProcessor()
        
        # Load font size preference
        self.settings = QSettings("Yomikata", "Settings")
        self.font_size = int(self.settings.value("font_size", 14))
        
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Yomikata Japanese Assistant")
        self.resize(1200, 850)
        self.setStyleSheet(build_stylesheet(font_base=self.font_size))

        self.splitter = QSplitter(Qt.Orientation.Horizontal)

        # --- LEFT SIDE (Reading & Input) ---
        left_container = QWidget()
        left_container.setObjectName("leftPanel")
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
        right_container.setObjectName("rightPanel")
        right_layout = QVBoxLayout(right_container)

        self.dict_display = QTextEdit()
        self.dict_display.setReadOnly(True)

        # Search box for FTS
        search_layout = QHBoxLayout()
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search definitions...")
        self.search_box.returnPressed.connect(self.do_definition_search)
        search_btn = QPushButton()
        search_btn.setIcon(qta.icon("fa5s.search", color="white"))
        search_btn.setFixedSize(40, 40)
        search_btn.setToolTip("Search")
        search_btn.clicked.connect(self.do_definition_search)
        search_layout.addWidget(self.search_box)
        search_layout.addWidget(search_btn)
        search_btn.setObjectName("primary-btn")
        search_btn.setStyleSheet("padding: 0;")

        # --- AI and Settings Buttons ---
        ai_controls_layout = QHBoxLayout()

        # AI Template selector
        self.ai_template = QComboBox()
        self.ai_template.addItems(
            [
                "Grammar Breakdown",
                "Example Sentences",
                "Etymology",
                "Conjugation",
                "Compare/Contrast",
            ]
        )
        self.ai_template.setToolTip("Select analysis mode")
        self.ai_template.setFixedHeight(40)

        # Main AI Button
        self.ai_btn = QPushButton(" Ask AI Sensei")  # Added a space for icon padding
        self.ai_btn.setIcon(qta.icon("fa5s.robot", color="white"))  # Robot icon!
        self.ai_btn.clicked.connect(self.ask_ai)
        self.ai_btn.setEnabled(False)
        self.ai_btn.setMinimumHeight(40)
        self.ai_btn.setObjectName("AnalyzeBtn")  # Reusing the blue style

        ai_controls_layout.addWidget(self.ai_template, stretch=2)
        ai_controls_layout.addWidget(self.ai_btn, stretch=3)  # Takes up most space

        self.save_ai_btn = QPushButton("Save AI to Personal Dict")
        self.save_ai_btn.setIcon(qta.icon("fa5s.save", color="white"))
        self.save_ai_btn.clicked.connect(self.save_ai_to_dict)
        self.save_ai_btn.setVisible(False)  # Hide it until AI responds
        self.save_ai_btn.setObjectName("success-btn")

        self.edit_note_btn = QPushButton("Edit Note")
        self.edit_note_btn.setIcon(qta.icon("fa5s.edit", color="white"))
        self.edit_note_btn.clicked.connect(self.edit_note)
        self.edit_note_btn.setEnabled(False)
        self.edit_note_btn.setObjectName("secondary-btn")
        self.edit_note_btn.setMinimumHeight(40)

        self.history_btn = QPushButton()
        self.history_btn.setIcon(qta.icon("fa5s.clock", color="white"))
        self.history_btn.setFixedSize(40, 40)
        self.history_btn.setToolTip("History")
        self.history_btn.clicked.connect(self.show_history)
        self.history_btn.setObjectName("secondary-btn")
        self.history_btn.setStyleSheet("padding: 0;")

        self.settings_btn = QPushButton()
        self.settings_btn.setIcon(qta.icon("fa5s.cog", color="white"))
        self.settings_btn.setFixedSize(40, 40)
        self.settings_btn.setToolTip("Settings")
        self.settings_btn.clicked.connect(self.open_settings)
        self.settings_btn.setObjectName("secondary-btn")
        self.settings_btn.setStyleSheet("padding: 0;")
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Indeterminate "pulser"
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet(
            "QProgressBar::chunk { background-color: #3d5afe; }"
        )
        self.progress_bar.setFixedHeight(4)

        dict_label = QLabel("<b>DICTIONARY REVEAL</b>")
        dict_label.setStyleSheet("background: transparent;")
        right_layout.addWidget(dict_label)
        right_layout.addLayout(search_layout)
        right_layout.addWidget(self.dict_display)
        right_layout.addLayout(ai_controls_layout)

        # Note buttons row
        note_btn_layout = QHBoxLayout()
        note_btn_layout.addWidget(self.save_ai_btn)
        note_btn_layout.addWidget(self.edit_note_btn, stretch=1)
        note_btn_layout.addWidget(self.history_btn)
        note_btn_layout.addWidget(self.settings_btn)
        right_layout.addLayout(note_btn_layout)

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
                and event.modifiers() & Qt.KeyboardModifier.ControlModifier
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

        # Save to history before processing
        if text:
            max_entries = int(self.settings.value("history_size", 50))
            save_history(text, max_entries)

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

    def show_history(self):
        """Show history dialog with previously analyzed texts."""
        from PyQt6.QtWidgets import (
            QDialog, QVBoxLayout, QPushButton, QHBoxLayout,
            QScrollArea, QFrame, QLabel, QSizePolicy
        )
        from PyQt6.QtCore import Qt

        # Get max history entries from settings (default 50)
        max_entries = int(self.settings.value("history_size", 50))
        entries = get_history(limit=max_entries)

        dialog = QDialog(self)
        dialog.setWindowTitle("Text History")
        dialog.resize(700, 500)

        # Apply catppuccin styling
        dialog.setStyleSheet(f"""
            QDialog {{
                background-color: {CAT["background"]};
                color: {CAT["foreground"]};
            }}
            QScrollArea {{
                background-color: transparent;
                border: none;
            }}
            QPushButton {{
                background-color: {CAT["surface"]};
                color: {CAT["foreground"]};
                border: 1px solid {CAT["surface_hover"]};
                border-radius: 4px;
                padding: 8px 16px;
            }}
            QPushButton:hover {{
                background-color: {CAT["surface_hover"]};
            }}
        """)

        layout = QVBoxLayout(dialog)

        # Scroll area with history cards
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none;")

        # Container for history cards
        cards_container = QWidget()
        cards_layout = QVBoxLayout(cards_container)
        cards_layout.setSpacing(10)
        cards_layout.addStretch()

        # Create a card for each history entry
        entry_map = {}  # Map card widget to original text

        for text, timestamp in entries:
            # Create card frame
            card = QFrame()
            card.setFrameShape(QFrame.Shape.StyledPanel)
            card.setStyleSheet(f"""
                QFrame {{
                    background-color: {CAT["surface"]};
                    border: 1px solid {CAT["surface_hover"]};
                    border-radius: 6px;
                    padding: 10px;
                }}
                QFrame:hover {{
                    border: 1px solid {CAT["selection"]};
                }}
            """)
            card.setCursor(Qt.CursorShape.PointingHandCursor)

            card_layout = QVBoxLayout(card)

            # Timestamp label (smaller, muted)
            ts_label = QLabel(str(timestamp))
            ts_label.setStyleSheet(f"color: {CAT['comment']}; font-size: 11px;")
            card_layout.addWidget(ts_label)

            # Text content (with word wrap)
            text_label = QLabel(text)
            text_label.setStyleSheet(f"color: {CAT['foreground']}; font-size: {self.font_size}px;")
            text_label.setWordWrap(True)
            text_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            card_layout.addWidget(text_label)

            cards_layout.insertWidget(cards_layout.count() - 1, card)
            entry_map[card] = text

            # Click handler
            card.mousePressEvent = lambda event, t=text, w=card: self._on_history_card_click(t, w, dialog)

        scroll.setWidget(cards_container)
        layout.addWidget(scroll, stretch=1)

        # Close button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.close)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

        dialog.exec()

    def _on_history_card_click(self, text, card_widget, dialog):
        """Handle history card click - restore text and analyze."""
        self.input_area.setPlainText(text)
        self.analyze_text()  # Automatically analyze
        dialog.close()

    def update_font_size(self, size: int):
        """Update font size and regenerate stylesheet."""
        self.font_size = size
        self.settings.setValue("font_size", size)
        self.setStyleSheet(build_stylesheet(font_base=size))
        # Update token display sizes
        self._update_token_font_sizes()

    def _update_token_font_sizes(self):
        """Update font sizes in existing token widgets."""
        kanji_size = get_font_size("kanji", self.font_size)
        kana_size = get_font_size("kana", self.font_size)
        romaji_size = get_font_size("romaji", self.font_size)

        for i in range(self.matrix_layout.count()):
            widget = self.matrix_layout.itemAt(i).widget()
            if widget and isinstance(widget, TokenWidget):
                widget.romaji_lbl.setStyleSheet(f"font-size: {romaji_size}px; color: #6272a4;")
                widget.kana_lbl.setStyleSheet(f"font-size: {kana_size}px; font-weight: bold; color: #8be9fd;")
                widget.surface_lbl.setStyleSheet(f"font-size: {kanji_size}px; font-weight: 500; color: #f8f8f2;")

    def save_ai_to_dict(self):
        """Modified to save the COMBINED phrase, not just one word."""
        if self.selection_list and hasattr(self, "last_ai_response"):
            # Join all selected surfaces (e.g. "わかっ" + "た" = "ようになった")
            combined_surface = "".join([t["surface"] for t in self.selection_list])

            save_to_personal_dict(combined_surface, self.last_ai_response)

            self.dict_display.append(
                f"<br><i style='color:{CAT["green"]};'>✓ Saved '{combined_surface}' to personal dictionary!</i>"
            )
            self.save_ai_btn.setVisible(False)

    def edit_note(self):
        """Open a dialog to manually edit the personal note for the selected word."""
        if not self.selection_list:
            return

        combined_surface = "".join([t["surface"] for t in self.selection_list])

        # Get existing note if any
        existing = get_personal_note(combined_surface)

        text, ok = QInputDialog.getMultiLineText(
            self,
            "Edit Personal Note",
            f"Note for '{combined_surface}' (Markdown supported):",
            existing or "",
        )
        if ok and text:
            save_to_personal_dict(combined_surface, text)
            self.dict_display.append(
                f"<br><i style='color:{CAT["green"]};'>✓ Note saved for '{combined_surface}'</i>"
            )
            self.update_dictionary_view()

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
        self.edit_note_btn.setEnabled(True)

    def apply_custom_css(self, html):
        return f"""
        <style>
            body {{ font-family: 'Shippori Mincho', serif; color: {CAT["foreground"]}; }}
            h1 {{ color: {CAT["blue"]}; font-size: 28px; margin-bottom: 0; }}
            h3 {{ color: {CAT["mauve"]}; border-bottom: 1px solid {CAT["surface_hover"]}; padding-bottom: 5px; }}
            code {{ background-color: {CAT["surface"]}; color: {CAT["mauve"]}; padding: 2px 4px; border-radius: 4px; }}
            strong {{ color: {CAT["foreground"]}; }}
            hr {{ border: 0; border-top: 1px solid {CAT["surface_hover"]}; }}
            a {{ color: {CAT["blue"]}; }}
        </style>
        {html}
        """

    def ask_ai(self):
        if not self.selection_list:
            return

        # Create details for the AI
        details = [
            f"Token: {t['surface']} (Reading: {t['kana']}, POS: {t['pos']})"
            for t in self.selection_list
        ]
        combined_text = "".join([t["surface"] for t in self.selection_list])
        context = self.input_area.toPlainText()
        pos_list = ", ".join(set([t["pos"] for t in self.selection_list]))
        components = "\n".join(details)

        # Get selected template
        selected_template = self.ai_template.currentText()
        template = AI_TEMPLATES.get(
            selected_template, AI_TEMPLATES["Grammar Breakdown"]
        )

        # Fill in template placeholders
        prompt = template.format(
            text=combined_text, context=context, components=components, pos=pos_list
        )

        self.log_debug(f"AI Prompt Sent (mode: {selected_template}): {prompt[:200]}...")
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
            b, strong {{ color: {CAT["blue"]}; }}
            li {{ margin-bottom: 5px; }}
            code {{ background-color: {CAT["surface"]}; padding: 2px; }}
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
        self.dict_display.append(f"<p style='color:{CAT["red"]};'>{err}</p>")

    def do_definition_search(self):
        """Search inside definitions using FTS5."""
        query = self.search_box.text().strip()
        if not query:
            return

        extra_dicts = QSettings("Yomikata", "Settings").value("extra_dictionaries", [])
        results = search_definitions(query, extra_dicts)

        markdown_text = f"# Search: {query}\n\n"
        if results:
            markdown_text += results
        else:
            markdown_text += "_No matches found in definitions._"

        html = markdown.markdown(markdown_text, extensions=["extra"])
        self.dict_display.setHtml(self.apply_custom_css(html))


if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Load custom fonts
    font_dir = os.path.join(os.path.dirname(__file__), "..", "fonts")
    if os.path.exists(font_dir):
        for font_file in os.listdir(font_dir):
            if font_file.endswith(".ttf") or font_file.endswith(".otf"):
                QFontDatabase.addApplicationFont(os.path.join(font_dir, font_file))

    window = YomikataApp()
    window.show()
    sys.exit(app.exec())
