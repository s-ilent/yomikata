from database import DatabaseManager


class HistoryService:
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

    def save_history(self, text: str, max_entries: int = 50):
        """
        Save text to history, maintaining the specified limit.
        """
        if not text:
            return
        self.db_manager.save_history(text, max_entries)

    def get_history(self, limit: int = 50) -> list[dict]:
        """
        Retrieve the most recent history entries.
        """
        return self.db_manager.get_history(limit)
