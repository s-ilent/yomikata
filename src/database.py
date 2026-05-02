import os
import sqlite3

DB_PATH = "yomikata.db"


def get_connection():
    return sqlite3.connect(DB_PATH)


def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dictionary (
            headword TEXT,
            definition TEXT
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_headword ON dictionary(headword)")

    # Phrase history table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            original TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def lookup_eijiro(word):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT definition FROM dictionary WHERE headword = ?", (word,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None
