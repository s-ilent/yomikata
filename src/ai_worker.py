import ollama
from openai import OpenAI
from PyQt6.QtCore import QSettings, QThread, pyqtSignal


class AIWorker(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, prompt):
        super().__init__()
        self.prompt = prompt
        self.settings = QSettings("Yomikata", "Settings")

    def run(self):
        provider = self.settings.value("ai_provider", "Ollama")
        model = self.settings.value("ai_model", "llama3")

        try:
            if provider == "Ollama":
                # Local Ollama library
                response = ollama.generate(model=model, prompt=self.prompt)
                self.finished.emit(response["response"])

            else:
                # Using the OpenAI Library for Remote Providers
                # DeepInfra, OpenAI, etc.
                base_url = self.settings.value(
                    "api_url", "https://api.openai.com/v1"
                ).strip()
                api_key = self.settings.value("api_key", "").strip()

                # Initialize the client
                client = OpenAI(
                    base_url=base_url,
                    api_key=api_key,
                    timeout=60.0,  # Increased timeout to 1 minute
                )

                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a Japanese language expert and tutor.",
                        },
                        {"role": "user", "content": self.prompt},
                    ],
                    temperature=0.3,
                )

                self.finished.emit(response.choices[0].message.content)

        except Exception as e:
            # The openai library provides very descriptive error messages
            self.error.emit(str(e))
