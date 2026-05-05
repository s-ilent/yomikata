import logging
from collections.abc import Callable
from ai_worker import AIWorker

logger = logging.getLogger("yomikata.ai_service")

class AIService:
    def __init__(self) -> None:
        self._current_worker: AIWorker | None = None

    def run_analysis(
        self,
        prompt: str,
        on_finished: Callable[[str], None],
        on_error: Callable[[str], None],
    ) -> None:
        """
        Instantiate and start an AIWorker for text analysis.
        """
        logger.info("Starting AI analysis worker...")
        # Cancel current worker if running?
        # For now, let's just start a new one.
        self._current_worker = AIWorker(prompt)
        self._current_worker.finished.connect(on_finished)
        self._current_worker.error.connect(on_error)
        self._current_worker.start()
        logger.info("AI analysis worker started")

    def build_prompt(self, template: str, data: dict[str, str]) -> str:
        """
        Format an AI prompt using a template and data.
        """
        logger.debug("Building AI prompt from template")
        return template.format(**data)
