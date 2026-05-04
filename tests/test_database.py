import pytest
import sqlite3

def test_db_manager_init(db_manager):
    """Verify that the necessary tables are created."""
    conn = sqlite3.connect(db_manager.main_db)
    cursor = conn.cursor()
    
    # Check for dictionary_entries
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='dictionary_entries'")
    assert cursor.fetchone() is not None, "dictionary_entries table not found"
    
    # Check for personal_dict
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='personal_dict'")
    assert cursor.fetchone() is not None, "personal_dict table not found"
    
    conn.close()

def test_lookup_nonexistent(db_manager):
    """Verify lookup returns empty string for nonexistent word."""
    result = db_manager.lookup("nonexistentword", "nonexistentword", [])
    assert result == ""
