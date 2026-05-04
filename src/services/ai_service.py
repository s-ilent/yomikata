from typing import Optional, Dict
from ai_worker import AIWorker

class AIService:
    def __init__(self):
        self._current_worker = None

    def run_analysis(self, prompt: str, on_finished, on_error):
        """
        Instantiate and start an AIWorker for text analysis.
        """
        # Cancel current worker if running? 
        # For now, let's just start a new one.
        self._current_worker = AIWorker(prompt)
        self._current_worker.finished.connect(on_finished)
        self._current_worker.error.connect(on_error)
        self._current_worker.start()

    def build_prompt(self, template: str, data: Dict[str, str]) -> str:
        """
        Format an AI prompt using a template and data.
        """
        return template.format(**data)
