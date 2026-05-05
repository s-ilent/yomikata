from database import DatabaseManager


class HistoryService:
    def __init__(self, db_manager: DatabaseManager) -> None:
        self.db_manager = db_manager

    def save_history(self, text: str, max_entries: int = 50) -> None:
        """
        Save text to history, maintaining the specified limit.
        """
        if not text:
            return
        self.db_manager.save_history(text, max_entries)

    def get_history(self, limit: int = 50) -> list[dict[str, str]]:
        """
        Retrieve the most recent history entries.
        """
        rows = self.db_manager.get_history(limit)
        return [{"text": row[0], "timestamp": row[1]} for row in rows]
