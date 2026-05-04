import os
import sqlite3

import fugashi
from jamdict import Jamdict


class DatabaseManager:
    def __init__(self, main_db="yomikata.db"):
        self.main_db = main_db
        self._conn_cache = {}  # Cache open connections
        self.init_main_db()
        # Initialize jamdict for JMDict lookups
        self.jam = Jamdict()

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
            except Exception:
                # Connection dead, remove from cache
                del self._conn_cache[db_path]
        
        # Create new connection with sqlite-zstd
        conn = sqlite3.connect(db_path, check_same_thread=False)
        try:
            import sqlite_zstd
            conn.enable_load_extension(True)
            sqlite_zstd.load(conn)
        except Exception:
            pass  # Extension not available
        self._conn_cache[db_path] = conn
        return conn

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
        import re
        from PyQt6.QtCore import QDateTime
        # Normalize: collapse all whitespace to single space, strip
        normalized = re.sub(r'\s+', ' ', text).strip()
        if not normalized:
            return

        conn = self.get_conn(self.main_db)
        cursor = conn.cursor()

        # Check if this normalized text already exists
        existing = cursor.execute(
            "SELECT id FROM history WHERE normalized_text = ?",
            (normalized,)
        ).fetchone()

        if existing:
            # Update timestamp to move to top
            cursor.execute(
                "UPDATE history SET timestamp = CURRENT_TIMESTAMP WHERE id = ?",
                (existing[0],)
            )
        else:
            # Insert new entry
            cursor.execute(
                "INSERT INTO history (text, normalized_text) VALUES (?, ?)",
                (text, normalized)
            )

            # Keep only last max_entries entries
            cursor.execute("""
                DELETE FROM history WHERE id NOT IN (
                    SELECT id FROM history ORDER BY timestamp DESC LIMIT ?
                )
            """, (max_entries,))

        conn.commit()

    def get_history(self, limit: int = 50):
        """Get recent history entries ordered by timestamp descending."""
        conn = self.get_conn(self.main_db)
        res = conn.execute(
            "SELECT text, timestamp FROM history ORDER BY timestamp DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return res

    def get_lemma(self, word):
        """Get the base lemma form of a word using Fugashi."""
        tagger = fugashi.Tagger()
        tokens = tagger(word)
        if tokens:
            first = tokens[0]
            if first.feature and first.feature.lemma:
                return first.feature.lemma
        return None

    def get_inflected_forms(self, word):
        """Get various inflected forms of a word using Fugashi.

        Returns a list of inflected forms that might exist in the dictionary,
        making lookup more comprehensive. This includes past tense, te-form,
        and other common inflections.
        """
        forms = []
        try:
            tagger = fugashi.Tagger()
            tokens = tagger(word)
            if tokens:
                first = tokens[0]
                # Use conjugations attribute if available
                if hasattr(first, 'conjugations') and first.conjugations:
                    for conj in first.conjugations:
                        if conj.form:
                            forms.append(conj.form)
        except Exception:
            pass
        return forms

    def lookup_jmdict(self, word):
        """Look up word in JMDict via jamdict."""
        try:
            result = self.jam.lookup(word)
            if not result.entries:
                return None

            entries = []
            for entry in result.entries:
                text = entry.text()
                entries.append(text)

            return "\n\n".join(entries)
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

        # Collect all forms to search: exact word first, then inflected, lemma last
        forms_to_try = [word]  # Exact word highest priority

        # Add inflected forms after exact word (but before lemma)
        inflected_forms = self.get_inflected_forms(word)
        for form in inflected_forms:
            if form and form != word and form != lemma and form not in forms_to_try:
                forms_to_try.append(form)

        # Add lemma LAST - lowest priority (least specific match)
        if lemma and lemma != word and lemma not in forms_to_try:
            forms_to_try.append(lemma)

        for path in set(search_paths):
            if not os.path.exists(path):
                continue
            try:
                conn = self.get_conn(path)

                # Search legacy dictionary table (if it exists)
                try:
                    for w in forms_to_try:
                        res = conn.execute(
                            "SELECT definition FROM dictionary WHERE headword = ?",
                            (w,)
                        ).fetchone()
                        if res:
                            name = os.path.basename(path).replace(".db", "").upper()
                            results.append(f"### 📖 {name}\n{res[0]}")
                except Exception:
                    pass  # Table might not exist

                # Search new dictionary_entries table (Yomitan/JMDict)
                try:
                    for w in forms_to_try:
                        # Search by headword OR by reading (for Yomitan dictionaries)
                        res = conn.execute(
                            "SELECT glossary, reading, pos, dictionary_name, headword FROM dictionary_entries WHERE headword = ? OR reading = ?",
                            (w, w)
                        ).fetchone()
                        if res:
                            db_name = res[3] or os.path.basename(path).replace(".db", "").upper()
                            glossary = res[0]
                            reading = res[1] or ""
                            pos = res[2] or ""
                            headword = res[4]
                            # Format nicely
                            entry = f"**{headword}**"
                            if reading and reading != headword:
                                entry += f" [{reading}]"
                            if pos:
                                entry += f" <{pos}>"
                            entry += f"\n\n{glossary}"
                            results.append(f"### 📖 {db_name}\n{entry}")
                except Exception as e:
                    print(f"dictionary_entries error: {e}", file=__import__('sys').stderr)
            except Exception as e:
                print(f"Lookup error for {path}: {e}", file=__import__('sys').stderr)
                continue

        return "\n\n---\n\n".join(results)

    def search_definitions(self, query, extra_paths=None):
        """Search for query inside definitions using FTS5 with ranking, sanitization, and LIKE fallback."""
        results = []
        search_paths = [self.main_db] + (extra_paths or [])
        
        # Determine if we should use LIKE fallback for short queries (especially Japanese/Unicode)
        # Trigram needs 3+ characters to be effective.
        use_like_fallback = len(query) < 3 or any(ord(c) > 127 for c in query)

        # Sanitize query: split into words and wrap each in quotes to prevent syntax errors
        # but allow multiple words to be ANDed.
        parts = query.split()
        if not parts:
            return ""
        sanitized_query = " AND ".join(['"' + p.replace('"', '""') + '"' for p in parts])

        for path in set(search_paths):
            if not os.path.exists(path):
                continue
            try:
                conn = self.get_conn(path)
                db_name = os.path.basename(path).replace(".db", "").upper()

                # 1. Search Personal Notes if this is the main DB
                if path == self.main_db:
                    table_exists = conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name='personal_dict_fts'"
                    ).fetchone()
                    if table_exists:
                        # Try FTS first
                        res = conn.execute(
                            """SELECT p.headword, p.definition 
                               FROM personal_dict_fts f 
                               JOIN personal_dict p ON p.rowid = f.rowid 
                               WHERE f.definition MATCH ? ORDER BY rank LIMIT 5""",
                            (sanitized_query,)
                        ).fetchall()
                        
                        # Fallback to LIKE if no results and query is short/unicode
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
                if not table_exists:
                    continue

                # FTS5 search with BM25 ranking. 
                # We join with 'dictionary' because FTS only indexes the definition column now.
                res = conn.execute(
                    """SELECT d.headword, d.definition 
                       FROM dictionary_fts f
                       JOIN dictionary d ON d.id = f.rowid
                       WHERE f.definition MATCH ? ORDER BY rank LIMIT 10""",
                    (sanitized_query,)
                ).fetchall()
                
                # Fallback to LIKE if no results and query is short/unicode
                if not res and use_like_fallback:
                    res = conn.execute(
                        "SELECT headword, definition FROM dictionary WHERE definition LIKE ? LIMIT 10",
                        (f"%{query}%",)
                    ).fetchall()
                
                if res:
                    for headword, definition in res:
                        results.append(f"### 📖 {db_name} (search: {headword})\n{definition}")
            except Exception as e:
                # Fallback to LIKE on any error (like FTS syntax error)
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