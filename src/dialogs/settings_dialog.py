import os
import sqlite3
import qtawesome as qta
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QTabWidget, QWidget, QFormLayout, QHBoxLayout,
    QSlider, QLabel, QComboBox, QLineEdit, QTextEdit, QPushButton,
    QListWidget, QFileDialog, QProgressBar, QMessageBox
)
from widgets import (
    create_fts_index, import_dictionary_file, export_personal_dict, 
    import_personal_dict, ImportWorker
)
from config import ConfigManager

class SettingsDialog(QDialog):
    settings_saved = pyqtSignal(int, int) # font_size, history_size

    def __init__(self, parent=None, font_size=14, history_size=50, debug_logs=None):
        super().__init__(parent)
        self.setWindowTitle("Settings & Debug")
        self.resize(700, 600)
        self.config = ConfigManager()
        self.debug_logs = debug_logs or []

        main_layout = QVBoxLayout(self)
        self.tabs = QTabWidget()

        # --- TAB 0: Display ---
        display_tab = QWidget()
        display_layout = QFormLayout(display_tab)
        self.font_size_slider = QSlider(Qt.Orientation.Horizontal)
        self.font_size_slider.setRange(10, 24)
        self.font_size_slider.setValue(font_size)
        self.font_size_value_label = QLabel(f"{font_size}px")
        self.font_size_slider.valueChanged.connect(lambda v: self.font_size_value_label.setText(f"{v}px"))
        font_layout = QHBoxLayout()
        font_layout.addWidget(self.font_size_slider)
        font_layout.addWidget(self.font_size_value_label)
        display_layout.addRow("Font Size:", font_layout)
        self.tabs.addTab(display_tab, "Display")

        # --- TAB 1: AI Configuration ---
        config_tab = QWidget()
        config_layout = QFormLayout(config_tab)
        self.ai_provider = QComboBox()
        self.ai_provider.addItems(["Ollama", "OpenAI / Compatible"])
        self.ai_provider.setCurrentText(self.config.ai_provider)
        self.api_url = QLineEdit(self.config.get("api_url", "http://localhost:11434"))
        self.api_key = QLineEdit(self.config.get("api_key", ""))
        self.api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.toggle_key_action = self.api_key.addAction(
            qta.icon("fa5s.eye", color="gray"),
            QLineEdit.ActionPosition.TrailingPosition
        )
        self.toggle_key_action.triggered.connect(self.toggle_api_key_visibility)
        
        self.ai_model = QLineEdit(self.config.ai_model)
        config_layout.addRow("AI Provider:", self.ai_provider)
        config_layout.addRow("API URL:", self.api_url)
        config_layout.addRow("API Key:", self.api_key)
        config_layout.addRow("Model Name:", self.ai_model)
        self.tabs.addTab(config_tab, "AI Configuration")

        # --- TAB 2: History ---
        history_tab = QWidget()
        history_layout = QFormLayout(history_tab)
        self.history_size_slider = QSlider(Qt.Orientation.Horizontal)
        self.history_size_slider.setRange(10, 100)
        self.history_size_slider.setSingleStep(10)
        self.history_size_slider.setValue(history_size)
        self.history_size_value_label = QLabel(f"{history_size} entries")
        self.history_size_slider.valueChanged.connect(lambda v: self.history_size_value_label.setText(f"{v} entries"))
        hist_layout = QHBoxLayout()
        hist_layout.addWidget(self.history_size_slider)
        hist_layout.addWidget(self.history_size_value_label)
        history_layout.addRow("History Size:", hist_layout)
        self.tabs.addTab(history_tab, "History")

        # --- TAB 3: Dictionaries ---
        dict_tab = QWidget()
        dict_layout = QVBoxLayout(dict_tab)
        self.dict_list = QListWidget()
        self.refresh_dict_list()
        add_dict_btn = QPushButton("Add Dictionary (.db)")
        add_dict_btn.clicked.connect(self.add_dictionary)
        remove_dict_btn = QPushButton("Remove Selected")
        remove_dict_btn.clicked.connect(self.remove_dictionary)
        rebuild_fts_btn = QPushButton("Rebuild Search Index")
        rebuild_fts_btn.clicked.connect(self.rebuild_fts_index_handler)
        optimize_btn = QPushButton("Optimize Database")
        optimize_btn.clicked.connect(self.optimize_database)
        dict_layout.addWidget(QLabel("Active Dictionaries:"))
        dict_layout.addWidget(self.dict_list)
        dict_layout.addWidget(add_dict_btn)
        dict_layout.addWidget(remove_dict_btn)
        dict_layout.addWidget(rebuild_fts_btn)
        dict_layout.addWidget(optimize_btn)
        self.tabs.addTab(dict_tab, "Dictionaries")

        # --- TAB 4: Import ---
        import_tab = QWidget()
        import_layout = QVBoxLayout(import_tab)
        format_layout = QHBoxLayout()
        format_layout.addWidget(QLabel("Format:"))
        self.import_format = QComboBox()
        self.import_format.addItems(["Text (Eijiro)", "Yomitan (ZIP)", "JMDict (auto)"])
        self.import_format.currentTextChanged.connect(self.on_import_format_changed)
        format_layout.addWidget(self.import_format)
        import_layout.addLayout(format_layout)
        self.source_file_label = QLabel("No file selected")
        select_file_btn = QPushButton("Select Source File...")
        select_file_btn.clicked.connect(self.select_source_file)
        file_row = QHBoxLayout()
        file_row.addWidget(select_file_btn)
        file_row.addWidget(self.source_file_label, stretch=1)
        import_layout.addLayout(file_row)
        target_row = QHBoxLayout()
        target_row.addWidget(QLabel("Target DB:"))
        self.target_db = QLineEdit("")
        browse_target_btn = QPushButton("Browse...")
        browse_target_btn.clicked.connect(self.browse_target_db)
        target_row.addWidget(self.target_db)
        target_row.addWidget(browse_target_btn)
        import_layout.addLayout(target_row)
        self.import_progress = QProgressBar()
        self.import_progress.setVisible(False)
        self.import_status = QLabel("")
        import_btn = QPushButton("Start Import")
        import_btn.clicked.connect(self.start_import)
        import_layout.addWidget(self.import_progress)
        import_layout.addWidget(self.import_status)
        import_layout.addWidget(import_btn)
        import_layout.addStretch()
        self.tabs.addTab(import_tab, "Import")

        # --- TAB 5: Export ---
        export_tab = QWidget()
        export_layout = QVBoxLayout(export_tab)
        self.export_format = QComboBox()
        self.export_format.addItems(["JSON", "CSV"])
        exp_fmt_row = QHBoxLayout()
        exp_fmt_row.addWidget(QLabel("Format:"))
        exp_fmt_row.addWidget(self.export_format)
        export_layout.addLayout(exp_fmt_row)
        self.export_status = QLabel("")
        export_btn = QPushButton("Export to File...")
        export_btn.clicked.connect(self.export_personal_dict_handler)
        import_personal_btn = QPushButton("Import from File...")
        import_personal_btn.clicked.connect(self.import_personal_dict_handler)
        export_layout.addWidget(self.export_status)
        export_layout.addWidget(export_btn)
        export_layout.addWidget(import_personal_btn)
        export_layout.addStretch()
        self.tabs.addTab(export_tab, "Export")

        # --- TAB 6: Debug Logs ---
        debug_tab = QWidget()
        debug_layout = QVBoxLayout(debug_tab)
        self.log_viewer = QTextEdit()
        self.log_viewer.setReadOnly(True)
        self.log_viewer.setPlainText("\n".join(self.debug_logs))
        debug_layout.addWidget(self.log_viewer)
        clear_btn = QPushButton("Clear Logs")
        clear_btn.clicked.connect(self.clear_debug_logs)
        debug_layout.addWidget(clear_btn)
        self.tabs.addTab(debug_tab, "Debug Logs")

        main_layout.addWidget(self.tabs)

        # Bottom Buttons
        btn_box = QHBoxLayout()
        save_btn = QPushButton("Save Settings")
        save_btn.clicked.connect(self.save)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_box.addWidget(save_btn)
        btn_box.addWidget(cancel_btn)
        main_layout.addLayout(btn_box)

    def refresh_dict_list(self):
        self.dict_list.clear()
        dicts = self.config.extra_dictionaries
        self.dict_list.addItems(dicts)

    def add_dictionary(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open Dictionary", "", "SQLite DB (*.db)")
        if path:
            self.config.add_extra_dictionary(path)
            self.refresh_dict_list()

    def remove_dictionary(self):
        current = self.dict_list.currentItem()
        if current:
            self.config.remove_extra_dictionary(current.text())
            self.refresh_dict_list()

    def rebuild_fts_index_handler(self):
        current = self.dict_list.currentItem()
        if current:
            db_path = current.text()
            try:
                count = create_fts_index(db_path)
                QMessageBox.information(self, "Success", f"Rebuilt FTS index with {count} entries.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"FTS rebuild failed: {e}")

    def optimize_database(self):
        try:
            conn = sqlite3.connect("yomikata.db")
            cursor = conn.cursor()
            cursor.execute("VACUUM")
            conn.commit()
            conn.close()
            QMessageBox.information(self, "Success", "Database optimized (VACUUM).")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Optimization failed: {e}")

    def on_import_format_changed(self, format_type):
        if format_type == "JMDict (auto)":
            self.source_file_label.setText("Auto-enabled (jamdict)")
            self.import_status.setText("JMDict is auto-loaded via jamdict.")
        else:
            self.source_file_label.setText("No file selected")
            self.import_status.setText("")

    def select_source_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Source File")
        if path:
            self.source_file_label.setText(os.path.basename(path))
            self._source_path = path

    def browse_target_db(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Dictionary As", "", "SQLite DB (*.db)")
        if path:
            self.target_db.setText(path)

    def start_import(self):
        source = getattr(self, "_source_path", None)
        target = self.target_db.text()
        fmt = self.import_format.currentText()
        if not source or not target:
            QMessageBox.warning(self, "Missing Info", "Please select source and target.")
            return
        self.import_progress.setVisible(True)
        self.import_status.setText("Importing...")
        self.worker = ImportWorker(source, target, fmt)
        self.worker.progress.connect(self.import_progress.setValue)
        self.worker.finished.connect(lambda c: self.import_status.setText(f"✓ Imported {c} entries."))
        self.worker.error.connect(lambda e: QMessageBox.critical(self, "Error", e))
        self.worker.start()

    def export_personal_dict_handler(self):
        fmt = self.export_format.currentText().lower()
        path, _ = QFileDialog.getSaveFileName(self, "Export Personal Dictionary", f"personal_dict.{fmt}")
        if path:
            try:
                count = export_personal_dict(path, fmt)
                self.export_status.setText(f"✓ Exported {count} entries.")
            except Exception as e:
                self.export_status.setText(f"Error: {e}")

    def import_personal_dict_handler(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import Personal Dictionary")
        if path:
            try:
                count = import_personal_dict(path)
                self.export_status.setText(f"✓ Imported {count} entries.")
            except Exception as e:
                self.export_status.setText(f"Error: {e}")

    def clear_debug_logs(self):
        self.log_viewer.clear()
        if hasattr(self.parent(), "debug_logs"):
            self.parent().debug_logs = []

    def toggle_api_key_visibility(self):
        if self.api_key.echoMode() == QLineEdit.EchoMode.Password:
            self.api_key.setEchoMode(QLineEdit.EchoMode.Normal)
            self.toggle_key_action.setIcon(qta.icon("fa5s.eye-slash", color="white"))
        else:
            self.api_key.setEchoMode(QLineEdit.EchoMode.Password)
            self.toggle_key_action.setIcon(qta.icon("fa5s.eye", color="gray"))

    def save(self):
        font_size = self.font_size_slider.value()
        history_size = self.history_size_slider.value()
        self.config.font_size = font_size
        self.config.history_size = history_size
        self.config.set("ai_provider", self.ai_provider.currentText())
        self.config.set("api_url", self.api_url.text())
        self.config.set("api_key", self.api_key.text())
        self.config.set("ai_model", self.ai_model.text())
        self.settings_saved.emit(font_size, history_size)
        self.accept()
