import argparse
import os
import re
import sys

import qtawesome as qta
from PyQt6.QtCore import QDateTime, Qt
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

from config import ConfigManager
from database import DatabaseManager
from dialogs.history_dialog import HistoryDialog
from dialogs.settings_dialog import SettingsDialog
from flow_layout import FlowLayout
from processor import TextProcessor
from services.ai_service import AIService
from services.dictionary_service import DictionaryService
from services.history_service import HistoryService
from style import CATPPUCCIN_MOCHA as CAT
from style import build_stylesheet, get_font_size
from widgets import (
    DictionaryCardStack,
    JMDictCard,
    JMnedictCard,
    LegacyCard,
    PunctuationWidget,
    TokenWidget,
    WordHeaderCard,
    YomitanCard,
)

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
        self.db_manager = DatabaseManager()
        self.dict_service = DictionaryService(self.db_manager)
        self.history_service = HistoryService(self.db_manager)
        self.ai_service = AIService()
        self.processor = TextProcessor()

        # Load font size preference
        self.config = ConfigManager()
        self.font_size = self.config.font_size

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

        # Dictionary display as card stack in scroll area
        dict_scroll = QScrollArea()
        dict_scroll.setWidgetResizable(True)
        dict_scroll.setStyleSheet("border: none;")

        self.card_stack = DictionaryCardStack()
        dict_scroll.setWidget(self.card_stack)

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
        self.ai_btn = QPushButton(" Ask AI")  # Added a space for icon padding
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
        self.progress_bar.setStyleSheet("QProgressBar::chunk { background-color: #3d5afe; }")
        self.progress_bar.setFixedHeight(4)

        dict_label = QLabel("<b>DICTIONARY REVEAL</b>")
        dict_label.setStyleSheet("background: transparent;")
        right_layout.addWidget(dict_label)
        right_layout.addLayout(search_layout)
        right_layout.addWidget(dict_scroll)
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
            if event.key() == Qt.Key.Key_Return and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                self.analyze_text()
                return True
        return super().eventFilter(obj, event)

    def format_definition(self, text):
        """Adds line breaks before special symbols and formats definitions nicely."""
        if not text:
            return ""
        # Convert single newlines to double to preserve line breaks in markdown
        text = re.sub(r"(?<!\n)\n(?!\n)", r"\n\n", text)
        # Also handle double-width spaces
        text = text.replace("　", " ")

        # Split into individual dictionary entries (separated by ### 📖)
        entries = re.split(r"(### 📖)", text)

        formatted_entries = []
        current_entry = ""

        for i, part in enumerate(entries):
            if not part.strip():
                continue
            if part == "### 📖":
                # Save previous entry
                if current_entry:
                    formatted_entries.append(self._format_single_entry(current_entry))
                current_entry = "### 📖"
                continue
            current_entry += part

        # Add last entry
        if current_entry:
            formatted_entries.append(self._format_single_entry(current_entry))

        return "\n\n".join(formatted_entries)

    def _format_single_entry(self, text):
        """Format a single dictionary entry with better spacing and structure."""
        # Add double break before our custom sense markers ◆X anywhere they appear
        text = re.sub(r"(◆[①②③④⑤⑥⑦⑧⑨⑩])", r"\n\n\1", text)
        # Break before bracketed numbers (e.g., 【1】 or (1))
        text = re.sub(r"([（\(【]\d+[】\)])", r"\n\n\1", text)
        # Break before numbered Japanese patterns like "1 〔...〕" or "1〔...〕"
        text = re.sub(r"(\d+\s*〔)", r"\n\n\1", text)
        # Break before patterns like "1)" after Japanese characters
        text = re.sub(r"([一-龥あ-んァ-ン])(\))", r"\1\n\n\2", text)
        # Also break on "1." "2." patterns in definitions
        text = re.sub(r"(\d+)\.\s+", r"\n\n\1. ", text)
        # Handle patterns like "1 言語" (number + space + Japanese)
        text = re.sub(r"(\n\d+\s+〔.+?\.)(\s*)(\d+\s+〔)", r"\1\n\n\3", text)

        # Clean up multiple line breaks
        text = re.sub(r"\n{3,}", "\n\n", text)

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
            max_entries = self.config.history_size
            self.history_service.save_history(text, max_entries)

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
        font_size = self.config.font_size
        history_size = self.config.history_size
        dialog = SettingsDialog(self, font_size, history_size, self.debug_logs)
        dialog.settings_saved.connect(self.apply_settings)
        dialog.exec()

    def apply_settings(self, font_size, history_size):
        # Apply the new settings
        self.update_font_size(font_size)
        self.log_debug(f"Settings applied: font_size={font_size}, history_size={history_size}")

    def show_history(self):
        """Show history dialog with previously analyzed texts."""
        max_entries = self.config.history_size
        entries = self.history_service.get_history(limit=max_entries)

        dialog = HistoryDialog(self, entries, self.font_size)
        dialog.text_selected.connect(self.restore_history_text)
        dialog.exec()

    def restore_history_text(self, text):
        """Restore text from history and analyze."""
        self.input_area.setPlainText(text)
        self.analyze_text()

    def update_font_size(self, size: int):
        """Update font size and regenerate stylesheet."""
        self.font_size = size
        self.config.font_size = size
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

            self.dict_service.save_personal_note(combined_surface, self.last_ai_response)

            # Show success as a card
            success_card = LegacyCard("Personal Note", f"✓ Saved '{combined_surface}' to personal dictionary!")
            self.card_stack.layout().insertWidget(self.card_stack.layout().count() - 1, success_card)
            self.save_ai_btn.setVisible(False)

    def edit_note(self):
        """Open a dialog to manually edit the personal note for the selected word."""
        if not self.selection_list:
            return

        combined_surface = "".join([t["surface"] for t in self.selection_list])

        # Get existing note if any
        existing = self.dict_service.get_personal_note(combined_surface)

        text, ok = QInputDialog.getMultiLineText(
            self,
            "Edit Personal Note",
            f"Note for '{combined_surface}' (Markdown supported):",
            existing or "",
        )
        if ok and text:
            self.dict_service.save_personal_note(combined_surface, text)
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

        # Clear existing cards from stack (including stretch)
        while self.card_stack.layout().count():
            child = self.card_stack.layout().takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # Add word header card
        header_card = WordHeaderCard(combined_surface, combined_kana, combined_romaji, lemma_list, pos_list)
        self.card_stack.layout().addWidget(header_card)

        # Fetch dictionary content using structured lookup
        extra_dicts = self.config.extra_dictionaries
        result = self.dict_service.lookup_structured(combined_surface, lemma_list, extra_dicts)

        # Create cards from structured entries (in normal order)
        for entry in result.get("entries", []):
            self._add_entry_card(entry)

        # Add stretch at the end
        self.card_stack.layout().addStretch()

        self.ai_btn.setEnabled(True)
        self.edit_note_btn.setEnabled(True)

    def _add_entry_card(self, entry: dict):
        """Create and add the appropriate card type for an entry."""
        source = entry.get("source", "Dictionary")
        content = entry.get("content", "")
        card_type = entry.get("card_type", "yomitan")
        priority = entry.get("priority", 0)

        if card_type == "jmdict":
            card = JMDictCard(source, content)
        elif card_type == "jmnedict":
            card = JMnedictCard(source, content)
        elif card_type == "legacy":
            card = LegacyCard(source, content)
        else:
            card = YomitanCard(source, content, priority)

        self.card_stack.layout().addWidget(card)

    def apply_custom_css(self, html):
        return f"""
        <style>
            body {{ font-family: 'Shippori Mincho', 'Noto Serif JP', serif; color: {CAT["foreground"]}; line-height: 1.6; }}
            h1 {{ color: {CAT["blue"]}; font-size: 24px; margin: 0 0 8px 0; font-weight: 600; letter-spacing: 0.05em; }}
            h2 {{ color: {CAT["mauve"]}; font-size: 16px; margin: 16px 0 4px 0; border-bottom: 1px solid {CAT["surface_hover"]}; padding-bottom: 4px; }}
            h3 {{ color: {CAT["cyan"]}; font-size: 14px; margin: 12px 0 4px 0; font-weight: 500; }}
            code {{ background-color: {CAT["surface"]}; color: {CAT["mauve"]}; padding: 2px 6px; border-radius: 3px; font-size: 0.95em; }}
            strong {{ color: {CAT["foreground"]}; font-weight: 600; }}
            hr {{ border: 0; border-top: 1px solid {CAT["surface_hover"]}; margin: 12px 0; }}
            a {{ color: {CAT["blue"]}; }}
            p {{ margin: 6px 0; }}
            ul, ol {{ margin: 4px 0; padding-left: 20px; }}
            li {{ margin: 2px 0; }}
            blockquote {{
                border-left: 3px solid {CAT["mauve"]};
                margin: 8px 0;
                padding-left: 12px;
                color: {CAT["comment"]};
            }}
            .pos-badge {{
                display: inline-block;
                background: {CAT["surface"]};
                color: {CAT["cyan"]};
                padding: 2px 8px;
                border-radius: 10px;
                font-size: 11px;
                font-family: sans-serif;
                margin-right: 6px;
            }}
            .dict-entry {{
                background: {CAT["surface"]};
                border-radius: 8px;
                padding: 12px 16px;
                margin: 8px 0;
            }}
            .dict-header {{
                display: flex;
                align-items: center;
                margin-bottom: 8px;
            }}
            .dict-source {{
                font-size: 11px;
                color: {CAT["comment"]};
                margin-left: auto;
            }}
        </style>
        {html}
        """

    def ask_ai(self):
        if not self.selection_list:
            return

        # Create details for the AI
        details = [f"Token: {t['surface']} (Reading: {t['kana']}, POS: {t['pos']})" for t in self.selection_list]
        combined_text = "".join([t["surface"] for t in self.selection_list])
        context = self.input_area.toPlainText()
        pos_list = ", ".join(set([t["pos"] for t in self.selection_list]))
        components = "\n".join(details)

        # Get selected template
        selected_template = self.ai_template.currentText()
        template = AI_TEMPLATES.get(selected_template, AI_TEMPLATES["Grammar Breakdown"])

        # Fill in template placeholders
        prompt_data = {
            "text": combined_text,
            "context": context,
            "components": components,
            "pos": pos_list,
        }
        prompt = self.ai_service.build_prompt(template, prompt_data)

        self.log_debug(f"AI Prompt Sent (mode: {selected_template}): {prompt[:200]}...")
        self.progress_bar.setVisible(True)
        self.ai_btn.setEnabled(False)

        self.ai_service.run_analysis(prompt, self.on_ai_response, self.on_ai_error)

    def on_ai_response(self, response):
        self.log_debug(f"AI Response Received:\n{response}")
        self.progress_bar.setVisible(False)
        self.ai_btn.setEnabled(True)
        self.last_ai_response = response

        # Display AI response as a card
        ai_card = LegacyCard("AI Notes", response)
        self.card_stack.layout().insertWidget(self.card_stack.layout().count() - 1, ai_card)
        self.save_ai_btn.setVisible(True)

    def on_ai_error(self, err):
        self.log_debug(f"AI ERROR: {err}")
        self.progress_bar.setVisible(False)
        self.ai_btn.setEnabled(True)
        error_card = LegacyCard("Error", err)
        self.card_stack.layout().insertWidget(self.card_stack.layout().count() - 1, error_card)

    def do_definition_search(self):
        """Search inside definitions using FTS5."""
        query = self.search_box.text().strip()
        if not query:
            return

        extra_dicts = self.config.extra_dictionaries
        results = self.dict_service.search_definitions(query, extra_dicts)

        # Clear cards and show search results
        while self.card_stack.layout().count():
            child = self.card_stack.layout().takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        search_card = LegacyCard(f"Search: {query}", results if results else "No matches found.")
        self.card_stack.layout().insertWidget(self.card_stack.layout().count() - 1, search_card)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Yomikata - Japanese Reading Assistant")
    parser.add_argument("--lookup", "-l", metavar="WORD", help="Lookup a word and exit")
    parser.add_argument(
        "--import-yomitan", "-i", nargs=2, metavar=("ZIPFILE", "TARGET.DB"), help="Import Yomitan ZIP to SQLite DB"
    )
    args = parser.parse_args()

    if args.import_yomitan:
        # CLI mode: import dictionary from ZIP or TXT
        path, target_db = args.import_yomitan
        if not os.path.exists(path):
            print(f"Error: File not found: {path}")
            sys.exit(1)

        from importer import import_dictionary_archive

        count = import_dictionary_archive(path, target_db)
        print(f"Done. Imported {count} entries to {target_db}")
        sys.exit(0)

    if args.lookup:
        # CLI mode: lookup and print result
        db = DatabaseManager()
        config = ConfigManager()
        extra_dicts = config.extra_dictionaries
        # lemma defaults to word when in CLI mode (no morphological analysis)
        result = db.lookup(args.lookup, args.lookup, extra_dicts)
        print(result or "No results found")
        sys.exit(0)

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
