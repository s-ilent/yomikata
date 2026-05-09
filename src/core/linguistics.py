from fugashi import Tagger


class LinguisticsManager:
    """Handles Japanese inflection and lemma processing."""

    def __init__(self):
        self.tagger = Tagger()

    def get_inflected_forms(self, word: str) -> list[str]:
        """Use fugashi/MeCab to get dictionary forms (lemmas)."""
        if not word:
            return []

        # Parse the word
        tokens = self.tagger(word)

        # Collect lemma forms
        lemmas = set()
        for token in tokens:
            lemma = token.feature.lemma
            # In UniDic, lemma is often the word itself if not found
            if lemma:
                lemmas.add(lemma)
            else:
                lemmas.add(token.surface)

        return list(lemmas)
