import qtawesome as qta
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
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

from ui.layouts.flow_layout import FlowLayout
from ui.style import build_stylesheet


class YomikataMainWindow(QMainWindow):
    def __init__(self, ai_controller):
        super().__init__()
        self.ai_controller = ai_controller
        self._setup_ui()

    def _setup_ui(self):
        self.setWindowTitle("Yomikata Japanese Assistant")
        self.resize(1200, 850)
        # Assuming font_size is managed centrally; temporarily using default
        self.setStyleSheet(build_stylesheet(font_base=12))

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
        # Connections will be established in the controller or main app

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

        self.card_stack = QFrame()
        self.card_stack.setObjectName("DictionaryCardStack")
        stack_layout = QVBoxLayout(self.card_stack)
        stack_layout.setContentsMargins(0, 0, 0, 0)
        stack_layout.setSpacing(4)
        stack_layout.addStretch()
        self.card_stack.setStyleSheet("""
            QFrame#DictionaryCardStack {
                background: transparent;
            }
        """)
        dict_scroll.setWidget(self.card_stack)

        # Search box for FTS
        search_layout = QHBoxLayout()
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search definitions...")
        search_btn = QPushButton()
        search_btn.setIcon(qta.icon("fa5s.search", color="white"))
        search_btn.setFixedSize(40, 40)
        search_btn.setToolTip("Search")
        search_layout.addWidget(self.search_box)
        search_layout.addWidget(search_btn)
        search_btn.setObjectName("primary-btn")
        search_btn.setStyleSheet("padding: 0;")

        # --- AI and Settings Buttons ---
        ai_controls_layout = QHBoxLayout()

        # AI Template selector
        self.ai_template = QComboBox()
        self.ai_template.addItems(self.ai_controller.get_template_names())
        self.ai_template.setToolTip("Select analysis mode")
        self.ai_template.setFixedHeight(40)

        # Main AI Button
        self.ai_btn = QPushButton(" Ask AI")
        self.ai_btn.setIcon(qta.icon("fa5s.robot", color="white"))
        self.ai_btn.setEnabled(False)
        self.ai_btn.setMinimumHeight(40)
        self.ai_btn.setObjectName("AnalyzeBtn")

        ai_controls_layout.addWidget(self.ai_template, stretch=2)
        ai_controls_layout.addWidget(self.ai_btn, stretch=3)

        self.save_ai_btn = QPushButton("Save AI to Personal Dict")
        self.save_ai_btn.setIcon(qta.icon("fa5s.save", color="white"))
        self.save_ai_btn.setVisible(False)
        self.save_ai_btn.setObjectName("success-btn")

        self.edit_note_btn = QPushButton("Edit Note")
        self.edit_note_btn.setIcon(qta.icon("fa5s.edit", color="white"))
        self.edit_note_btn.setEnabled(False)
        self.edit_note_btn.setObjectName("secondary-btn")
        self.edit_note_btn.setMinimumHeight(40)

        self.history_btn = QPushButton()
        self.history_btn.setIcon(qta.icon("fa5s.clock", color="white"))
        self.history_btn.setFixedSize(40, 40)
        self.history_btn.setToolTip("History")
        self.history_btn.setObjectName("secondary-btn")
        self.history_btn.setStyleSheet("padding: 0;")

        self.settings_btn = QPushButton()
        self.settings_btn.setIcon(qta.icon("fa5s.cog", color="white"))
        self.settings_btn.setFixedSize(40, 40)
        self.settings_btn.setToolTip("Settings")
        self.settings_btn.setObjectName("secondary-btn")
        self.settings_btn.setStyleSheet("padding: 0;")

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
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
