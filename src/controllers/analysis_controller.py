import re

from config import ConfigManager
from processor import TextProcessor
from services.dictionary_service import DictionaryService
from services.history_service import HistoryService


class AnalysisController:
    def __init__(self, processor: TextProcessor, dict_service: DictionaryService, history_service: HistoryService, config: ConfigManager):
        self.processor = processor
        self.dict_service = dict_service
        self.history_service = history_service
        self.config = config
        self.selection_list = []

    def tokenize_text(self, text):
        # Save to history before processing
        max_entries = self.config.history_size
        self.history_service.save_history(text, max_entries)
        return self.processor.tokenize(text)

    def toggle_token_selection(self, token, ctrl_held):
        if not ctrl_held:
            self.selection_list = [token]
            return {"action": "replace", "token": token}
        else:
            if token in self.selection_list:
                self.selection_list.remove(token)
                return {"action": "remove", "token": token}
            else:
                self.selection_list.append(token)
                return {"action": "add", "token": token}

    def get_selection_info(self):
        surface = "".join([t["surface"] for t in self.selection_list])
        kana = "".join([t["kana"] for t in self.selection_list])
        romaji = "".join([t["romaji"] for t in self.selection_list])
        pos = ", ".join(set([t["pos"] for t in self.selection_list]))
        lemma = " + ".join(set([t["lemma"] for t in self.selection_list]))
        return surface, kana, romaji, pos, lemma

    def lookup_selection(self):
        surface, _, _, _, lemma = self.get_selection_info()
        return self.dict_service.lookup_structured(surface, lemma, self.config.extra_dictionaries)

    def format_definition(self, text):
        if not text: return ""
        text = re.sub(r"(?<!\n)\n(?!\n)", r"\n\n", text)
        text = text.replace("　", " ")
        entries = re.split(r"(### 📖)", text)
        formatted_entries = []
        current_entry = ""
        for part in entries:
            if not part.strip(): continue
            if part == "### 📖":
                if current_entry: formatted_entries.append(self._format_single_entry(current_entry))
                current_entry = "### 📖"
                continue
            current_entry += part
        if current_entry: formatted_entries.append(self._format_single_entry(current_entry))
        return "\n\n".join(formatted_entries)

    def _format_single_entry(self, text):
        text = re.sub(r"(◆[①②③④⑤⑥⑦⑧⑨⑩])", r"\n\n\1", text)
        text = re.sub(r"([（\(【]\d+[】\)])", r"\n\n\1", text)
        text = re.sub(r"(\d+\s*〔)", r"\n\n\1", text)
        text = re.sub(r"([一-龥あ-んァ-ン])(\))", r"\1\n\n\2", text)
        text = re.sub(r"(\d+)\.\s+", r"\n\n\1. ", text)
        text = re.sub(r"(\n\d+\s+〔.+?\.)(\s*)(\d+\s+〔)", r"\1\n\n\3", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text
