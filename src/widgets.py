from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from PyQt6.QtCore import QSettings


class PunctuationWidget(QLabel):
    """Small, non-clickable widget for 、。！？ etc."""

    def __init__(self, text):
        super().__init__(text)
        self.setStyleSheet(
            "font-size: 20px; color: #555; padding: 0px; margin-top: 15px;"
        )
        self.setAlignment(Qt.AlignmentFlag.AlignBottom)


class TokenWidget(QFrame):
    clicked = pyqtSignal(dict, bool)  # Added bool for Ctrl-click status

    def __init__(self, token_data):
        super().__init__()
        self.setObjectName("TokenCard")
        self.data = token_data
        self.is_selected = False  # Tracking state

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(0)

        # Labels as before...
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
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        fm = self.surface_lbl.fontMetrics()
        width = fm.boundingRect(token_data["surface"]).width() + 20
        self.setFixedWidth(max(40, width))

    def set_highlight(self, state):
        self.is_selected = state
        if state:
            self.setStyleSheet(
                "QFrame#TokenCard { border: 2px solid #3d5afe; background-color: #2a2a2a; }"
            )
        else:
            self.setStyleSheet("")  # Reverts to stylesheet default

    def mousePressEvent(self, event):
        # Check if Control key is held
        ctrl_held = event.modifiers() & Qt.KeyboardModifier.ControlModifier
        self.clicked.emit(self.data, bool(ctrl_held))


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings & Debug")
        self.resize(600, 500)
        self.settings = QSettings("Yomikata", "Settings")

        main_layout = QVBoxLayout(self)
        self.tabs = QTabWidget()

        # --- TAB 1: Configuration ---
        config_tab = QWidget()
        config_layout = QFormLayout(config_tab)

        self.ai_provider = QComboBox()
        self.ai_provider.addItems(["Ollama", "OpenAI / Compatible"])
        self.ai_provider.setCurrentText(self.settings.value("ai_provider", "Ollama"))

        self.api_url = QLineEdit(
            self.settings.value("api_url", "http://localhost:11434")
        )
        self.api_key = QLineEdit(self.settings.value("api_key", ""))
        self.ai_model = QLineEdit(self.settings.value("ai_model", "llama3"))

        config_layout.addRow("AI Provider:", self.ai_provider)
        config_layout.addRow("API URL:", self.api_url)
        config_layout.addRow("API Key:", self.api_key)
        config_layout.addRow("Model Name:", self.ai_model)

        self.tabs.addTab(config_tab, "AI Configuration")

        # --- TAB 2: Debug Logs ---
        debug_tab = QWidget()
        debug_layout = QVBoxLayout(debug_tab)

        self.log_viewer = QTextEdit()
        self.log_viewer.setReadOnly(True)
        self.log_viewer.setPlaceholderText("No logs yet...")
        self.log_viewer.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)

        # Access the logs from the main app (the parent)
        if parent and hasattr(parent, "debug_logs"):
            self.log_viewer.setPlainText("\n".join(parent.debug_logs))
            # Auto-scroll to bottom
            self.log_viewer.verticalScrollBar().setValue(
                self.log_viewer.verticalScrollBar().maximum()
            )

        clear_btn = QPushButton("Clear Logs")
        clear_btn.clicked.connect(self.clear_debug_logs)

        debug_layout.addWidget(self.log_viewer)
        debug_layout.addWidget(clear_btn)
        self.tabs.addTab(debug_tab, "Debug Logs")

        main_layout.addWidget(self.tabs)

        # --- TAB 3: Dictionaries ---
        dict_tab = QWidget()
        dict_layout = QVBoxLayout(dict_tab)

        self.dict_list = QListWidget()
        self.refresh_dict_list()

        add_dict_btn = QPushButton("Add Dictionary (.db)")
        add_dict_btn.clicked.connect(self.add_dictionary)

        remove_dict_btn = QPushButton("Remove Selected")
        remove_dict_btn.clicked.connect(self.remove_dictionary)

        dict_layout.addWidget(QLabel("Active Dictionaries:"))
        dict_layout.addWidget(self.dict_list)
        dict_layout.addWidget(add_dict_btn)
        dict_layout.addWidget(remove_dict_btn)
        self.tabs.addTab(dict_tab, "Dictionaries")

        # Bottom Buttons
        btn_box = QHBoxLayout()
        save_btn = QPushButton("Save Settings")
        save_btn.clicked.connect(self.save_settings)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_box.addWidget(save_btn)
        btn_box.addWidget(cancel_btn)
        main_layout.addLayout(btn_box)

    def refresh_dict_list(self):
        self.dict_list.clear()
        dicts = self.settings.value("extra_dictionaries", [])
        self.dict_list.addItems(dicts)

    def add_dictionary(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Dictionary", "", "SQLite DB (*.db)"
        )
        if path:
            dicts = self.settings.value("extra_dictionaries", [])
            if path not in dicts:
                dicts.append(path)
                self.settings.setValue("extra_dictionaries", dicts)
                self.refresh_dict_list()

    def remove_dictionary(self):
        current = self.dict_list.currentItem()
        if current:
            dicts = self.settings.value("extra_dictionaries", [])
            dicts.remove(current.text())
            self.settings.setValue("extra_dictionaries", dicts)
            self.refresh_dict_list()

    def clear_debug_logs(self):
        if self.parent() and hasattr(self.parent(), "debug_logs"):
            self.parent().debug_logs = []
        self.log_viewer.clear()

    def save_settings(self):
        self.settings.setValue("ai_provider", self.ai_provider.currentText())
        self.settings.setValue("api_url", self.api_url.text())
        self.settings.setValue("api_key", self.api_key.text())
        self.settings.setValue("ai_model", self.ai_model.text())
        self.accept()