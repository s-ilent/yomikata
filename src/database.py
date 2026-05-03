import os
import sqlite3

import fugashi


class DatabaseManager:
    def __init__(self, main_db="yomikata.db"):
        self.main_db = main_db
        self._conn_cache = {}  # Cache open connections
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

    def get_lemma(self, word):
        """Get the base lemma form of a word using Fugashi."""
        tagger = fugashi.Tagger()
        tokens = tagger(word)
        if tokens:
            first = tokens[0]
            if first.feature and first.feature.lemma:
                return first.feature.lemma
        return None

    def lookup(self, word, lemma, extra_paths=None):
        results = []

        # 1. Personal Note
        note = self.get_personal_note(word) or self.get_personal_note(lemma)
        if note:
            results.append(f"### 📝 Personal Note\n{note}")

        # 2. Search all registered DBs
        search_paths = [self.main_db] + (extra_paths or [])
        for path in set(search_paths):
            if not os.path.exists(path):
                continue
            try:
                conn = self.get_conn(path)
                for w in [word, lemma]:
                    res = conn.execute(
                        "SELECT definition FROM dictionary WHERE headword = ?",
                        (w,)
                    ).fetchone()
                    if res:
                        name = os.path.basename(path).replace(".db", "").upper()
                        results.append(f"### 📖 {name}\n{res[0]}")
            except Exception:
                continue

        # 3. De-inflection fallback: if no results, try lemma via Fugashi
        if not results:
            inflected_lemma = self.get_lemma(word)
            if inflected_lemma and inflected_lemma != word:
                # Search personal dict with lemma
                note = self.get_personal_note(inflected_lemma)
                if note:
                    results.append(f"### 📝 Personal Note (de-inflected)\n{note}")

                # Search dictionary DBs with lemma
                for path in set(search_paths):
                    if not os.path.exists(path):
                        continue
                    try:
                        conn = self.get_conn(path)
                        res = conn.execute(
                            "SELECT definition FROM dictionary WHERE headword = ?",
                            (inflected_lemma,)
                        ).fetchone()
                        if res:
                            name = os.path.basename(path).replace(".db", "").upper()
                            results.append(f"### 📖 {name} (de-inflected)\n{res[0]}")
                    except Exception:
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


def search_definitions(query, extra_dicts=None):
    """Search for query inside definitions using FTS5."""
    return _get_db().search_definitions(query, extra_dicts)