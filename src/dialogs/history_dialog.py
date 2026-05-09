from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ui.style import CATPPUCCIN_MOCHA as CAT


class HistoryDialog(QDialog):
    text_selected = pyqtSignal(str)

    def __init__(self, parent=None, entries=None, font_size=14):
        super().__init__(parent)
        self.setWindowTitle("Text History")
        self.resize(700, 500)
        self.font_size = font_size

        # Apply catppuccin styling
        self.setStyleSheet(f"""
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

        layout = QVBoxLayout(self)

        # Hover/selected styling for history cards and their labels
        # Using class/nth selectors to avoid cascading QFrame rules to child QLabels
        self.card_style = f"""
            QFrame#HistoryCard {{
                background-color: {CAT["surface"]};
                border: 1px solid {CAT["surface_hover"]};
                border-radius: 6px;
            }}
            QFrame#HistoryCard:hover {{
                border: 1px solid {CAT["selection"]};
            }}
            QLabel#HistoryTimestamp {{
                color: {CAT["comment"]};
                font-size: 11px;
            }}
            QLabel#HistoryText {{
                color: {CAT["foreground"]};
                font-size: {self.font_size}px;
            }}
        """

        # Scroll area with history cards
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none;")

        # Container for history cards
        cards_container = QWidget()
        cards_layout = QVBoxLayout(cards_container)
        cards_layout.setSpacing(10)
        cards_layout.addStretch()

        if entries:
            for entry in entries:
                text = entry.get("text", "")
                timestamp = entry.get("timestamp", "")
                # Card frame with visual hover indication
                card = QFrame()
                card.setObjectName("HistoryCard")
                card.setStyleSheet(self.card_style)
                card.setCursor(Qt.CursorShape.PointingHandCursor)

                card_layout = QVBoxLayout(card)
                card_layout.setContentsMargins(10, 10, 10, 10)

                # Timestamp label (smaller, muted)
                ts_label = QLabel(str(timestamp))
                ts_label.setObjectName("HistoryTimestamp")
                card_layout.addWidget(ts_label)

                # Text preview — trimmed to keep cards compact, no text selection
                preview = (text[:197] + "...") if len(text) > 200 else text
                text_label = QLabel(preview)
                text_label.setObjectName("HistoryText")
                text_label.setWordWrap(True)
                card_layout.addWidget(text_label)

                cards_layout.insertWidget(cards_layout.count() - 1, card)

                # Use a proper signal emission for clicks
                card.mousePressEvent = lambda event, t=text: self.on_card_clicked(t)

        scroll.setWidget(cards_container)
        layout.addWidget(scroll, stretch=1)

        # Close button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

    def on_card_clicked(self, text):
        self.text_selected.emit(text)
        self.accept()
