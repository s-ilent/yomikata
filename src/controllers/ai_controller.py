from services.ai_service import AIService

AI_TEMPLATES = {
    "Grammar Breakdown": (
        "You are a Japanese linguistic expert. Analyze this specific phrase: '{text}'\n"
        "Context: {context}\n"
        "Grammar Components:\n{components}\n\n"
        "Please explain:\n"
        "1. The meaning of the combined phrase.\n"
        "2. How the individual tokens conjugate or connect (e.g., stem + auxiliary).\n"
        "3. Any specific nuance in this context.\n"
        "Use Markdown for formatting."
    ),
    "Example Sentences": (
        "You are a Japanese language expert. Provide example sentences using: '{text}'\n"
        "Context from user's text: {context}\n\n"
        "Please provide:\n"
        "1. 3-5 example sentences using this word/phrase in different contexts.\n"
        "2. For each sentence, provide: Japanese, romaji reading, and English translation.\n"
        "3. Briefly explain the grammar pattern used in each example.\n"
        "Use Markdown for formatting."
    ),
    "Etymology": (
        "You are a Japanese language historian. Analyze the etymology of: '{text}'\n"
        "Part of speech: {pos}\n\n"
        "Please explain:\n"
        "1. The kanji composition (if any) and their individual meanings.\n"
        "2. Historical origin and how the word evolved.\n"
        "3. Any interesting linguistic notes about this word.\n"
        "4. Related words or compounds that share the same kanji/roots.\n"
        "Use Markdown for formatting."
    ),
    "Conjugation": (
        "You are a Japanese grammar expert. Provide a complete conjugation table for: '{text}'\n"
        "Part of speech: {pos}\n\n"
        "Please provide:\n"
        "1. All basic conjugations: dictionary, past, negative, polite (ます), te-form, potential, passive, causative, conditional.\n"
        "2. For verbs: include masu-stem, te-stem, ra-stem variations.\n"
        "3. Explain any irregular conjugations.\n"
        "Use Markdown tables for the conjugation chart."
    ),
    "Compare/Contrast": (
        "You are a Japanese language expert. Compare and contrast: '{text}'\n"
        "Context: {context}\n"
        "Part of speech: {pos}\n\n"
        "Please explain:\n"
        "1. What this word/phrase means and its key characteristics.\n"
        "2. Common synonyms and how they differ in usage.\n"
        "3. Words that are often confused with this one and why.\n"
        "4. Tips for distinguishing between them.\n"
        "Use Markdown for formatting."
    ),
}

class AIController:
    def __init__(self, ai_service: AIService):
        self.ai_service = ai_service

    def get_template_names(self):
        return list(AI_TEMPLATES.keys())

    def run_analysis(self, template_name, prompt_data, success_callback, error_callback):
        template = AI_TEMPLATES.get(template_name, AI_TEMPLATES["Grammar Breakdown"])
        prompt = self.ai_service.build_prompt(template, prompt_data)
        self.ai_service.run_analysis(prompt, success_callback, error_callback)
