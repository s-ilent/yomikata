import os
import sqlite3

from PyQt6.QtCore import Qt, pyqtSignal, QThread, pyqtSignal as QtSignal
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
    QProgressBar,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from PyQt6.QtCore import QSettings


def import_dictionary_file(source_path, target_db_path, progress_callback=None):
    """
    Import entries from an Eijiro-style text file into a SQLite database.
    Handles both UTF-8 and CP932 (Shift-JIS) encoding.

    Returns the number of entries imported.
    """
    # Initialize target database
    conn = sqlite3.connect(target_db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dictionary (
            headword TEXT,
            definition TEXT
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_headword ON dictionary(headword)")
    conn.commit()

    # Detect encoding
    try:
        f = open(source_path, "r", encoding="utf-8")
        f.readline()
        f.seek(0)
    except UnicodeDecodeError:
        f = open(source_path, "r", encoding="cp932")

    entries = []
    total = 0

    with f:
        for line in f:
            if line.startswith("■"):
                parts = line.lstrip("■").split(" : ", 1)
                if len(parts) == 2:
                    entries.append((parts[0].strip(), parts[1].strip()))

            if len(entries) >= 20000:
                cursor.executemany("INSERT INTO dictionary VALUES (?, ?)", entries)
                conn.commit()
                total += len(entries)
                entries = []
                if progress_callback:
                    progress_callback(total)

    # Insert remaining
    if entries:
        cursor.executemany("INSERT INTO dictionary VALUES (?, ?)", entries)
        total += len(entries)

    conn.commit()
    conn.close()

    if progress_callback:
        progress_callback(total)

    return total


class ImportWorker(QThread):
    progress = QtSignal(int)
    finished = QtSignal(int)
    error = QtSignal(str)

    def __init__(self, source_path, target_db_path):
        super().__init__()
        self.source_path = source_path
        self.target_db_path = target_db_path

    def run(self):
        try:
            count = import_dictionary_file(
                self.source_path,
                self.target_db_path,
                lambda p: self.progress.emit(p)
            )
            self.finished.emit(count)
        except Exception as e:
            self.error.emit(str(e))


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

        # --- TAB 4: Import ---
        import_tab = QWidget()
        import_layout = QVBoxLayout(import_tab)

        import_layout.addWidget(QLabel("Import Eijiro-style Dictionary:"))
        import_layout.addWidget(QLabel("<small>Select a text file (UTF-8 or Shift-JIS) to import entries into a database.</small>"))

        self.source_file_label = QLabel("No file selected")
        btn_layout = QHBoxLayout()
        select_file_btn = QPushButton("Select Source File...")
        select_file_btn.clicked.connect(self.select_source_file)
        btn_layout.addWidget(select_file_btn)
        btn_layout.addWidget(self.source_file_label, stretch=1)
        import_layout.addLayout(btn_layout)

        # Target database
        target_layout = QHBoxLayout()
        target_layout.addWidget(QLabel("Target DB:"))
        self.target_db = QLineEdit("")
        browse_target_btn = QPushButton("Browse...")
        browse_target_btn.clicked.connect(self.browse_target_db)
        target_layout.addWidget(self.target_db)
        target_layout.addWidget(browse_target_btn)
        import_layout.addLayout(target_layout)

        self.import_progress = QProgressBar()
        self.import_progress.setVisible(False)
        import_layout.addWidget(self.import_progress)

        self.import_status = QLabel("")
        import_layout.addWidget(self.import_status)

        import_btn = QPushButton("Start Import")
        import_btn.clicked.connect(self.start_import)
        import_layout.addWidget(import_btn)

        import_layout.addStretch()
        self.tabs.addTab(import_tab, "Import")

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

    def select_source_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Dictionary Source File", "",
            "Text Files (*.txt);;All Files (*)"
        )
        if path:
            self.source_file_label.setText(os.path.basename(path))
            self.source_file = path
            # Suggest a default DB name based on source file
            base_name = os.path.splitext(os.path.basename(path))[0]
            self.target_db.setText(f"{base_name}.db")

    def browse_target_db(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Target Database", "",
            "SQLite Database (*.db)"
        )
        if path:
            self.target_db.setText(path)

    def start_import(self):
        if not hasattr(self, "source_file"):
            self.import_status.setText("Please select a source file first.")
            return

        source = self.source_file
        target = self.target_db.text()

        self.import_progress.setVisible(True)
        self.import_progress.setRange(0, 0)  # Indeterminate
        self.import_status.setText("Importing...")

        self.worker = ImportWorker(source, target)
        self.worker.finished.connect(self.on_import_finished)
        self.worker.error.connect(self.on_import_error)
        self.worker.start()

    def on_import_finished(self, count):
        self.import_progress.setVisible(False)
        self.import_status.setText(f"✓ Imported {count:,} entries.")

        # Optionally add to active dictionaries
        target = self.target_db.text()
        if target != "yomikata.db":
            dicts = self.settings.value("extra_dictionaries", [])
            if target not in dicts:
                dicts.append(target)
                self.settings.setValue("extra_dictionaries", dicts)
                self.refresh_dict_list()

    def on_import_error(self, err):
        self.import_progress.setVisible(False)
        self.import_status.setText(f"Error: {err}")

    def save_settings(self):
        self.settings.setValue("ai_provider", self.ai_provider.currentText())
        self.settings.setValue("api_url", self.api_url.text())
        self.settings.setValue("api_key", self.api_key.text())
        self.settings.setValue("ai_model", self.ai_model.text())
        self.accept()