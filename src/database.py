import ast
import json
import logging
import os
import re
import sqlite3

import jamdict_data
from jamdict import Jamdict

from yomitan_parser import _flatten_content

# Configure logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("yomikata.database")


class DatabaseManager:
    def __init__(self, main_db="yomikata.db"):
        self.main_db = main_db
        self._conn_cache = {}  # Cache open connections
        # Initialize jamdict for JMDict lookups
        # Use jamdict-data pre-built database
        db_path = os.path.join(os.path.dirname(jamdict_data.__file__), 'jamdict.db')
        self.jam = Jamdict(db_path=db_path)
        self.init_main_db()

    def get_conn(self, db_path=None):
        if db_path is None:
            db_path = self.main_db

        # Return cached connection if available
        if db_path in self._conn_cache:
            conn = self._conn_cache[db_path]
            try:
                # Verify connection is still valid
                conn.execute("SELECT 1")
                return conn
            except Exception as e:
                logger.warning(f"Connection to {db_path} dead, removing from cache: {e}")
                del self._conn_cache[db_path]

        logger.info(f"Creating new database connection: {db_path}")
        # Create new connection with sqlite-zstd
        try:
            conn = sqlite3.connect(db_path, check_same_thread=False, timeout=10)
            conn.execute("PRAGMA journal_mode = WAL")
            try:
                import sqlite_zstd
                conn.enable_load_extension(True)
                sqlite_zstd.load(conn)
            except Exception as e:
                logger.debug(f"Could not load sqlite-zstd for {db_path}: {e}")
            self._conn_cache[db_path] = conn
            return conn
        except Exception as e:
            logger.error(f"Failed to connect to {db_path}: {e}")
            raise

    def close_all(self):
        """Close all cached connections."""
        for conn in self._conn_cache.values():
            conn.close()
        self._conn_cache.clear()

    def _execute(self, conn, query, params=()):
        """Execute a query and commit immediately."""
        conn.execute(query, params)
        conn.commit()

    def init_main_db(self):
        conn = self.get_conn(self.main_db)
        cursor = conn.cursor()
        # Personal notes
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS personal_dict (
                headword TEXT PRIMARY KEY,
                definition TEXT
            )
        """)
        # Create FTS for personal notes - index only definition to save space
        cursor.execute("DROP TABLE IF EXISTS personal_dict_fts")
        cursor.execute("""
            CREATE VIRTUAL TABLE personal_dict_fts USING fts5(
                definition, 
                content='personal_dict',
                tokenize='trigram',
                detail=column
            )
        """)
        # Sync FTS for personal notes
        cursor.execute("INSERT INTO personal_dict_fts(personal_dict_fts) VALUES('rebuild')")

        # Main dictionary (Eijiro)
        cursor.execute("CREATE TABLE IF NOT EXISTS dictionary (headword TEXT, definition TEXT)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_headword ON dictionary(headword)")

        # History for previously analyzed texts
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL,
                normalized_text TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_normalized ON history(normalized_text)")

        # Rich dictionary table for modern formats
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
                UNIQUE(headword, reading, dictionary_name)
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_headword_rich ON dictionary_entries(headword)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_reading ON dictionary_entries(reading)")

        # FTS5 for rich definitions
        cursor.execute("DROP TABLE IF EXISTS dictionary_entries_fts")
        cursor.execute("""
            CREATE VIRTUAL TABLE dictionary_entries_fts USING fts5(
                headword, reading, glossary,
                tokenize='trigram',
                detail=column
            )
        """)
        conn.commit()

    def save_personal_note(self, word, definition):
        conn = self.get_conn(self.main_db)
        cursor = conn.cursor()

        # Get old definition to properly delete from FTS index
        old_res = cursor.execute("SELECT definition FROM personal_dict WHERE headword = ?", (word,)).fetchone()
        if old_res:
            cursor.execute("INSERT INTO personal_dict_fts(personal_dict_fts, definition) VALUES('delete', ?)", (old_res[0],))

        cursor.execute(
            "INSERT OR REPLACE INTO personal_dict VALUES (?, ?)",
            (word, definition)
        )

        # Insert new entry into FTS
        cursor.execute("INSERT INTO personal_dict_fts(definition) VALUES (?)", (definition,))
        conn.commit()

    def get_personal_note(self, word):
        conn = self.get_conn(self.main_db)
        res = conn.execute(
            "SELECT definition FROM personal_dict WHERE headword = ?",
            (word,)
        ).fetchone()
        return res[0] if res else None

    def save_history(self, text: str, max_entries: int = 50):
        """Save text to history, deduplicating by normalized form (whitespace collapsed)."""

        if not text.strip():
            return

        normalized = re.sub(r'\s+', ' ', text.strip())
        conn = self.get_conn(self.main_db)
        cursor = conn.cursor()

        # Check if already exists in history
        exists = cursor.execute(
            "SELECT id FROM history WHERE normalized_text = ?",
            (normalized,)
        ).fetchone()

        if exists:
            # Update timestamp
            cursor.execute(
                "UPDATE history SET timestamp = CURRENT_TIMESTAMP WHERE id = ?",
                (exists[0],)
            )
        else:
            # Insert new
            cursor.execute(
                "INSERT INTO history (text, normalized_text) VALUES (?, ?)",
                (text, normalized)
            )

        # Enforce limit
        cursor.execute("""
            DELETE FROM history WHERE id NOT IN (
                SELECT id FROM history ORDER BY timestamp DESC LIMIT ?
            )
        """, (max_entries,))
        conn.commit()

    def get_history(self, limit: int = 50):
        conn = self.get_conn(self.main_db)
        res = conn.execute(
            "SELECT text, timestamp FROM history ORDER BY timestamp DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return res

    def get_inflected_forms(self, word):
        """Use fugashi/MeCab to guess potential lemma/inflected forms."""
        # Simple implementation for now - just returns a list with the word itself
        # In a real app, this would use fugashi to get dictionary forms
        return [word]

    def lookup_jmdict(self, word):
        """Look up word in JMDict via jamdict and return formatted string."""
        try:
            # Check if jamdict is properly initialized
            if not self.jam.is_available():
                return None

            result = self.jam.lookup(word)
            if not result.entries:
                return None

            output = []
            for entry in result.entries:
                # JMDEntry uses text(), kanji_forms, kana_forms, senses
                headwords = entry.kanji_forms or []
                readings = entry.kana_forms or []
                # Use the first kanji as headword, first kana as reading
                headword = headwords[0] if headwords else ""
                reading = readings[0] if readings else ""
                # Use text() for formatted glossary
                glossary = entry.text() or ""
                if headword and glossary:
                    output.append(f"**{headword}** [{reading}]<br>{glossary}")

            return "<br><br>".join(output) if output else None
        except Exception as e:
            print(f"JMDict lookup error: {e}")
            return None

    def lookup(self, word, lemma, extra_paths=None):
        results = []

        # 1. Personal Note
        note = self.get_personal_note(word) or self.get_personal_note(lemma)
        if note:
            results.append(f"### 📝 Personal Note\n{note}")

        # 2. JMDict via jamdict
        jm_result = self.lookup_jmdict(word)
        if jm_result:
            results.append(f"### 📖 JMDict\n{jm_result}")

        # 3. Search all registered DBs with multiple forms
        search_paths = [self.main_db] + (extra_paths or [])

        # Collect all forms to search
        forms_to_try = [word]
        inflected_forms = self.get_inflected_forms(word)
        for form in inflected_forms:
            if form and form != word and form != lemma and form not in forms_to_try:
                forms_to_try.append(form)

        if lemma and lemma != word and lemma not in forms_to_try:
            forms_to_try.append(lemma)

        for path in set(search_paths):
            if not os.path.exists(path):
                continue

            db_name = os.path.basename(path)
            conn = self.get_conn(path)

            # Try to search 'dictionary_entries' (rich) table
            has_rich = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='dictionary_entries'"
            ).fetchone()

            found_in_this_db = False
            if has_rich:
                for form in forms_to_try:
                    res = conn.execute(
                        "SELECT reading, glossary FROM dictionary_entries WHERE headword = ? OR reading = ?",
                        (form, form)
                    ).fetchall()
                    if res:
                        for r, g in res:
                            # Try to parse as structured content and flatten
                            # Check for dict-like patterns: { or {{
                            g_stripped = g.strip() if isinstance(g, str) else ""
                            if g_stripped.startswith(('{', '[', "'{'")):
                                try:
                                    # Try JSON first
                                    try:
                                        parsed = json.loads(g)
                                    except json.JSONDecodeError:
                                        # Fall back to Python literal_eval for dict repr
                                        parsed = ast.literal_eval(g)
                                    g = _flatten_content(parsed)
                                except (json.JSONDecodeError, TypeError, ValueError, SyntaxError):
                                    pass  # Keep original string
                            results.append(f"### 📖 {db_name} ({form} [{r}])\n{g}")
                        found_in_this_db = True
                        break # Only take the best match form

            # Try to search 'dictionary' (legacy) table if not found or no rich table
            if not found_in_this_db:
                has_legacy = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='dictionary'"
                ).fetchone()
                if has_legacy:
                    for form in forms_to_try:
                        res = conn.execute(
                            "SELECT definition FROM dictionary WHERE headword = ?",
                            (form,)
                        ).fetchall()
                        if res:
                            for definition, in res:
                                results.append(f"### 📖 {db_name} ({form})\n{definition}")
                            break

        return "\n\n---\n\n".join(results)

    def search_definitions(self, query, extra_paths=None):
        """Search for query inside definitions using FTS5."""
        results = []

        # Sanitize query for FTS5
        sanitized_query = query.replace('"', '""')
        if not sanitized_query:
            return ""

        # Use LIKE fallback for short queries or if FTS fails
        use_like_fallback = len(query) < 3

        search_paths = [self.main_db] + (extra_paths or [])
        for path in set(search_paths):
            if not os.path.exists(path):
                continue

            db_name = os.path.basename(path)
            conn = self.get_conn(path)

            try:
                # 1. Search Personal Notes FTS if it exists
                if path == self.main_db:
                    has_personal_fts = conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name='personal_dict_fts'"
                    ).fetchone()
                    if has_personal_fts:
                        res = conn.execute(
                            """SELECT p.headword, p.definition 
                               FROM personal_dict_fts f 
                               JOIN personal_dict p ON p.rowid = f.rowid 
                               WHERE f.definition MATCH ? ORDER BY rank LIMIT 5""",
                            (sanitized_query,)
                        ).fetchall()

                        if not res and use_like_fallback:
                            res = conn.execute(
                                "SELECT headword, definition FROM personal_dict WHERE definition LIKE ? LIMIT 5",
                                (f"%{query}%",)
                            ).fetchall()

                        for headword, definition in res:
                            results.append(f"### 📝 Personal Note (search: {headword})\n{definition}")

                # 2. Search Dictionary FTS
                table_exists = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='dictionary_fts'"
                ).fetchone()
                if table_exists:
                    res = conn.execute(
                        """SELECT d.headword, d.definition 
                           FROM dictionary_fts f
                           JOIN dictionary d ON d.id = f.rowid
                           WHERE f.definition MATCH ? ORDER BY rank LIMIT 10""",
                        (sanitized_query,)
                    ).fetchall()

                    if not res and use_like_fallback:
                        res = conn.execute(
                            "SELECT headword, definition FROM dictionary WHERE definition LIKE ? LIMIT 10",
                            (f"%{query}%",)
                        ).fetchall()

                    if res:
                        for headword, definition in res:
                            results.append(f"### 📖 {db_name} (search: {headword})\n{definition}")

                # 3. Search rich dictionary entries FTS
                rich_fts_exists = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='dictionary_entries_fts'"
                ).fetchone()
                if rich_fts_exists:
                    res = conn.execute(
                        """SELECT d.headword, d.reading, d.glossary 
                           FROM dictionary_entries_fts f
                           JOIN dictionary_entries d ON d.rowid = f.rowid
                           WHERE f.glossary MATCH ? OR f.headword MATCH ? ORDER BY rank LIMIT 10""",
                        (sanitized_query, sanitized_query)
                    ).fetchall()
                    if res:
                        for h, r, g in res:
                            results.append(f"### 📖 {db_name} (search: {h} [{r}])\n{g}")

            except Exception:
                # Fallback to LIKE
                try:
                    res = conn.execute(
                        "SELECT headword, definition FROM dictionary WHERE definition LIKE ? LIMIT 10",
                        (f"%{query}%",)
                    ).fetchall()
                    if res:
                        for headword, definition in res:
                            results.append(f"### 📖 {db_name} (search: {headword})\n{definition}")
                except Exception:
                    continue

        return "\n\n---\n\n".join(results)

# Standalone helper functions
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

    # Commit any pending transactions before VACUUM
    conn.commit()

    # Vacuum to recover space
    cursor.execute("VACUUM")
    conn.close()

    return total_count


def import_dictionary_file(source_path, target_db_path, progress_callback=None, debug_callback=None):
    """Import entries from an Eijiro-style text file into a SQLite database."""
    def log(msg):
        if debug_callback:
            debug_callback(msg)

    conn = sqlite3.connect(target_db_path)
    cursor = conn.cursor()

    try:
        import sqlite_zstd
        conn.enable_load_extension(True)
        sqlite_zstd.load(conn)
    except Exception:
        pass

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
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_headword ON dictionary(headword)")

    # Detect encoding
    try:
        f = open(source_path, encoding="utf-8")
        f.readline()
        f.seek(0)
    except UnicodeDecodeError:
        f = open(source_path, encoding="cp932")

    entries = []
    total = 0
    with f:
        for line in f:
            if line.startswith("■"):
                parts = line.lstrip("■").split(" : ", 1)
                if len(parts) == 2:
                    entries.append((parts[0].strip(), parts[1].strip()))

            if len(entries) >= 20000:
                cursor.executemany("INSERT INTO dictionary (headword, definition) VALUES (?, ?)", entries)
                conn.commit()
                total += len(entries)
                entries = []
                if progress_callback:
                    progress_callback(total)

    if entries:
        cursor.executemany("INSERT INTO dictionary (headword, definition) VALUES (?, ?)", entries)
        total += len(entries)

    conn.commit()
    create_fts_index(target_db_path)
    conn.close()

    if progress_callback:
        progress_callback(total)

    return total


def export_personal_dict(output_path, format="json"):
    """Export personal_dict table to JSON or CSV."""
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
    """Import personal_dict from a JSON or CSV file."""
    if format is None:
        format = os.path.splitext(input_path)[1].lower().lstrip(".")

    conn = sqlite3.connect("yomikata.db")
    cursor = conn.cursor()

    if format == "json":
        import json
        with open(input_path, encoding="utf-8") as f:
            data = json.load(f)
        entries = [(item["headword"], item["definition"]) for item in data]
    else:  # csv
        import csv
        with open(input_path, encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            entries = [(row["headword"], row["definition"]) for row in reader]

    cursor.executemany("INSERT OR REPLACE INTO personal_dict VALUES (?, ?)", entries)
    conn.commit()
    conn.close()
    return len(entries)

def import_yomitan_zip(zip_path: str, db_path: str, progress_callback=None) -> int:
    """Import Yomitan ZIP into the database."""
    from yomitan_parser import parse_yomitan_zip
    entries = list(parse_yomitan_zip(zip_path))
    total = len(entries)

    conn = sqlite3.connect(db_path)
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
            UNIQUE(headword, reading, dictionary_name)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_headword_rich ON dictionary_entries(headword)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_reading ON dictionary_entries(reading)")
    conn.commit()

    batch_size = 1000
    for i in range(0, total, batch_size):
        batch = entries[i:i+batch_size]
        for entry in batch:
            cursor.execute("""
                INSERT OR IGNORE INTO dictionary_entries 
                (headword, reading, pos, pitch_accent, glossary, priority, dictionary_name)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                entry['headword'],
                entry['reading'],
                entry['pos'],
                entry['pitch_accent'],
                entry['glossary'],
                entry['priority'],
                entry['dictionary_name']
            ))
        conn.commit()
        if progress_callback:
            progress_callback(min(i + batch_size, total), total)

    conn.close()
    create_fts_index(db_path)
    return total

# Global instance for backward compatibility
_db = None

def _get_db():
    global _db
    if _db is None:
        _db = DatabaseManager()
    return _db

def init_db():
    """Initialize the database (creates tables if needed)."""
    _get_db().init_main_db()

def lookup_word(word, lemma, extra_dicts=None):
    """Backward-compatible lookup function."""
    return _get_db().lookup(word, lemma, extra_dicts)

def save_to_personal_dict(word, definition):
    """Backward-compatible save function."""
    _get_db().save_personal_note(word, definition)

def get_personal_note(word):
    """Get a personal note for a word."""
    return _get_db().get_personal_note(word)

def save_history(text: str, max_entries: int = 50):
    """Backward-compatible save history function."""
    _get_db().save_history(text, max_entries)

def get_history(limit: int = 50):
    """Backward-compatible get history function."""
    return _get_db().get_history(limit)

def search_definitions(query, extra_dicts=None):
    """Search for query inside definitions using FTS5."""
    return _get_db().search_definitions(query, extra_dicts)
