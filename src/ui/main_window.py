import qtawesome as qta
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
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
from ui.widgets.widgets import (
    DictionaryCardStack,
)


class YomikataUI:
    def __init__(self, main_window):
        self.win = main_window
        self._setup_ui()

    def _setup_ui(self):
        self.win.setWindowTitle("Yomikata Japanese Assistant")
        self.win.resize(1200, 850)
        self.win.setStyleSheet(build_stylesheet(font_base=self.win.font_size))

        self.win.splitter = QSplitter(Qt.Orientation.Horizontal)

        # --- LEFT SIDE (Reading & Input) ---
        left_container = QWidget()
        left_container.setObjectName("leftPanel")
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(15, 15, 15, 15)

        # 1. Top: Reading Area (The Output)
        self.win.scroll = QScrollArea()
        self.win.scroll.setWidgetResizable(True)
        self.win.matrix_container = QWidget()
        self.win.matrix_container.setStyleSheet("background-color: transparent;")

        # Use our NEW wrapping layout
        self.win.matrix_layout = FlowLayout(self.win.matrix_container, spacing=10)
        self.win.scroll.setWidget(self.win.matrix_container)

        # 2. Bottom: Input Area
        input_container = QVBoxLayout()
        self.win.input_area = QTextEdit()
        self.win.input_area.setPlaceholderText("Paste Japanese text here...")
        self.win.input_area.setMaximumHeight(150)

        self.win.analyze_btn = QPushButton("Analyze Text (Ctrl+Enter)")
        self.win.analyze_btn.setObjectName("AnalyzeBtn")
        self.win.analyze_btn.clicked.connect(self.win.analyze_text)

        input_container.addWidget(self.win.input_area)
        input_container.addWidget(self.win.analyze_btn)

        # Build Left Layout: Scroll (Top), Input (Bottom)
        left_layout.addWidget(self.win.scroll, stretch=1)
        left_layout.addLayout(input_container)

        # --- RIGHT SIDE (Dictionary & AI) ---
        right_container = QWidget()
        right_container.setObjectName("rightPanel")
        right_layout = QVBoxLayout(right_container)

        # Dictionary display as card stack in scroll area
        dict_scroll = QScrollArea()
        dict_scroll.setWidgetResizable(True)
        dict_scroll.setStyleSheet("border: none;")

        self.win.card_stack = DictionaryCardStack()
        dict_scroll.setWidget(self.win.card_stack)

        # Search box for FTS
        search_layout = QHBoxLayout()
        self.win.search_box = QLineEdit()
        self.win.search_box.setPlaceholderText("Search definitions...")
        self.win.search_box.returnPressed.connect(self.win.do_definition_search)
        search_btn = QPushButton()
        search_btn.setIcon(qta.icon("fa5s.search", color="white"))
        search_btn.setFixedSize(40, 40)
        search_btn.setToolTip("Search")
        search_btn.clicked.connect(self.win.do_definition_search)
        search_layout.addWidget(self.win.search_box)
        search_layout.addWidget(search_btn)
        search_btn.setObjectName("primary-btn")
        search_btn.setStyleSheet("padding: 0;")

        # --- AI and Settings Buttons ---
        ai_controls_layout = QHBoxLayout()

        # AI Template selector
        from PyQt6.QtWidgets import QComboBox
        self.win.ai_template = QComboBox()
        self.win.ai_template.addItems(self.win.ai_controller.get_template_names())
        self.win.ai_template.setToolTip("Select analysis mode")
        self.win.ai_template.setFixedHeight(40)

        # Main AI Button
        self.win.ai_btn = QPushButton(" Ask AI")  # Added a space for icon padding
        self.win.ai_btn.setIcon(qta.icon("fa5s.robot", color="white"))  # Robot icon!
        self.win.ai_btn.clicked.connect(self.win.ask_ai)
        self.win.ai_btn.setEnabled(False)
        self.win.ai_btn.setMinimumHeight(40)
        self.win.ai_btn.setObjectName("AnalyzeBtn")  # Reusing the blue style

        ai_controls_layout.addWidget(self.win.ai_template, stretch=2)
        ai_controls_layout.addWidget(self.win.ai_btn, stretch=3)  # Takes up most space

        self.win.save_ai_btn = QPushButton("Save AI to Personal Dict")
        self.win.save_ai_btn.setIcon(qta.icon("fa5s.save", color="white"))
        self.win.save_ai_btn.clicked.connect(self.win.save_ai_to_dict)
        self.win.save_ai_btn.setVisible(False)  # Hide it until AI responds
        self.win.save_ai_btn.setObjectName("success-btn")

        self.win.edit_note_btn = QPushButton("Edit Note")
        self.win.edit_note_btn.setIcon(qta.icon("fa5s.edit", color="white"))
        self.win.edit_note_btn.clicked.connect(self.win.edit_note)
        self.win.edit_note_btn.setEnabled(False)
        self.win.edit_note_btn.setObjectName("secondary-btn")
        self.win.edit_note_btn.setMinimumHeight(40)

        self.win.history_btn = QPushButton()
        self.win.history_btn.setIcon(qta.icon("fa5s.clock", color="white"))
        self.win.history_btn.setFixedSize(40, 40)
        self.win.history_btn.setToolTip("History")
        self.win.history_btn.clicked.connect(self.win.show_history)
        self.win.history_btn.setObjectName("secondary-btn")
        self.win.history_btn.setStyleSheet("padding: 0;")

        self.win.settings_btn = QPushButton()
        self.win.settings_btn.setIcon(qta.icon("fa5s.cog", color="white"))
        self.win.settings_btn.setFixedSize(40, 40)
        self.win.settings_btn.setToolTip("Settings")
        self.win.settings_btn.clicked.connect(self.win.open_settings)
        self.win.settings_btn.setObjectName("secondary-btn")
        self.win.settings_btn.setStyleSheet("padding: 0;")

        self.win.progress_bar = QProgressBar()
        self.win.progress_bar.setRange(0, 0)  # Indeterminate "pulser"
        self.win.progress_bar.setVisible(False)
        self.win.progress_bar.setStyleSheet("QProgressBar::chunk { background-color: #3d5afe; }")
        self.win.progress_bar.setFixedHeight(4)

        dict_label = QLabel("<b>DICTIONARY REVEAL</b>")
        dict_label.setStyleSheet("background: transparent;")
        right_layout.addWidget(dict_label)
        right_layout.addLayout(search_layout)
        right_layout.addWidget(dict_scroll)
        right_layout.addLayout(ai_controls_layout)

        # Note buttons row
        note_btn_layout = QHBoxLayout()
        note_btn_layout.addWidget(self.win.save_ai_btn)
        note_btn_layout.addWidget(self.win.edit_note_btn, stretch=1)
        note_btn_layout.addWidget(self.win.history_btn)
        note_btn_layout.addWidget(self.win.settings_btn)
        right_layout.addLayout(note_btn_layout)

        right_layout.addWidget(self.win.progress_bar)

        self.win.splitter.addWidget(left_container)
        self.win.splitter.addWidget(right_container)
        self.win.splitter.setStretchFactor(0, 3)
        self.win.splitter.setStretchFactor(1, 1)

        self.win.setCentralWidget(self.win.splitter)

        # Shortcut for Ctrl+Enter
        self.win.input_area.installEventFilter(self.win)
