from typing import List, Optional, Dict
from database import DatabaseManager

class DictionaryService:
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

    def lookup(self, word: str, lemma: str, extra_paths: Optional[List[str]] = None) -> str:
        """
        Coordinate lookup across personal notes, JMDict, and multiple dictionary databases.
        """
        return self.db_manager.lookup(word, lemma, extra_paths)

    def search_definitions(self, query: str, extra_paths: Optional[List[str]] = None) -> str:
        """
        Search for query inside definitions using FTS5 across available databases.
        """
        return self.db_manager.search_definitions(query, extra_paths)

    def save_personal_note(self, word: str, definition: str):
        """
        Save or update a personal note for a word.
        """
        self.db_manager.save_personal_note(word, definition)

    def get_personal_note(self, word: str) -> Optional[str]:
        """
        Retrieve a personal note for a word.
        """
        return self.db_manager.get_personal_note(word)
