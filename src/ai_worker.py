import ollama
from PyQt6.QtCore import QThread, pyqtSignal


class OllamaWorker(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, prompt):
        super().__init__()
        self.prompt = prompt

    def run(self):
        try:
            response = ollama.generate(
                model="llama3",  # or your preferred model
                prompt=self.prompt,
            )
            self.finished.emit(response["response"])
        except Exception as e:
            self.error.emit(str(e))
