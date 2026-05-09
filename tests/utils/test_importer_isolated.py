from utils.importer import import_dictionary_archive


def test_import_dictionary_file(tmp_path):
    # Create a dummy Eijiro-style text file
    source = tmp_path / "sample.txt"
    source.write_text("■猫 : Cat\n■犬 : Dog\n", encoding="utf-8")

    target_db = str(tmp_path / "test_dict.db")

    count = import_dictionary_archive(str(source), target_db)
    assert count == 2

    # Check if database was created and has entries
    import sqlite3
    conn = sqlite3.connect(target_db)
    cursor = conn.cursor()
    cursor.execute("SELECT headword, definition FROM dictionary")
    rows = cursor.fetchall()
    assert len(rows) == 2
    assert ("猫", "Cat") in rows
    assert ("犬", "Dog") in rows
    conn.close()
