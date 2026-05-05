import logging
from database import DatabaseManager

logger = logging.getLogger("yomikata.dictionary_service")

class DictionaryService:
    def __init__(self, db_manager: DatabaseManager) -> None:
        self.db_manager = db_manager

    def lookup(self, word: str, lemma: str, extra_paths: list[str] | None = None) -> str:
        """
        Coordinate lookup across personal notes, JMDict, and multiple dictionary databases.
        """
        logger.info(f"Lookup request for word: '{word}', lemma: '{lemma}'")
        try:
            result = self.db_manager.lookup(word, lemma, extra_paths)
            logger.info(f"Lookup successful for '{word}'")
            return result
        except Exception as e:
            logger.error(f"Lookup failed for '{word}': {e}")
            raise

    def search_definitions(self, query: str, extra_paths: list[str] | None = None) -> str:
        """
        Search for query inside definitions using FTS5 across available databases.
        """
        logger.info(f"FTS5 search request: '{query}'")
        try:
            result = self.db_manager.search_definitions(query, extra_paths)
            logger.info(f"FTS5 search completed for '{query}'")
            return result
        except Exception as e:
            logger.error(f"FTS5 search failed for '{query}': {e}")
            raise

    def save_personal_note(self, word: str, definition: str) -> None:
        """
        Save or update a personal note for a word.
        """
        logger.info(f"Saving personal note for: '{word}'")
        self.db_manager.save_personal_note(word, definition)
        logger.info(f"Personal note saved for '{word}'")

    def get_personal_note(self, word: str) -> str | None:
        """
        Retrieve a personal note for a word.
        """
        note = self.db_manager.get_personal_note(word)
        return str(note) if note else None

