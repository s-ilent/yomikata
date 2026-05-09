import argparse
import os
import sys

from PyQt6.QtCore import QDateTime, QObject, Qt
from PyQt6.QtGui import QFontDatabase
from PyQt6.QtWidgets import QApplication, QInputDialog

from controllers.ai_controller import AIController
from controllers.analysis_controller import AnalysisController
from core.config import ConfigManager
from core.database import DatabaseManager
from core.processor import TextProcessor
from dialogs.history_dialog import HistoryDialog
from dialogs.settings_dialog import SettingsDialog
from services.ai_service import AIService
from services.dictionary_service import DictionaryService
from services.history_service import HistoryService
from ui.card_factory import CardFactory
from ui.main_window import YomikataMainWindow
from ui.widgets.token_widgets import (
    PunctuationWidget,
    TokenWidget,
)
from utils.importer import import_dictionary_archive


class YomikataApp(QObject):
    def __init__(self):
        super().__init__()
        self.debug_logs = []  # Store logs for the settings menu
        self.db_manager = DatabaseManager()
        self.dict_service = DictionaryService(self.db_manager)
        self.history_service = HistoryService(self.db_manager)
        self.ai_service = AIService()
        self.ai_controller = AIController(self.ai_service)
        self.processor = TextProcessor()
        self.config = ConfigManager()
        self.analysis_controller = AnalysisController(
            self.processor, self.dict_service, self.history_service, self.config
        )
        self.font_size = self.config.font_size

        self.window = YomikataMainWindow(self.ai_controller)
        self.update_font_size(self.font_size)
        self._bind_ui()

    def _bind_ui(self):
        self.window.analyze_btn.clicked.connect(self.analyze_text)
        self.window.search_box.returnPressed.connect(self.do_definition_search)
        self.window.ai_btn.clicked.connect(self.ask_ai)
        self.window.save_ai_btn.clicked.connect(self.save_ai_to_dict)
        self.window.edit_note_btn.clicked.connect(self.edit_note)
        self.window.history_btn.clicked.connect(self.show_history)
        self.window.settings_btn.clicked.connect(self.open_settings)
        self.window.installEventFilter(self)

    def eventFilter(self, obj, event):
        if obj is self.window.input_area and event.type() == event.Type.KeyPress:
            if event.key() == Qt.Key.Key_Return and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                self.analyze_text()
                return True
        return super().eventFilter(obj, event)

    def analyze_text(self):
        text = self.window.input_area.toPlainText().strip()
        if not text:
            return

        while self.window.matrix_layout.count():
            item = self.window.matrix_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        tokens = self.analysis_controller.tokenize_text(text)
        punct_chars = "、。「」！？（）()., "

        for token in tokens:
            if token["surface"] in punct_chars or "記号" in token["pos"]:
                widget = PunctuationWidget(token["surface"])
                self.window.matrix_layout.addWidget(widget)
            else:
                card = TokenWidget(token)
                card.clicked.connect(self.handle_token_click)
                self.window.matrix_layout.addWidget(card)

    def open_settings(self):
        font_size = self.config.font_size
        history_size = self.config.history_size
        dialog = SettingsDialog(self.window, font_size, history_size, self.debug_logs)
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

        dialog = HistoryDialog(self.window, entries, self.font_size)
        dialog.text_selected.connect(self.restore_history_text)
        dialog.exec()

    def restore_history_text(self, text):
        """Restore text from history and analyze."""
        self.window.input_area.setPlainText(text)
        self.analyze_text()

    def update_font_size(self, size: int):
        """Update font size and regenerate stylesheet."""
        self.font_size = size
        self.config.font_size = size
        # Re-using internal main window styling
        from ui.style import build_stylesheet

        self.window.setStyleSheet(build_stylesheet(font_base=size))

    def log_debug(self, message):
        timestamp = QDateTime.currentDateTime().toString("hh:mm:ss")
        self.debug_logs.append(f"[{timestamp}] {message}")
        print(f"DEBUG: [{timestamp}] {message}")

    def handle_token_click(self, data, ctrl_held):
        # Find the widget that sent the signal
        sender = self.window.sender()
        result = self.analysis_controller.toggle_token_selection(data, ctrl_held)

        if not ctrl_held:
            for i in range(self.window.matrix_layout.count()):
                w = self.window.matrix_layout.itemAt(i).widget()
                if isinstance(w, TokenWidget):
                    w.set_highlight(False)
            sender.set_highlight(True)
        else:
            sender.set_highlight(result["action"] == "add")

        self.update_dictionary_view()

    def do_definition_search(self):
        """Search inside definitions using FTS5."""
        query = self.window.search_box.text().strip()
        if not query:
            return

        extra_dicts = self.config.extra_dictionaries
        results = self.dict_service.search_definitions(query, extra_dicts)

        # Clear cards and show search results
        while self.window.card_stack.layout().count():
            child = self.window.card_stack.layout().takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        from ui.widgets.cards import LegacyCard

        search_card = LegacyCard(f"Search: {query}", results if results else "No matches found.")
        self.window.card_stack.layout().insertWidget(self.window.card_stack.layout().count() - 1, search_card)

    def update_dictionary_view(self):
        if not self.analysis_controller.selection_list:
            return

        combined_surface, combined_kana, combined_romaji, pos_list, lemma_list = (
            self.analysis_controller.get_selection_info()
        )

        # Clear existing cards from stack
        while self.window.card_stack.layout().count():
            child = self.window.card_stack.layout().takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        from ui.widgets.cards import WordHeaderCard
        header_card = WordHeaderCard(combined_surface, combined_kana, combined_romaji, lemma_list, pos_list)
        self.window.card_stack.layout().addWidget(header_card)

        # Fetch dictionary content using structured lookup
        result = self.analysis_controller.lookup_selection()
        active_cards = {}  # {(source, card_type): card_instance}

        # Create/Populate cards from structured entries
        for entry in result.get("entries", []):
            source = entry.get("source", "Dictionary")
            card_type = entry.get("card_type", "yomitan")
            key = (source, card_type)

            if key not in active_cards:
                card = CardFactory.create(entry)
                active_cards[key] = card
                self.window.card_stack.layout().addWidget(card)
            else:
                active_cards[key].append_entry(entry.get("content"))

        # Add stretch at the end
        self.window.card_stack.layout().addStretch()

        self.window.ai_btn.setEnabled(True)
        self.window.edit_note_btn.setEnabled(True)

    def ask_ai(self):
        if not self.analysis_controller.selection_list:
            return

        # Create details for the AI
        details = [
            f"Token: {t['surface']} (Reading: {t['kana']}, POS: {t['pos']})"
            for t in self.analysis_controller.selection_list
        ]
        combined_text = "".join([t["surface"] for t in self.analysis_controller.selection_list])
        context = self.window.input_area.toPlainText()
        pos_list = ", ".join(set([t["pos"] for t in self.analysis_controller.selection_list]))
        components = "\n".join(details)

        # Get selected template
        selected_template = self.window.ai_template.currentText()

        # Fill in template placeholders
        prompt_data = {
            "text": combined_text,
            "context": context,
            "components": components,
            "pos": pos_list,
        }

        self.log_debug(f"AI Prompt Sent (mode: {selected_template})")
        self.window.progress_bar.setVisible(True)
        self.window.ai_btn.setEnabled(False)

        self.ai_controller.run_analysis(selected_template, prompt_data, self.on_ai_response, self.on_ai_error)

    def on_ai_response(self, response):
        self.log_debug(f"AI Response Received:\n{response}")
        self.window.progress_bar.setVisible(False)
        self.window.ai_btn.setEnabled(True)
        self.last_ai_response = response

        from ui.widgets.cards import LegacyCard

        # Display AI response as a card
        ai_card = LegacyCard("AI Notes", response)
        self.window.card_stack.layout().insertWidget(self.window.card_stack.layout().count() - 1, ai_card)
        self.window.save_ai_btn.setVisible(True)

    def on_ai_error(self, err):
        self.log_debug(f"AI ERROR: {err}")
        self.window.progress_bar.setVisible(False)
        self.window.ai_btn.setEnabled(True)
        from ui.widgets.cards import LegacyCard

        error_card = LegacyCard("Error", err)
        self.window.card_stack.layout().insertWidget(self.window.card_stack.layout().count() - 1, error_card)

    def save_ai_to_dict(self):
        """Modified to save the COMBINED phrase, not just one word."""
        if self.analysis_controller.selection_list and hasattr(self, "last_ai_response"):
            combined_surface = "".join([t["surface"] for t in self.analysis_controller.selection_list])
            self.dict_service.save_personal_note(combined_surface, self.last_ai_response)

            from ui.widgets.cards import LegacyCard

            success_card = LegacyCard("Personal Note", f"✓ Saved '{combined_surface}' to personal dictionary!")
            self.window.card_stack.layout().insertWidget(self.window.card_stack.layout().count() - 1, success_card)
            self.window.save_ai_btn.setVisible(False)

    def edit_note(self):
        """Open a dialog to manually edit the personal note for the selected word."""
        if not self.analysis_controller.selection_list:
            return

        combined_surface = "".join([t["surface"] for t in self.analysis_controller.selection_list])

        # Get existing note if any
        existing = self.dict_service.get_personal_note(combined_surface)

        text, ok = QInputDialog.getMultiLineText(
            self.window,
            "Edit Personal Note",
            f"Note for '{combined_surface}' (Markdown supported):",
            existing or "",
        )
        if ok and text:
            self.dict_service.save_personal_note(combined_surface, text)
            self.update_dictionary_view()


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

        from utils.importer import import_dictionary_archive

        count = import_dictionary_archive(path, target_db)
        print(f"Done. Imported {count} entries to {target_db}")
        sys.exit(0)

    if args.lookup:
        # CLI mode: lookup and print result
        from core.database import DatabaseManager

        db = DatabaseManager()
        config = ConfigManager()
        extra_dicts = config.extra_dictionaries
        # lemma defaults to word when in CLI mode (no morphological analysis)
        result = db.lookup(args.lookup, args.lookup, extra_dicts)
        print(result or "No results found")
        sys.exit(0)

    app = QApplication(sys.argv)
    app.setOrganizationName("Yomikata")
    app.setApplicationName("Settings")

    # Load custom fonts
    font_dir = os.path.join(os.path.dirname(__file__), "..", "fonts")
    if os.path.exists(font_dir):
        for font_file in os.listdir(font_dir):
            if font_file.endswith(".ttf") or font_file.endswith(".otf"):
                QFontDatabase.addApplicationFont(os.path.join(font_dir, font_file))

    app_instance = YomikataApp()
    app_instance.window.show()
    sys.exit(app.exec())
