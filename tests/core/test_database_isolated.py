import sqlite3

import pytest

from core.database import DatabaseManager


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test_yomikata.db")

@pytest.fixture
def db_manager(db_path):
    manager = DatabaseManager(main_db=db_path)
    yield manager
    manager.close_all()

def test_init_main_db(db_manager, db_path):
    # Check if tables exist
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='personal_dict'")
    assert cursor.fetchone() is not None
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='history'")
    assert cursor.fetchone() is not None
    conn.close()

def test_personal_note_lifecycle(db_manager):
    word = "テスト"
    note = "This is a test note."

    # Save
    db_manager.save_personal_note(word, note)

    # Get
    retrieved = db_manager.get_personal_note(word)
    assert retrieved == note

    # Update
    new_note = "Updated note."
    db_manager.save_personal_note(word, new_note)
    assert db_manager.get_personal_note(word) == new_note

def test_history_lifecycle(db_manager):
    text = "日本語の勉強"
    db_manager.save_history(text, max_entries=5)

    history = db_manager.get_history(limit=5)
    assert len(history) == 1
    assert history[0][0] == text

    # Deduplication/Update
    db_manager.save_history(text, max_entries=5)
    history = db_manager.get_history(limit=5)
    assert len(history) == 1

    # Limit
    for i in range(10):
        db_manager.save_history(f"text {i}", max_entries=5)

    history = db_manager.get_history(limit=10)
    assert len(history) == 5
    assert history[0][0] == "text 9"

def test_lookup_structured_personal(db_manager):
    word = "猫"
    note = "Cat"
    db_manager.save_personal_note(word, note)

    result = db_manager.lookup_structured(word, word)
    assert result["headword"] == word
    # Should have personal note
    personal_entries = [e for e in result["entries"] if e["source"] == "Personal Note"]
    assert len(personal_entries) == 1
    assert personal_entries[0]["content"] == note


def test_lookup_jmdict_structured_all_strings(db_manager):
    """Test that lookup_jmdict_structured returns plain Python types, not jamdict objects."""
    result = db_manager.lookup_jmdict_structured("猫")
    if result is None:
        pytest.skip("jamdict database not available")

    for entry in result:
        assert isinstance(entry["kanji"], str), f"Expected str, got {type(entry['kanji'])}"
        assert isinstance(entry["kana"], str), f"Expected str, got {type(entry['kana'])}"
        for sense in entry["senses"]:
            for gloss in sense["gloss"]:
                assert isinstance(gloss, str), f"Expected str, got {type(gloss)}: {gloss}"
            for pos in sense["pos"]:
                assert isinstance(pos, str), f"Expected str, got {type(pos)}: {pos}"


def test_lookup_jmdict_text_is_clean(db_manager):
    """Test that the text lookup_jmdict returns clean text (no SenseGloss TypeError)."""
    result = db_manager.lookup_jmdict("猫")
    if result is None:
        pytest.skip("jamdict database not available")

    assert isinstance(result, str)
    assert "**" not in result
    assert "猫" in result


def test_lookup_jmdict_structured_json_serializable(db_manager):
    """Test that structured JMDict data is JSON-serializable (no custom objects)."""
    import json

    result = db_manager.lookup_jmdict_structured("猫")
    if result is None:
        pytest.skip("jamdict database not available")

    serialized = json.dumps(result, ensure_ascii=False)
    assert isinstance(serialized, str)
    deserialized = json.loads(serialized)
    assert deserialized == result
