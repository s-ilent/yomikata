import sqlite3

DB_PATH = "yomikata.db"


def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Eijiro table
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS dictionary (headword TEXT, definition TEXT)"
    )
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_headword ON dictionary(headword)")

    # Personal Dictionary (for AI suggestions and manual entries)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS personal_dict (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            headword TEXT UNIQUE,
            definition TEXT,
            notes TEXT
        )
    """)
    conn.commit()
    conn.close()


def lookup_word(word, lemma):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Try exact word, then lemma in Personal Dict, then Eijiro
    results = []

    for w in [word, lemma]:
        # 1. Personal Dict
        cursor.execute("SELECT definition FROM personal_dict WHERE headword = ?", (w,))
        res = cursor.fetchone()
        if res:
            results.append(f"<b>[Personal]</b> {res[0]}")

        # 2. Eijiro
        cursor.execute("SELECT definition FROM dictionary WHERE headword = ?", (w,))
        res = cursor.fetchone()
        if res:
            results.append(res[0])

    conn.close()
    return "\n\n".join(list(dict.fromkeys(results)))  # Deduplicate


def save_to_personal_dict(headword, definition):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Using REPLACE to update if the word already exists
    cursor.execute(
        """
        INSERT OR REPLACE INTO personal_dict (headword, definition)
        VALUES (?, ?)
    """,
        (headword, definition),
    )
    conn.commit()
    conn.close()
