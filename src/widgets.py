from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtCore import pyqtSignal as QtSignal
from PyQt6.QtGui import QCursor, QFont, QFontMetrics, QPainter
from PyQt6.QtWidgets import (
    QFrame,
    QLabel,
    QSizePolicy,
    QStyle,
    QStyleOption,
    QVBoxLayout,
)

from core.database import import_dictionary_file, import_yomitan_zip
from style import CATPPUCCIN_MOCHA as CAT


class ImportWorker(QThread):
    progress = QtSignal(int)
    finished = QtSignal(int)
    error = QtSignal(str)

    def __init__(self, source_path, target_db_path, import_format="Text (Eijiro)"):
        super().__init__()
        self.source_path = source_path
        self.target_db_path = target_db_path
        self.import_format = import_format

    def run(self):
        try:
            import sys
            debug_logs = []
            def debug_cb(msg):
                debug_logs.append(msg)
                print(f"IMPORT: {msg}", file=sys.stderr)

            if self.import_format == "Yomitan (ZIP)":
                count = import_yomitan_zip(
                    self.source_path,
                    self.target_db_path,
                    lambda p, t: self.progress.emit(int((p/t)*100)) if t > 0 else None
                )
            else:
                count = import_dictionary_file(
                    self.source_path,
                    self.target_db_path,
                    lambda p: self.progress.emit(p % 101), # Simple progress for now
                    debug_cb
                )

            self.finished.emit(count)
            # Send debug logs to parent if possible
            if self.parent() and hasattr(self.parent(), "debug_logs"):
                self.parent().debug_logs.extend(debug_logs)
        except Exception as e:
            self.error.emit(str(e))


class PunctuationWidget(QLabel):
    """Small, non-clickable widget for 、。！？ etc."""

    def __init__(self, text):
        super().__init__(text)
        self.setStyleSheet(
            f"font-size: 20px; color: {CAT['foreground']}; padding: 0px 5px; margin-top: 15px;"
        )
        self.setAlignment(Qt.AlignmentFlag.AlignBottom)


class TokenWidget(QFrame):
    clicked = pyqtSignal(dict, bool)  # Added bool for Ctrl-click status

    def __init__(self, token_data):
        super().__init__()
        self.setObjectName("TokenCard")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.data = token_data
        self.is_selected = False  # Tracking state

        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 4, 2, 4) # Reduced margins
        layout.setSpacing(0)

        # Labels
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
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        # Accurate width calculation matching CSS exactly
        f_romaji = QFont(); f_romaji.setPixelSize(10)
        f_kana = QFont(); f_kana.setPixelSize(12); f_kana.setBold(True)
        f_surface = QFont(); f_surface.setPixelSize(20); f_surface.setWeight(QFont.Weight.Medium)

        w_romaji = QFontMetrics(f_romaji).horizontalAdvance(token_data["romaji"])
        w_kana = QFontMetrics(f_kana).horizontalAdvance(token_data["kana"])
        w_surface = QFontMetrics(f_surface).horizontalAdvance(token_data["surface"])

        # Reduced padding (total horizontal padding: 8px)
        width = max(w_romaji, w_kana, w_surface) + 8
        self.setFixedWidth(max(20, width))

    def set_highlight(self, state):
        self.is_selected = state
        self.setProperty("selected", state)
        self.style().unpolish(self)
        self.style().polish(self)

    def paintEvent(self, event):
        opt = QStyleOption()
        opt.initFrom(self)
        p = QPainter(self)
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_Widget, opt, p, self)

    def mousePressEvent(self, event):
        # Check if Control key is held
        ctrl_held = event.modifiers() & Qt.KeyboardModifier.ControlModifier
        self.clicked.emit(self.data, bool(ctrl_held))


# ===== Dictionary Card Widgets =====

class DictionaryCardStack(QFrame):
    """Container widget for stacking dictionary cards."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DictionaryCardStack")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addStretch()
        self.setStyleSheet("""
            QFrame#DictionaryCardStack {
                background: transparent;
            }
        """)


class BaseDictionaryCard(QFrame):
    """Base class for dictionary cards with consistent styling."""

    def __init__(self, source_label: str, content, accent_color: str, parent=None):
        # content can be: dict, list, or str
        super().__init__(parent)
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

        # Parse content and build native widgets
        if content is None:
            content = "No definitions"

        if isinstance(content, dict):
            self._parse_dict_content(content, layout)
        elif isinstance(content, list):
            self._parse_list_content(content, layout)
        elif isinstance(content, str):
            self._parse_str_content(content, layout)
        else:
            lbl = QLabel(str(content))
            self._style_content_label(lbl)
            layout.addWidget(lbl)

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
        """Parse Yomitan structured-content dict and build widgets."""
        # Handle Yomitan structure: type="structured-content" with content=[]
        if data.get("type") == "structured-content":
            content_list = data.get("content", [])
            self._parse_list_content(content_list, layout)
            return

        # Handle glossary list style (numbered senses)
        style = data.get("style", {})
        list_style = style.get("listStyleType", "")
        if list_style.startswith('"'):
            number = list_style.strip('"').strip()
            # Find glossary content
            content = data.get("content", [])
            for item in content:
                if isinstance(item, dict) and item.get("data", {}).get("content") == "glossary":
                    self._add_label(f"◆{number}", layout)
                    self._parse_dict_content(item, layout)
                    return

        # Handle glossary key
        if "glossary" in data or "content" in data:
            gloss = data.get("glossary") or data.get("content", [])
            if isinstance(gloss, list):
                for item in gloss:
                    if isinstance(item, str):
                        self._add_label(item, layout)
                    elif isinstance(item, dict):
                        self._parse_dict_content(item, layout)

        # Generic: iterate through dict values
        for key, value in data.items():
            if key in ("type", "style", "data"):
                continue
            if isinstance(value, str) and value.strip():
                self._add_label(value, layout)
            elif isinstance(value, list):
                self._parse_list_content(value, layout)
            elif isinstance(value, dict):
                self._parse_dict_content(value, layout)

    def _parse_list_content(self, items, layout):
        """Parse list content and build widgets."""
        for item in items:
            if isinstance(item, str) and item.strip():
                self._add_label(item, layout)
            elif isinstance(item, dict):
                self._parse_dict_content(item, layout)
            elif isinstance(item, list):
                self._parse_list_content(item, layout)

    def _parse_str_content(self, text, layout):
        """Parse plain text content."""
        for line in text.split('\n'):
            if line.strip():
                self._add_label(line, layout)

    def _add_label(self, text, layout):
        """Create and add a content label."""
        lbl = QLabel(text)
        self._style_content_label(lbl)
        layout.addWidget(lbl)


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


class JMDictCard(BaseDictionaryCard):
    """Card for JMDict entries (blue accent)."""

    def __init__(self, source_label, content, parent=None):
        super().__init__(source_label, content, CAT['blue'], parent)
        self.setObjectName("JMDictCard")


class YomitanCard(BaseDictionaryCard):
    """Card for Yomitan entries (mauve accent)."""

    def __init__(self, source_label, content, priority=None, parent=None):
        # Call parent with priority indicator in label
        if priority and priority > 0:
            source_label = f"{source_label} ★{priority}"
        super().__init__(source_label, content, CAT['mauve'], parent)
        self.setObjectName("YomitanCard")


class JMnedictCard(BaseDictionaryCard):
    """Card for JMnedict name entries (peach accent)."""

    def __init__(self, source_label, content, parent=None):
        super().__init__(source_label, content, CAT['peach'], parent)
        self.setObjectName("JMnedictCard")


class LegacyCard(BaseDictionaryCard):
    """Card for legacy Eijiro format (surface hover accent)."""

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
