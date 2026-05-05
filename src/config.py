from PyQt6.QtCore import QSettings


class ConfigManager:
    """Centralized configuration manager for Yomikata."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.settings = QSettings("Yomikata", "Settings")
        return cls._instance

    def get(self, key, default=None):
        return self.settings.value(key, default)

    def set(self, key, value):
        self.settings.setValue(key, value)

    @property
    def font_size(self) -> int:
        return int(self.get("font_size", 14))

    @font_size.setter
    def font_size(self, value: int):
        self.set("font_size", value)

    @property
    def history_size(self) -> int:
        return int(self.get("history_size", 50))

    @history_size.setter
    def history_size(self, value: int):
        self.set("history_size", value)

    @property
    def ai_provider(self) -> str:
        return str(self.get("ai_provider", "Ollama"))

    @property
    def ai_model(self) -> str:
        return str(self.get("ai_model", "llama3"))

    @property
    def extra_dictionaries(self) -> list:
        return self.get("extra_dictionaries", [])

    def add_extra_dictionary(self, path: str):
        dicts = self.extra_dictionaries
        if path not in dicts:
            dicts.append(path)
            self.set("extra_dictionaries", dicts)

    def remove_extra_dictionary(self, path: str):
        dicts = self.extra_dictionaries
        if path in dicts:
            dicts.remove(path)
            self.set("extra_dictionaries", dicts)

    def set_extra_dictionaries(self, dicts: list):
        """Replace the entire extra_dictionaries list (for reordering)."""
        self.set("extra_dictionaries", dicts)
