import sys
from pathlib import Path

# Add src to path so we can use database.py
sys.path.append(str(Path(__file__).parent.parent / "src"))
from database import get_connection, init_db


def run_import(file_path):
    init_db()
    conn = get_connection()
    cursor = conn.cursor()

    print(f"Reading {file_path}...")
    entries = []

    # Try UTF-8, fallback to CP932 (Shift-JIS) if needed
    try:
        f = open(file_path, "r", encoding="utf-8")
        f.readline()
        f.seek(0)
    except UnicodeDecodeError:
        f = open(file_path, "r", encoding="cp932")

    with f:
        for line in f:
            if line.startswith("■"):
                parts = line.lstrip("■").split(" : ", 1)
                if len(parts) == 2:
                    entries.append((parts[0].strip(), parts[1].strip()))

            if len(entries) >= 20000:
                cursor.executemany("INSERT INTO dictionary VALUES (?, ?)", entries)
                entries = []
                print(".", end="", flush=True)

    cursor.executemany("INSERT INTO dictionary VALUES (?, ?)", entries)
    conn.commit()
    print("\nImport finished.")


if __name__ == "__main__":
    # Update this path to your actual file location
    run_import("data/WAEIJI-144-10.TXT")
