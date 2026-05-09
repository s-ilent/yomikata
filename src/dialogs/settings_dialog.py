import os
import sqlite3

import qtawesome as qta
from PyQt6.QtCore import Qt, QTime, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSlider,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.config import ConfigManager
from core.database import (
    create_fts_index,
    export_personal_dict,
    import_personal_dict,
)
from ui.widgets.widgets import ImportWorker


class SettingsDialog(QDialog):
    settings_saved = pyqtSignal(int, int) # font_size, history_size

    def __init__(self, parent=None, font_size=14, history_size=50, debug_logs=None):
        super().__init__(parent)
        self.setWindowTitle("Settings & Debug")
        self.resize(700, 600)
        self.config = ConfigManager()
        self.debug_logs = debug_logs or []

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        self.stack = QStackedWidget()

        # Category sidebar
        sidebar = QWidget()
        sidebar.setFixedWidth(160)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(8, 16, 8, 16)
        sidebar_layout.setSpacing(0)

        self.category_list = QListWidget()
        self.category_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.category_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        sidebar_layout.addWidget(self.category_list)

        categories = ["General", "AI", "Dictionaries", "Import", "Personal Data", "Debug Logs"]
        for cat in categories:
            self.category_list.addItem(cat)

        # Category selection handler
        self.category_list.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.category_list.setCurrentRow(0)

        # Sidebar styling
        sidebar.setStyleSheet("""
            QWidget {
                background: #252536;
            }
            QListWidget {
                border: none;
                background: transparent;
            }
            QListWidget::item {
                padding: 12px 16px;
                color: #888888;
                border-left: 3px solid transparent;
            }
            QListWidget::item:selected {
                color: #ffffff;
                border-left: 3px solid #7c3aed;
                background: rgba(124, 58, 237, 0.1);
            }
        """)

        # --- PAGE 1: General (Display + History) ---
        general_page = QWidget()
        general_layout = QVBoxLayout(general_page)
        general_layout.setContentsMargins(20, 20, 20, 20)
        general_layout.setSpacing(16)

        display_section = QGroupBox("Display")
        display_section_layout = QFormLayout(display_section)
        self.font_size_slider = QSlider(Qt.Orientation.Horizontal)
        self.font_size_slider.setRange(10, 24)
        self.font_size_slider.setValue(font_size)
        self.font_size_value_label = QLabel(f"{font_size}px")
        self.font_size_slider.valueChanged.connect(lambda v: self.font_size_value_label.setText(f"{v}px"))
        font_layout = QHBoxLayout()
        font_layout.addWidget(self.font_size_slider)
        font_layout.addWidget(self.font_size_value_label)
        display_section_layout.addRow("Font Size:", font_layout)
        general_layout.addWidget(display_section)

        history_section = QGroupBox("History")
        history_section_layout = QFormLayout(history_section)
        self.history_size_slider = QSlider(Qt.Orientation.Horizontal)
        self.history_size_slider.setRange(10, 100)
        self.history_size_slider.setSingleStep(10)
        self.history_size_slider.setValue(history_size)
        self.history_size_value_label = QLabel(f"{history_size} entries")
        self.history_size_slider.valueChanged.connect(lambda v: self.history_size_value_label.setText(f"{v} entries"))
        hist_layout = QHBoxLayout()
        hist_layout.addWidget(self.history_size_slider)
        hist_layout.addWidget(self.history_size_value_label)
        history_section_layout.addRow("History Size:", hist_layout)
        general_layout.addWidget(history_section)

        general_layout.addStretch()
        self.stack.addWidget(general_page)

        # --- PAGE 2: AI ---
        ai_page = QWidget()
        ai_layout = QVBoxLayout(ai_page)
        ai_layout.setContentsMargins(20, 20, 20, 20)
        ai_layout.setSpacing(16)

        ai_section = QGroupBox("AI Configuration")
        ai_section_layout = QFormLayout(ai_section)
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
        ai_section_layout.addRow("AI Provider:", self.ai_provider)
        ai_section_layout.addRow("API URL:", self.api_url)
        ai_section_layout.addRow("API Key:", self.api_key)
        ai_section_layout.addRow("Model Name:", self.ai_model)
        ai_layout.addWidget(ai_section)

        ai_layout.addStretch()
        self.stack.addWidget(ai_page)

        # --- PAGE 3: Dictionaries (includes Import) ---
        dict_page = QWidget()
        dict_page_layout = QVBoxLayout(dict_page)
        dict_page_layout.setContentsMargins(20, 20, 20, 20)
        dict_page_layout.setSpacing(16)

        dicts_section = QGroupBox("Active Dictionaries")
        dicts_section_layout = QVBoxLayout(dicts_section)
        self.dict_list = QListWidget()
        self.refresh_dict_list()
        dicts_section_layout.addWidget(self.dict_list)

        dict_btn_row = QHBoxLayout()
        add_dict_btn = QPushButton("Add Dictionary (.db)")
        add_dict_btn.clicked.connect(self.add_dictionary)
        remove_dict_btn = QPushButton("Remove Selected")
        remove_dict_btn.clicked.connect(self.remove_dictionary)
        dict_btn_row.addWidget(add_dict_btn)
        dict_btn_row.addWidget(remove_dict_btn)
        dicts_section_layout.addLayout(dict_btn_row)

        reorder_btn_row = QHBoxLayout()
        move_up_btn = QPushButton("Move Up")
        move_up_btn.clicked.connect(self.move_dictionary_up)
        move_down_btn = QPushButton("Move Down")
        move_down_btn.clicked.connect(self.move_dictionary_down)
        reorder_btn_row.addWidget(move_up_btn)
        reorder_btn_row.addWidget(move_down_btn)
        dicts_section_layout.addLayout(reorder_btn_row)

        self.rebuild_fts_btn = QPushButton("Rebuild Search Index")
        self.rebuild_fts_btn.clicked.connect(self.rebuild_fts_index_handler)
        dicts_section_layout.addWidget(self.rebuild_fts_btn)

        self.optimize_btn = QPushButton("Optimize Database")
        self.optimize_btn.clicked.connect(self.optimize_database_start)
        dicts_section_layout.addWidget(self.optimize_btn)

        dict_page_layout.addWidget(dicts_section)
        dict_page_layout.addStretch()
        self.stack.addWidget(dict_page)

        # --- PAGE 4: Import ---
        import_page = QWidget()
        import_page_layout = QVBoxLayout(import_page)
        import_page_layout.setContentsMargins(20, 20, 20, 20)
        import_page_layout.setSpacing(16)

        import_section = QGroupBox("Import Dictionary")
        import_section_layout = QVBoxLayout(import_section)
        format_layout = QHBoxLayout()
        format_layout.addWidget(QLabel("Format:"))
        self.import_format = QComboBox()
        self.import_format.addItems(["Text (Eijiro)", "Yomitan (ZIP)"])
        format_layout.addWidget(self.import_format)
        import_section_layout.addLayout(format_layout)

        self.source_file_label = QLabel("No file selected")
        select_file_btn = QPushButton("Select Source File...")
        select_file_btn.clicked.connect(self.select_source_file)
        file_row = QHBoxLayout()
        file_row.addWidget(select_file_btn)
        file_row.addWidget(self.source_file_label, stretch=1)
        import_section_layout.addLayout(file_row)

        target_row = QHBoxLayout()
        target_row.addWidget(QLabel("Target DB:"))
        self.target_db = QLineEdit("")
        browse_target_btn = QPushButton("Browse...")
        browse_target_btn.clicked.connect(self.browse_target_db)
        target_row.addWidget(self.target_db)
        target_row.addWidget(browse_target_btn)
        import_section_layout.addLayout(target_row)

        self.import_progress = QProgressBar()
        self.import_progress.setVisible(False)
        self.import_status = QLabel("")
        self.import_btn = QPushButton("Start Import")
        self.import_btn.clicked.connect(self.start_import)
        import_section_layout.addWidget(self.import_progress)
        import_section_layout.addWidget(self.import_status)
        import_section_layout.addWidget(self.import_btn)

        import_page_layout.addWidget(import_section)
        import_page_layout.addStretch()
        self.stack.addWidget(import_page)

        # --- PAGE 5: Personal Notes ---
        notes_page = QWidget()
        notes_layout = QVBoxLayout(notes_page)
        notes_layout.setContentsMargins(20, 20, 20, 20)
        notes_layout.setSpacing(16)

        notes_section = QGroupBox("Personal Notes")
        notes_section_layout = QVBoxLayout(notes_section)

        self.notes_list = QListWidget()
        self.notes_list.itemClicked.connect(self.load_note_to_editor)
        notes_section_layout.addWidget(self.notes_list)

        self.note_editor = QTextEdit()
        notes_section_layout.addWidget(QLabel("Definition:"))
        notes_section_layout.addWidget(self.note_editor)

        btn_row = QHBoxLayout()
        save_note_btn = QPushButton("Save Note")
        save_note_btn.clicked.connect(self.save_note_handler)
        delete_note_btn = QPushButton("Delete Note")
        delete_note_btn.clicked.connect(self.delete_note_handler)
        btn_row.addWidget(save_note_btn)
        btn_row.addWidget(delete_note_btn)
        notes_section_layout.addLayout(btn_row)

        notes_layout.addWidget(notes_section)
        self.stack.addWidget(notes_page)

        # Refresh notes list
        self.refresh_notes_list()

        # --- PAGE 5: Debug Logs ---
        debug_page = QWidget()
        debug_layout = QVBoxLayout(debug_page)
        debug_layout.setContentsMargins(20, 20, 20, 20)
        debug_layout.setSpacing(16)

        debug_section = QGroupBox("Debug Logs")
        debug_section_layout = QVBoxLayout(debug_section)
        self.log_viewer = QTextEdit()
        self.log_viewer.setReadOnly(True)
        self.log_viewer.setPlainText("\n".join(self.debug_logs))
        debug_section_layout.addWidget(self.log_viewer)

        clear_btn = QPushButton("Clear Logs")
        clear_btn.clicked.connect(self.clear_debug_logs)
        debug_section_layout.addWidget(clear_btn)

        debug_layout.addWidget(debug_section)
        debug_layout.addStretch()
        self.stack.addWidget(debug_page)

        # Content area with bottom buttons
        content_container = QWidget()
        content_container_layout = QVBoxLayout(content_container)
        content_container_layout.setContentsMargins(0, 0, 0, 0)
        content_container_layout.addWidget(self.stack)

        # Divider line
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet("QFrame { color: #3b3b5c; }")
        content_container_layout.addWidget(divider)

        # Bottom buttons
        btn_box = QHBoxLayout()
        btn_box.setContentsMargins(20, 12, 20, 12)
        btn_box.addStretch()
        save_btn = QPushButton("Save Settings")
        save_btn.clicked.connect(self.save)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_box.addWidget(save_btn)
        btn_box.addWidget(cancel_btn)
        content_container_layout.addLayout(btn_box)

        # Add sidebar and content container
        main_layout.addWidget(sidebar)
        main_layout.addWidget(content_container)

    def refresh_dict_list(self):
        """Refresh dictionary list with checkboxes and display names."""
        self.dict_list.clear()

        # Add JMDict as a toggleable source
        jmdict_item = QListWidgetItem("JMDict (built-in)")
        jmdict_item.setFlags(jmdict_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        jmdict_item.setCheckState(Qt.CheckState.Checked if self.config.get("jmdict_enabled", True) else Qt.CheckState.Unchecked)
        jmdict_item.setData(Qt.ItemDataRole.UserRole, ("jmdict", ""))
        jmdict_item.setToolTip("Toggle JMDict lookup")
        self.dict_list.addItem(jmdict_item)

        # Add external dictionaries with checkboxes
        dicts = self.config.extra_dictionaries
        for db_path in dicts:
            display_name = self._get_dictionary_display_name(db_path)
            item = QListWidgetItem(f"✓ {display_name}")
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            item.setData(Qt.ItemDataRole.UserRole, (display_name, db_path))
            item.setToolTip(db_path)
            self.dict_list.addItem(item)

    def _get_dictionary_display_name(self, db_path: str) -> str:
        """Extract a readable name from the database file."""
        if not os.path.exists(db_path):
            return os.path.basename(db_path) + " (not found)"

        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Try to get dictionary name from metadata or table
            # Check dictionary_entries table first
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='dictionary_entries'")
            if cursor.fetchone():
                cursor.execute("SELECT dictionary_name FROM dictionary_entries LIMIT 1")
                row = cursor.fetchone()
                if row and row[0]:
                    conn.close()
                    return row[0]

            # Fall back to filename without extension
            conn.close()
            base_name = os.path.basename(db_path)
            # Remove common prefixes like "01 ", "02 ", etc.
            import re
            cleaned = re.sub(r'^\d+\s+\[.*?\]\s*', '', base_name)
            name = os.path.splitext(cleaned)[0]
            return name
        except Exception:
            return os.path.basename(db_path)

    def _get_enabled_dicts(self) -> list[str]:
        """Get list of enabled dictionary paths."""
        enabled = []
        for i in range(self.dict_list.count()):
            item = self.dict_list.item(i)
            data = item.data(Qt.ItemDataRole.UserRole)
            if data:
                name, path = data
                if name == "jmdict":
                    # Handle JMDict toggle separately via config
                    if item.checkState() == Qt.CheckState.Checked:
                        self.config.set("jmdict_enabled", True)
                    else:
                        self.config.set("jmdict_enabled", False)
                elif path and item.checkState() == Qt.CheckState.Checked:
                    enabled.append(path)
        return enabled

    def refresh_notes_list(self):
        self.notes_list.clear()
        conn = sqlite3.connect("yomikata.db")
        cursor = conn.cursor()
        cursor.execute("SELECT headword FROM personal_dict")
        rows = cursor.fetchall()
        for row in rows:
            self.notes_list.addItem(row[0])
        conn.close()

    def load_note_to_editor(self, item):
        word = item.text()
        conn = sqlite3.connect("yomikata.db")
        cursor = conn.cursor()
        cursor.execute("SELECT definition FROM personal_dict WHERE headword = ?", (word,))
        res = cursor.fetchone()
        if res:
            self.note_editor.setPlainText(res[0])
        conn.close()

    def save_note_handler(self):
        item = self.notes_list.currentItem()
        if not item:
            return
        word = item.text()
        definition = self.note_editor.toPlainText()

        from core.database import _get_db
        _get_db().save_personal_note(word, definition)
        QMessageBox.information(self, "Success", "Note saved.")

    def delete_note_handler(self):
        item = self.notes_list.currentItem()
        if not item:
            return
        word = item.text()
        conn = sqlite3.connect("yomikata.db")
        cursor = conn.cursor()
        cursor.execute("DELETE FROM personal_dict WHERE headword = ?", (word,))
        conn.commit()
        conn.close()
        self.refresh_notes_list()
        self.note_editor.clear()
        QMessageBox.information(self, "Deleted", "Note deleted.")

    def add_dictionary(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open Dictionary", "", "SQLite DB (*.db)")
        if path:
            self.config.add_extra_dictionary(path)
            self.refresh_dict_list()

    def remove_dictionary(self):
        current = self.dict_list.currentItem()
        if current:
            data = current.data(Qt.ItemDataRole.UserRole)
            if data:
                name, path = data
                if path:  # Not the JMDict row
                    self.config.remove_extra_dictionary(path)
                    self.refresh_dict_list()

    def move_dictionary_up(self):
        row = self.dict_list.currentRow()
        # Account for JMDict at row 0 - only move if row > 1
        if row > 1:
            # Adjust for JMDict row at index 0
            dicts = self.config.extra_dictionaries
            dict_idx = row - 1  # Adjust for JMDict row
            dicts[dict_idx], dicts[dict_idx - 1] = dicts[dict_idx - 1], dicts[dict_idx]
            self.config.set_extra_dictionaries(dicts)
            self.refresh_dict_list()
            self.dict_list.setCurrentRow(row - 1)

    def move_dictionary_down(self):
        row = self.dict_list.currentRow()
        dicts = self.config.extra_dictionaries
        if row > 0 and row < len(dicts):
            dict_idx = row - 1  # Adjust for JMDict row
            dicts[dict_idx], dicts[dict_idx + 1] = dicts[dict_idx + 1], dicts[dict_idx]
            self.config.set_extra_dictionaries(dicts)
            self.refresh_dict_list()
            self.dict_list.setCurrentRow(row + 1)

    def rebuild_fts_index_handler(self):
        current = self.dict_list.currentItem()
        if current:
            db_path = current.text()
            self._log(f"Starting FTS index rebuild for: {db_path}")

            # Show loading state
            self.rebuild_fts_btn.setEnabled(False)
            self.rebuild_fts_btn.setText("Rebuilding...")

            QApplication.processEvents()

            try:
                count = create_fts_index(db_path)
                msg = f"Rebuilt FTS index with {count} entries."
                self._log(f"FTS rebuild complete: {count} entries")
                QMessageBox.information(self, "Success", msg)
            except Exception as e:
                msg = f"FTS rebuild failed: {e}"
                self._log(f"FTS rebuild failed: {e}")
                QMessageBox.critical(self, "Error", msg)
            finally:
                self.rebuild_fts_btn.setEnabled(True)
                self.rebuild_fts_btn.setText("Rebuild Search Index")

    def _log(self, message):
        """Append message to debug log viewer."""
        timestamp = QTime.currentTime().toString("HH:mm:ss")
        self.log_viewer.append(f"[{timestamp}] {message}")
        if hasattr(self.parent(), "debug_logs"):
            self.parent().debug_logs.append(f"[{timestamp}] {message}")

    def optimize_database_start(self):
        """Actually run the optimization in background."""
        self._log("Running VACUUM...")

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        QApplication.processEvents()

        try:
            conn = sqlite3.connect("yomikata.db")
            cursor = conn.cursor()
            cursor.execute("VACUUM")
            conn.commit()
            conn.close()
            self._log("Database optimized successfully (VACUUM).")
            QMessageBox.information(self, "Success", "Database optimized (VACUUM).")
        except Exception as e:
            self._log(f"Optimization failed: {e}")
            QMessageBox.critical(self, "Error", f"Optimization failed: {e}")
        finally:
            QApplication.restoreOverrideCursor()

    def select_source_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Source File")
        if path:
            self.source_file_label.setText(os.path.basename(path))
            self._source_path = path
            # Auto-suggest target DB path based on filename
            base_name = os.path.splitext(os.path.basename(path))[0]
            self.target_db.setText(f"{base_name}.db")

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

        self._log(f"Starting import: {source} -> {target} (format: {fmt})")

        self.import_progress.setVisible(True)
        self.import_progress.setValue(0)
        self.import_status.setText("Importing...")
        self.import_btn.setEnabled(False)

        self.worker = ImportWorker(source, target, fmt)
        self.worker.progress.connect(self.import_progress.setValue)
        self.worker.finished.connect(lambda c: (
            self.import_status.setText(f"✓ Imported {c} entries."),
            self._log(f"Import complete: {c} entries imported"),
            self.import_progress.setVisible(False),
            self.import_btn.setEnabled(True)
        ))
        self.worker.error.connect(lambda e: (
            QMessageBox.critical(self, "Error", e),
            self._log(f"Import failed: {e}"),
            self.import_status.setText("Failed."),
            self.import_progress.setVisible(False),
            self.import_btn.setEnabled(True)
        ))
        self.worker.start()

    def export_personal_dict_handler(self):
        fmt = self.export_format.currentText().lower()
        path, _ = QFileDialog.getSaveFileName(self, "Export Personal Dictionary", f"personal_dict.{fmt}")
        if path:
            self._log(f"Exporting personal dict to: {path} (format: {fmt})")
            try:
                count = export_personal_dict(path, fmt)
                self.export_status.setText(f"✓ Exported {count} entries.")
                self._log(f"Export complete: {count} entries")
            except Exception as e:
                self.export_status.setText(f"Error: {e}")
                self._log(f"Export failed: {e}")

    def import_personal_dict_handler(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import Personal Dictionary")
        if path:
            self._log(f"Importing personal dict from: {path}")
            try:
                count = import_personal_dict(path)
                self.import_personal_status.setText(f"✓ Imported {count} entries.")
                self._log(f"Import complete: {count} entries")
            except Exception as e:
                self.import_personal_status.setText(f"Error: {e}")
                self._log(f"Import failed: {e}")

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

        # Save enabled dictionaries
        enabled_dicts = self._get_enabled_dicts()
        self.config.set_extra_dictionaries(enabled_dicts)

        self.settings_saved.emit(font_size, history_size)
        self.accept()
