import sqlite3
import json
import os
from yomitan_parser import parse_yomitan_zip
from database import import_dictionary_file

def import_dictionary_archive(source_path: str, target_db: str) -> int:
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
                dictionary_meta TEXT
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_headword ON dictionary_entries(headword)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_reading ON dictionary_entries(reading)")

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

            conn.execute("""
                INSERT INTO dictionary_entries (headword, reading, pos, pitch_accent, glossary, priority, dictionary_name, dictionary_meta)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (entry['headword'], entry['reading'], pos, entry['pitch_accent'],
                  entry['glossary'], priority, entry['dictionary_name'],
                  json.dumps(entry.get('dictionary_meta', {}))))
            count += 1
            if count % 10000 == 0:
                print(f"  Imported {count} entries...")
        conn.commit()
        conn.close()
        
        from database import create_fts_index
        create_fts_index(target_db)
        return count
    else:
        # Assume Text (Eijiro) format
        return import_dictionary_file(source_path, target_db, progress_callback=lambda p: print(f"Imported {p} entries..."))
