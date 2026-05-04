import os
import sqlite3

from style import CATPPUCCIN_MOCHA as CAT

from PyQt6.QtCore import Qt, pyqtSignal, QThread, pyqtSignal as QtSignal
from PyQt6.QtGui import QFont, QFontMetrics, QCursor, QPainter
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
    QSlider,
    QStyle,
    QStyleOption,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from PyQt6.QtCore import QSettings


def create_fts_index(db_path):
    """Create or rebuild FTS5 index for an existing dictionary using external content."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    total_count = 0

    # Handle dictionary_entries table (Yomitan/JMDict)
    if cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='dictionary_entries'").fetchone():
        table_name = "dictionary_entries"
        fts_table = "dictionary_entries_fts"
        rowid_col = "rowid"

        cursor.execute(f"DROP TABLE IF EXISTS {fts_table}")
        cursor.execute(f"""
            CREATE VIRTUAL TABLE {fts_table} USING fts5(
                headword, reading, glossary,
                content='{table_name}',
                content_rowid='{rowid_col}',
                tokenize='trigram',
                detail=column
            )
        """)
        cursor.execute(f"INSERT INTO {fts_table}({fts_table}) VALUES('rebuild')")
        count = cursor.execute(f"SELECT COUNT(*) FROM {fts_table}").fetchone()[0]
        total_count += count

    # Handle legacy dictionary table (Eijiro)
    if cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='dictionary'").fetchone():
        table_name = "dictionary"
        fts_table = "dictionary_fts"
        rowid_col = "id"

        cursor.execute(f"DROP TABLE IF EXISTS {fts_table}")
        cursor.execute(f"""
            CREATE VIRTUAL TABLE {fts_table} USING fts5(
                definition,
                content='{table_name}',
                content_rowid='{rowid_col}',
                tokenize='trigram',
                detail=column
            )
        """)
        cursor.execute(f"INSERT INTO {fts_table}({fts_table}) VALUES('rebuild')")
        count = cursor.execute(f"SELECT COUNT(*) FROM {fts_table}").fetchone()[0]
        total_count += count

    # Handle personal_dict
    if cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='personal_dict'").fetchone():
        table_name = "personal_dict"
        fts_table = "personal_dict_fts"
        rowid_col = "rowid"

        cursor.execute(f"DROP TABLE IF EXISTS {fts_table}")
        cursor.execute(f"""
            CREATE VIRTUAL TABLE {fts_table} USING fts5(
                definition,
                content='{table_name}',
                content_rowid='{rowid_col}',
                tokenize='trigram',
                detail=column
            )
        """)
        cursor.execute(f"INSERT INTO {fts_table}({fts_table}) VALUES('rebuild')")
        count = cursor.execute(f"SELECT COUNT(*) FROM {fts_table}").fetchone()[0]
        total_count += count

    if total_count == 0:
        conn.close()
        return 0

    # Vacuum to recover space
    cursor.execute("VACUUM")
    conn.close()

    return total_count


def import_dictionary_file(source_path, target_db_path, progress_callback=None, debug_callback=None):
    """
    Import entries from an Eijiro-style text file into a SQLite database.
    Handles both UTF-8 and CP932 (Shift-JIS) encoding.

    Returns (count, debug_info) tuple.
    debug_info is a list of strings for logging.
    """
    # Helper to log
    def log(msg):
        if debug_callback:
            debug_callback(msg)
        print(f"IMPORT: {msg}", file=__import__('sys').stderr)

    # Initialize target database with optimizations
    conn = sqlite3.connect(target_db_path)
    cursor = conn.cursor()

    # Load sqlite-zstd for compression
    try:
        import sqlite_zstd
        conn.enable_load_extension(True)
        sqlite_zstd.load(conn)
        log("sqlite-zstd loaded successfully")
    except Exception as e:
        log(f"sqlite-zstd load failed: {e}")

    # Set page size to 4096 (default) and enable auto_vacuum
    cursor.execute("PRAGMA page_size = 4096")
    cursor.execute("PRAGMA journal_mode = WAL")
    cursor.execute("PRAGMA auto_vacuum = FULL")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dictionary (
            id INTEGER PRIMARY KEY,
            headword TEXT,
            definition TEXT
        )
    """)
    log("Dictionary table created")

    # Enable transparent compression on definition column - do this AFTER inserting data
    # (must have data first for sqlite-zstd to validate the chooser)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_headword ON dictionary(headword)")
    conn.commit()

    # Create FTS5 as external content (references dictionary table, doesn't duplicate data)
    # Only index definition to save space
    cursor.execute("DROP TABLE IF EXISTS dictionary_fts")
    cursor.execute("""
        CREATE VIRTUAL TABLE dictionary_fts USING fts5(
            definition,
            content='dictionary',
            content_rowid='id',
            tokenize='trigram',
            detail=column
        )
    """)
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
                    # id is auto-generated, just headword and definition
                    entries.append((parts[0].strip(), parts[1].strip()))

            if len(entries) >= 20000:
                cursor.executemany("INSERT INTO dictionary (headword, definition) VALUES (?, ?)", entries)
                conn.commit()
                total += len(entries)
                entries = []
                if progress_callback:
                    progress_callback(total)

    # Insert remaining
    if entries:
        cursor.executemany("INSERT INTO dictionary (headword, definition) VALUES (?, ?)", entries)
        total += len(entries)

    conn.commit()

    # Rebuild External Content FTS5 index after inserting data
    # This populates the FTS index from the content table
    try:
        cursor.execute("INSERT INTO dictionary_fts(dictionary_fts) VALUES('rebuild')")
        conn.commit()
        log("FTS5 external content index rebuilt successfully")
    except Exception as e:
        log(f"FTS5 rebuild failed: {e}")

    # Enable transparent compression AFTER inserting data
    try:
        import json
        config = {
            "table": "dictionary",
            "column": "definition",
            "compression_level": 19,
            "dict_chooser": "'a'"
        }
        cursor.execute("SELECT zstd_enable_transparent(?)", (json.dumps(config),))
        # Run maintenance to compress existing data
        cursor.execute("SELECT zstd_incremental_maintenance(null, 1)")
        log("Transparent compression enabled")
    except Exception as e:
        log(f"Transparent compression failed: {e}")

    # Run VACUUM to shrink file after compression
    cursor.execute("VACUUM")
    log("VACUUM done - file should be smaller now")
    conn.close()

    if progress_callback:
        progress_callback(total)

    return total


def export_personal_dict(output_path, format="json"):
    """
    Export personal_dict table to JSON or CSV.
    Returns the number of entries exported.
    """
    conn = sqlite3.connect("yomikata.db")
    cursor = conn.cursor()
    cursor.execute("SELECT headword, definition FROM personal_dict")
    rows = cursor.fetchall()
    conn.close()

    if format == "json":
        import json
        data = [{"headword": row[0], "definition": row[1]} for row in rows]
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    else:  # csv
        import csv
        with open(output_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["headword", "definition"])
            writer.writerows(rows)

    return len(rows)


def import_personal_dict(input_path, format=None):
    """
    Import personal_dict from a JSON or CSV file.
    Returns the number of entries imported.
    """
    if format is None:
        format = os.path.splitext(input_path)[1].lower().lstrip(".")

    conn = sqlite3.connect("yomikata.db")
    cursor = conn.cursor()

    if format == "json":
        import json
        with open(input_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        entries = [(item["headword"], item["definition"]) for item in data]
    else:  # csv
        import csv
        with open(input_path, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            entries = [(row["headword"], row["definition"]) for row in reader]

    cursor.executemany("INSERT OR REPLACE INTO personal_dict VALUES (?, ?)", entries)
    conn.commit()
    conn.close()

    return len(entries)


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
            import sys
            debug_logs = []
            def debug_cb(msg):
                debug_logs.append(msg)
                print(f"IMPORT: {msg}", file=sys.stderr)

            count = import_dictionary_file(
                self.source_path,
                self.target_db_path,
                lambda p: self.progress.emit(p),
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


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings & Debug")
        self.resize(600, 500)
        self.settings = QSettings("Yomikata", "Settings")

        main_layout = QVBoxLayout(self)
        self.tabs = QTabWidget()

        # --- TAB 0: Display ---
        display_tab = QWidget()
        display_layout = QFormLayout(display_tab)

        # Font size control
        font_size_layout = QHBoxLayout()
        self.font_size_slider = QSlider(Qt.Orientation.Horizontal)
        self.font_size_slider.setMinimum(10)
        self.font_size_slider.setMaximum(24)
        self.font_size_slider.setValue(14)
        self.font_size_value_label = QLabel("14px")
        self.font_size_slider.valueChanged.connect(
            lambda v: self.font_size_value_label.setText(f"{v}px")
        )
        font_size_layout.addWidget(self.font_size_slider)
        font_size_layout.addWidget(self.font_size_value_label)
        
        # Load saved font size from parent
        if parent and hasattr(parent, 'settings'):
            saved_size = parent.settings.value("font_size")
            if saved_size:
                self.font_size_slider.setValue(int(saved_size))
                self.font_size_value_label.setText(f"{saved_size}px")
        
        display_layout.addRow("Font Size:", font_size_layout)
        self.tabs.addTab(display_tab, "Display")

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

        # --- TAB 2: History ---
        history_tab = QWidget()
        history_layout = QFormLayout(history_tab)

        # History size control
        history_size_layout = QHBoxLayout()
        self.history_size_slider = QSlider(Qt.Orientation.Horizontal)
        self.history_size_slider.setMinimum(10)
        self.history_size_slider.setMaximum(100)
        self.history_size_slider.setSingleStep(10)
        self.history_size_slider.setValue(50)
        self.history_size_value_label = QLabel("50 entries")
        self.history_size_slider.valueChanged.connect(
            lambda v: self.history_size_value_label.setText(f"{v} entries")
        )

        # Load saved history size
        saved_history = self.settings.value("history_size")
        if saved_history:
            self.history_size_slider.setValue(int(saved_history))
            self.history_size_value_label.setText(f"{saved_history} entries")

        history_size_layout.addWidget(self.history_size_slider)
        history_size_layout.addWidget(self.history_size_value_label)
        history_layout.addRow("History Size:", history_size_layout)

        self.tabs.addTab(history_tab, "History")

        # --- TAB 3: Debug Logs ---
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

        rebuild_fts_btn = QPushButton("Rebuild Search Index")
        rebuild_fts_btn.clicked.connect(self.rebuild_fts_index)

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

        # Format selection
        format_layout = QHBoxLayout()
        format_layout.addWidget(QLabel("Format:"))
        self.import_format = QComboBox()
        self.import_format.addItems(["Text (Eijiro)", "Yomitan (ZIP)", "JMDict (auto)"])
        self.import_format.currentTextChanged.connect(self.on_import_format_changed)
        format_layout.addWidget(self.import_format)
        format_layout.addStretch()
        import_layout.addLayout(format_layout)

        import_layout.addWidget(QLabel("Import Dictionary:"))
        import_layout.addWidget(QLabel("<small>Select a text or ZIP file to import entries into a database.</small>"))

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

        # --- TAB 5: Export ---
        export_tab = QWidget()
        export_layout = QVBoxLayout(export_tab)

        export_layout.addWidget(QLabel("Export Personal Dictionary:"))
        export_layout.addWidget(QLabel("<small>Backup your saved notes and AI explanations.</small>"))

        self.export_format = QComboBox()
        self.export_format.addItems(["JSON", "CSV"])
        format_layout = QHBoxLayout()
        format_layout.addWidget(QLabel("Format:"))
        format_layout.addWidget(self.export_format)
        export_layout.addLayout(format_layout)

        self.export_status = QLabel("")
        export_layout.addWidget(self.export_status)

        export_btn = QPushButton("Export to File...")
        export_btn.clicked.connect(self.export_personal_dict)
        export_layout.addWidget(export_btn)

        import_btn = QPushButton("Import from File...")
        import_btn.clicked.connect(self.import_personal_dict)
        export_layout.addWidget(import_btn)

        export_layout.addStretch()
        self.tabs.addTab(export_tab, "Export")

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

    def rebuild_fts_index(self):
        """Rebuild FTS index for all active dictionaries."""
        current = self.dict_list.currentItem()
        if current:
            db_path = current.text()
        else:
            # Use main db
            db_path = "yomikata.db"

        try:
            count = create_fts_index(db_path)
            if current:
                msg = f"✓ Search index rebuilt: {count} entries indexed."
            else:
                msg = f"✓ Search index rebuilt for personal dict: {count} entries."
        except Exception as e:
            msg = f"Error: {e}"

        # Show message - could add a status label or use QMessageBox
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.information(self, "Rebuild Index", msg)

    def optimize_database(self):
        """Run VACUUM and rebuild FTS indexes."""
        db_path = "yomikata.db"

        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("VACUUM")

            # Rebuild all FTS indexes
            tables = ["personal_dict_fts", "dictionary_entries_fts"]
            for fts_table in tables:
                try:
                    cursor.execute(f"INSERT INTO {fts_table}({fts_table}) VALUES('rebuild')")
                except Exception:
                    pass  # Table might not exist

            conn.commit()
            conn.close()
            msg = "✓ Database optimized (VACUUM + FTS rebuild)"
        except Exception as e:
            msg = f"Error: {e}"

        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.information(self, "Optimize Database", msg)

    def clear_debug_logs(self):
        if self.parent() and hasattr(self.parent(), "debug_logs"):
            self.parent().debug_logs = []
        self.log_viewer.clear()

    def on_import_format_changed(self, format_type):
        """Handle import format dropdown change."""
        if format_type == "Yomitan (ZIP)":
            self.source_file_label.setText("No file selected")
            self.import_status.setText("Select a ZIP file containing Yomitan dictionary.")
        elif format_type == "JMDict (auto)":
            self.source_file_label.setText("Auto-enabled (jamdict)")
            self.import_status.setText("JMDict is auto-loaded via jamdict. No import needed.")
        else:
            self.source_file_label.setText("No file selected")
            self.import_status.setText("")

    def select_source_file(self):
        format_type = self.import_format.currentText()
        if format_type == "Yomitan (ZIP)":
            path, _ = QFileDialog.getOpenFileName(
                self, "Select Yomitan ZIP File", "",
                "ZIP Archives (*.zip);;All Files (*)"
            )
        else:
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
        format_type = self.import_format.currentText()

        # JMDict doesn't need import
        if format_type == "JMDict (auto)":
            self.import_status.setText("JMDict is auto-enabled via jamdict. No import needed.")
            return

        # For Yomitan, handle inline
        if format_type == "Yomitan (ZIP)":
            if not hasattr(self, "source_file"):
                self.import_status.setText("Please select a ZIP file first.")
                return

            target = self.target_db.text()
            if not target or target == "yomikata.db":
                # Default to a new dictionary file
                import datetime
                target = f"Yomitan_{datetime.date.today()}.db"
                self.target_db.setText(target)
            self.import_progress.setVisible(True)
            self.import_progress.setRange(0, 0)  # Indeterminate
            self.import_status.setText("Importing Yomitan...")

            try:
                import sys
                import os
                # Ensure src directory is in path
                src_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                if src_dir not in sys.path:
                    sys.path.insert(0, src_dir)

                from yomitan_parser import import_yomitan_zip

                def progress(current, total):
                    if total > 0:
                        self.import_progress.setRange(0, 100)
                        self.import_progress.setValue(int(current / total * 100))

                count = import_yomitan_zip(self.source_file, target, progress)
                print(f"Yomitan import complete: {count} entries", file=sys.stderr)
                self.import_progress.setVisible(False)
                self.import_status.setText(f"✓ Imported {count:,} entries.")
            except Exception as e:
                import traceback
                print(f"YOMITAN IMPORT ERROR: {e}", file=sys.stderr)
                traceback.print_exc(file=sys.stderr)
                self.import_progress.setVisible(False)
                self.import_status.setText(f"Error: {e}")
            return

        # Text (Eijiro) import - existing logic
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

    def export_personal_dict(self):
        fmt = self.export_format.currentText().lower()
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Personal Dictionary", f"personal_dict.{fmt}",
            f"{fmt.upper()} Files (*.{fmt});;All Files (*)"
        )
        if not path:
            return

        try:
            count = export_personal_dict(path, fmt)
            self.export_status.setText(f"✓ Exported {count} entries.")
        except Exception as e:
            self.export_status.setText(f"Error: {e}")

    def import_personal_dict(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Personal Dictionary", "",
            "Backup Files (*.json *.csv);;All Files (*)"
        )
        if not path:
            return

        try:
            count = import_personal_dict(path)
            self.export_status.setText(f"✓ Imported {count} entries.")
        except Exception as e:
            self.export_status.setText(f"Error: {e}")

    def save_settings(self):
        self.settings.setValue("ai_provider", self.ai_provider.currentText())
        self.settings.setValue("api_url", self.api_url.text())
        self.settings.setValue("api_key", self.api_key.text())
        self.settings.setValue("ai_model", self.ai_model.text())
        
        # Save font size to parent app if it has the update method
        font_size = self.font_size_slider.value()
        self.settings.setValue("font_size", font_size)
        if self.parent() and hasattr(self.parent(), 'update_font_size'):
            self.parent().update_font_size(font_size)

        # Save history size
        history_size = self.history_size_slider.value()
        self.settings.setValue("history_size", history_size)

        self.accept()