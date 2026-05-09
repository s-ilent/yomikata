import logging

from core.database import DatabaseManager

logger = logging.getLogger("yomikata.dictionary_service")

class DictionaryService:
    def __init__(self, db_manager: DatabaseManager) -> None:
        """
        Initializes the service with a database manager instance.

        Args:
            db_manager: The central engine for SQLite interactions.
        """
        self.db_manager = db_manager

    def lookup(self, word: str, lemma: str, extra_paths: list[str] | None = None) -> str:
        """
        Coordinate lookup across personal notes, JMDict, and multiple dictionary databases.

        Args:
            word: The surface form to lookup.
            lemma: The base dictionary form of the word.
            extra_paths: List of file paths for additional databases.

        Returns:
            A formatted string containing definition content or an empty string.
        """
        logger.info(f"Lookup request for word: '{word}', lemma: '{lemma}'")
        try:
            # Delegate lookup task to DatabaseManager; it handles the heavy lifting
            # of searching multiple tables and parsing structured content.
            result = self.db_manager.lookup(word, lemma, extra_paths)
            logger.info(f"Lookup successful for '{word}'")
            return result
        except Exception as e:
            logger.error(f"Lookup failed for '{word}': {e}")
            raise

    def search_definitions(self, query: str, extra_paths: list[str] | None = None) -> str:
        """
        Search for query inside definitions using FTS5 across available databases.

        Args:
            query: The search term.
            extra_paths: Optional list of additional database file paths.

        Returns:
            Formatted search results string.
        """
        logger.info(f"FTS5 search request: '{query}'")
        try:
            # Perform Full-Text Search (FTS5) across registered dictionary databases
            result = self.db_manager.search_definitions(query, extra_paths)
            logger.info(f"FTS5 search completed for '{query}'")
            return result
        except Exception as e:
            logger.error(f"FTS5 search failed for '{query}': {e}")
            raise

    def save_personal_note(self, word: str, definition: str) -> None:
        """
        Save or update a personal note for a word in the main database.
        """
        logger.info(f"Saving personal note for: '{word}'")
        self.db_manager.save_personal_note(word, definition)
        logger.info(f"Personal note saved for '{word}'")

    def get_personal_note(self, word: str) -> str | None:
        """
        Retrieve a personal note for a word.

        Returns:
            The note content or None if not found.
        """
        note = self.db_manager.get_personal_note(word)
        return str(note) if note else None

    def lookup_structured(self, word: str, lemma: str, extra_paths: list[str] | None = None) -> dict:
        """
        Lookup word and return structured entry data for card display.

        Returns:
            dict with keys: headword, entries (list of dicts with source, content, card_type, priority)
        """
        logger.info(f"Structured lookup for word: '{word}', lemma: '{lemma}'")
        try:
            result = self.db_manager.lookup_structured(word, lemma, extra_paths)
            logger.info(f"Structured lookup successful for '{word}'")
            return result
        except Exception as e:
            logger.error(f"Structured lookup failed for '{word}': {e}")
            raise

