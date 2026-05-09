import json
import os
import sqlite3
import sys

from PyQt6.QtCore import QThread
from PyQt6.QtCore import pyqtSignal as QtSignal

from core.database import create_fts_index, import_dictionary_file
from yomitan_parser import parse_yomitan_zip


def import_dictionary_archive(source_path: str, target_db: str, progress_callback=None) -> int:
    """Orchestrate the import of a dictionary from either a Yomitan ZIP or an Eijiro-style text file."""
    # Ensure a clean slate
    if os.path.exists(target_db):
        os.remove(target_db)

    print(f"Importing {source_path} -> {target_db}...")

    if source_path.lower().endswith('.zip'):
        conn = sqlite3.connect(target_db)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS dictionary_entries (
                id INTEGER PRIMARY KEY,
                headword TEXT NOT NULL,
                reading TEXT,
                pos TEXT,
                pitch_accent TEXT,
                glossary TEXT NOT NULL,
                priority INTEGER DEFAULT 0,
                dictionary_name TEXT,
                dictionary_meta TEXT,
                UNIQUE(headword, reading, dictionary_name)
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_headword ON dictionary_entries(headword)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_reading ON dictionary_entries(reading)")

        # For ZIPs, we can't easily know total ahead of time without pre-parsing everything.
        # We'll use a simple count-only progress if callback is provided
        count = 0
        for entry in parse_yomitan_zip(source_path):
            # Ensure 'pos' is a string before inserting.
            pos = entry['pos']
            if isinstance(pos, list):
                pos = ", ".join([str(p) for p in pos])
            elif pos is None:
                pos = ""
            else:
                pos = str(pos)

            # Ensure priority is an int
            priority = entry['priority']
            if not isinstance(priority, int):
                try:
                    priority = int(priority)
                except (ValueError, TypeError):
                    priority = 0

            cursor.execute("""
                INSERT OR IGNORE INTO dictionary_entries (headword, reading, pos, pitch_accent, glossary, priority, dictionary_name, dictionary_meta)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (entry['headword'], entry['reading'], pos, entry['pitch_accent'],
                  entry['glossary'], priority, entry['dictionary_name'],
                  json.dumps(entry.get('dictionary_meta', {}))))
            count += 1
            if count % 1000 == 0 and progress_callback:
                progress_callback(count, None) # Indeterminate
        conn.commit()
        conn.close()

        create_fts_index(target_db)
        return count
    else:
        # Assume Text (Eijiro) format
        return import_dictionary_file(source_path, target_db, progress_callback=progress_callback)


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
            debug_logs = []
            def debug_cb(msg):
                debug_logs.append(msg)
                print(f"IMPORT: {msg}", file=sys.stderr)

            # Updated progress handler
            def progress_cb(current, total):
                if total:
                    self.progress.emit(int((current / total) * 100))
                else:
                    # Indeterminate: cycle through 10-90% to show activity
                    self.progress.emit(10 + (current % 80))

            if self.import_format == "Yomitan (ZIP)":
                count = import_dictionary_archive(self.source_path, self.target_db_path, progress_callback=progress_cb)
            else:
                count = import_dictionary_file(
                    self.source_path,
                    self.target_db_path,
                    progress_callback=lambda p: progress_cb(p, None), # Assuming old files don't report total
                    debug_callback=debug_cb
                )

            self.finished.emit(count)
            # Send debug logs to parent if possible
            if self.parent() and hasattr(self.parent(), "debug_logs"):
                self.parent().debug_logs.extend(debug_logs)
        except Exception as e:
            self.error.emit(str(e))
