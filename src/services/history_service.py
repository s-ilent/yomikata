import logging

from core.database import DatabaseManager

logger = logging.getLogger("yomikata.history_service")

class HistoryService:
    def __init__(self, db_manager: DatabaseManager) -> None:
        """
        Initializes the service with a database manager instance.

        Args:
            db_manager: The central engine for SQLite interactions.
        """
        self.db_manager = db_manager

    def save_history(self, text: str, max_entries: int = 50) -> None:
        """
        Save text to history, maintaining the specified limit.

        Args:
            text: The text snippet to save.
            max_entries: Maximum number of history entries to keep.
        """
        if not text:
            return

        logger.debug(f"Saving text to history: {text[:50]}...")
        # Delegate history management to DatabaseManager
        self.db_manager.save_history(text, max_entries)
        logger.debug("History saved successfully")

    def get_history(self, limit: int = 50) -> list[dict[str, str]]:
        """
        Retrieve the most recent history entries.

        Args:
            limit: Maximum number of entries to retrieve.

        Returns:
            A list of dictionaries, each with 'text' and 'timestamp' keys.
        """
        logger.debug(f"Retrieving history with limit: {limit}")
        rows = self.db_manager.get_history(limit)
        # Format database tuples into dictionaries for the UI layer
        return [{"text": row[0], "timestamp": row[1]} for row in rows]
