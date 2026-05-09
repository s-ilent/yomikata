from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
)

from ui.style import CATPPUCCIN_MOCHA as CAT


class GlossarySenseManager:
    """Tracks and increments sense numbering for consolidated dictionary cards."""

    def __init__(self):
        self.sense_count = 0

    def next_number(self):
        self.sense_count += 1
        return self.sense_count

    def reset(self):
        self.sense_count = 0


class BaseDictionaryCard(QFrame):
    """Base class for dictionary cards with consistent styling and sense management."""

    def __init__(self, source_label: str, content, accent_color: str, parent=None):
        super().__init__(parent)
        self.sense_manager = GlossarySenseManager()
        self.setStyleSheet(f"""
            QFrame {{
                background: {CAT['surface']};
                border-left: 4px solid {accent_color};
                border-radius: 6px;
                padding: 4px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(2)
        self.layout = layout

        # Source label - styled as superscript
        label = QLabel(source_label)
        label.setObjectName("SourceLabel")
        label.setStyleSheet(f"""
            QLabel#SourceLabel {{
                background: transparent;
                font-size: 10px;
                font-weight: bold;
                color: {accent_color};
                padding: 0;
                margin: 0;
            }}
        """)
        layout.addWidget(label)

        # Initial parse
        self.append_entry(content)

    def append_entry(self, entry_content):
        """Append new content using subclass-specific parsing logic."""
        # Base implementation - to be overridden by subclasses
        if isinstance(entry_content, str):
            self._parse_str_content(entry_content, self.layout)
        else:
            self._parse_dict_content(entry_content, self.layout)

    def _style_content_label(self, label):
        """Apply common styling to content labels."""
        label.setStyleSheet(f"""
            QLabel {{
                background: transparent;
                font-size: 14px;
                color: {CAT['foreground']};
            }}
        """)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)

    def _parse_dict_content(self, data, layout):
        # Implementation in subclasses
        pass

    def _parse_str_content(self, text, layout):
        for line in text.split('\n'):
            if line.strip():
                self._add_label(line, layout)

    def _add_label(self, text, layout):
        lbl = QLabel(text)
        self._style_content_label(lbl)
        layout.addWidget(lbl)


class MarkdownCard(BaseDictionaryCard):
    """Card for markdown-formatted personal notes."""

    def __init__(self, source_label, content, parent=None):
        super().__init__(source_label, content, CAT['mauve'], parent)
        self.setObjectName("MarkdownCard")

    def _style_content_label(self, label):
        super()._style_content_label(label)
        label.setTextFormat(Qt.TextFormat.MarkdownText)


class WordHeaderCard(QFrame):
    """Header card showing word, reading, lemma, POS."""

    def __init__(self, headword, reading, romaji, lemma, pos, parent=None):
        super().__init__(parent)
        self.setObjectName("WordHeaderCard")
        self.setStyleSheet(f"""
            QFrame#WordHeaderCard {{
                background: {CAT['surface']};
                border-left: 4px solid {CAT['red']};
                border-radius: 6px;
                padding: 8px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(4)

        # Headword (large, red)
        headword_label = QLabel(headword)
        headword_label.setObjectName("Headword")
        headword_label.setStyleSheet(f"""
            QLabel#Headword {{
                font-size: 24px;
                font-weight: bold;
                color: {CAT['red']};
            }}
        """)
        layout.addWidget(headword_label)

        # Reading (kana + romaji, cyan)
        reading_text = f"{reading} [{romaji}]" if romaji else reading
        reading_label = QLabel(reading_text)
        reading_label.setObjectName("Reading")
        reading_label.setStyleSheet(f"""
            QLabel#Reading {{
                font-size: 16px;
                color: {CAT['cyan']};
            }}
        """)
        layout.addWidget(reading_label)

        # Lemma + POS (green badges)
        if lemma or pos:
            meta_row = QLabel()
            meta_parts = []
            if lemma:
                meta_parts.append(f"Lemma: {lemma}")
            if pos:
                meta_parts.append(f"Type: {pos}")
            meta_row.setText(" | ".join(meta_parts))
            meta_row.setStyleSheet(f"""
                QLabel {{
                    font-size: 12px;
                    color: {CAT['green']};
                }}
            """)
            layout.addWidget(meta_row)


class YomitanCard(BaseDictionaryCard):
    """Card for Yomitan entries (mauve accent)."""

    def __init__(self, source_label, content, priority=None, parent=None):
        if priority and priority > 0:
            source_label = f"{source_label} ★{priority}"
        super().__init__(source_label, content, CAT['mauve'], parent)
        self.setObjectName("YomitanCard")

    def _parse_dict_content(self, data, layout):
        if data.get("type") == "structured-content":
            self._parse_list_content(data.get("content", []), layout)
            return

        # Glossary/List parsing
        if "glossary" in data or "content" in data:
            gloss = data.get("glossary") or data.get("content", [])
            if isinstance(gloss, list):
                self._parse_list_content(gloss, layout)

        for key, value in data.items():
            if key in ("type", "style", "data"): continue
            if isinstance(value, str): self._add_label(value, layout)
            elif isinstance(value, list): self._parse_list_content(value, layout)
            elif isinstance(value, dict): self._parse_dict_content(value, layout)

    def _parse_list_content(self, items, layout):
        for item in items:
            if isinstance(item, str) and item.strip(): self._add_label(item, layout)
            elif isinstance(item, dict): self._parse_dict_content(item, layout)
            elif isinstance(item, list): self._parse_list_content(item, layout)


class JMDictCard(BaseDictionaryCard):
    """Card for JMDict entries (blue accent)."""

    def __init__(self, source_label, content, parent=None):
        super().__init__(source_label, content, CAT['blue'], parent)
        self.setObjectName("JMDictCard")


class JMnedictCard(BaseDictionaryCard):
    """Card for JMnedict name entries (peach accent)."""

    def __init__(self, source_label, content, parent=None):
        super().__init__(source_label, content, CAT['peach'], parent)
        self.setObjectName("JMnedictCard")


class LegacyCard(BaseDictionaryCard):
    """Card for legacy Eijiro format."""

    def __init__(self, source_label, content, parent=None):
        super().__init__(source_label, content, CAT['surface_hover'], parent)
        self.setObjectName("LegacyCard")
        # Override hover effect
        self.setStyleSheet(f"""
            QFrame#LegacyCard {{
                background: {CAT['surface']};
                border-left: 4px solid {CAT['surface_hover']};
                border-radius: 6px;
                padding: 8px;
            }}
            QFrame#LegacyCard:hover {{
                border-left-color: {CAT['comment']};
            }}
        """)
