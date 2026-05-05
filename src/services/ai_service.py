import logging
from collections.abc import Callable

from ai_worker import AIWorker

logger = logging.getLogger("yomikata.ai_service")

class AIService:
    def __init__(self) -> None:
        """Initializes the AI service with no active workers."""
        self._current_worker: AIWorker | None = None

    def run_analysis(
        self,
        prompt: str,
        on_finished: Callable[[str], None],
        on_error: Callable[[str], None],
    ) -> None:
        """
        Instantiate and start an AIWorker for text analysis in a background thread.

        Args:
            prompt: The full prompt string for the AI.
            on_finished: Callback function when analysis completes.
            on_error: Callback function when an error occurs.
        """
        logger.info("Starting AI analysis worker...")

        # Instantiate worker; the worker runs in its own QThread.
        self._current_worker = AIWorker(prompt)

        # Connect worker signals to the UI-provided callbacks
        self._current_worker.finished.connect(on_finished)
        self._current_worker.error.connect(on_error)

        # Start the background analysis thread
        self._current_worker.start()
        logger.info("AI analysis worker started")

    def build_prompt(self, template: str, data: dict[str, str]) -> str:
        """
        Format an AI prompt using a template and data.

        Args:
            template: The prompt template string containing placeholders.
            data: Mapping of placeholder names to values.

        Returns:
            The fully formatted prompt string.
        """
        logger.debug("Building AI prompt from template")
        return template.format(**data)
