import logging
from database import DatabaseManager

logger = logging.getLogger("yomikata.history_service")

class HistoryService:
    def __init__(self, db_manager: DatabaseManager) -> None:
        self.db_manager = db_manager

    def save_history(self, text: str, max_entries: int = 50) -> None:
        """
        Save text to history, maintaining the specified limit.
        """
        if not text:
            return
        logger.debug(f"Saving text to history: {text[:50]}...")
        self.db_manager.save_history(text, max_entries)
        logger.debug("History saved successfully")

    def get_history(self, limit: int = 50) -> list[dict[str, str]]:
        """
        Retrieve the most recent history entries.
        """
        logger.debug(f"Retrieving history with limit: {limit}")
        rows = self.db_manager.get_history(limit)
        return [{"text": row[0], "timestamp": row[1]} for row in rows]
