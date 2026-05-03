import os
import sqlite3


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
        # Main dictionary (Eijiro)
        cursor.execute("CREATE TABLE IF NOT EXISTS dictionary (headword TEXT, definition TEXT)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_headword ON dictionary(headword)")
        conn.commit()

    def save_personal_note(self, word, definition):
        conn = self.get_conn(self.main_db)
        conn.execute(
            "INSERT OR REPLACE INTO personal_dict VALUES (?, ?)",
            (word, definition)
        )
        conn.commit()

    def get_personal_note(self, word):
        conn = self.get_conn(self.main_db)
        res = conn.execute(
            "SELECT definition FROM personal_dict WHERE headword = ?",
            (word,)
        ).fetchone()
        return res[0] if res else None

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

        return "\n\n---\n\n".join(results)

    def search_definitions(self, query, extra_paths=None):
        """Search for query inside definitions using FTS5."""
        results = []
        search_paths = [self.main_db] + (extra_paths or [])

        for path in set(search_paths):
            if not os.path.exists(path):
                continue
            try:
                conn = self.get_conn(path)
                # Check if FTS table exists
                table_exists = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='dictionary_fts'"
                ).fetchone()
                if not table_exists:
                    continue

                # FTS5 search
                res = conn.execute(
                    "SELECT headword, definition FROM dictionary_fts WHERE dictionary_fts MATCH ? LIMIT 10",
                    (query,)
                ).fetchall()
                if res:
                    name = os.path.basename(path).replace(".db", "").upper()
                    for headword, definition in res:
                        def_text = definition
                        results.append(f"### 📖 {name} (search: {headword})\n{def_text}")
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