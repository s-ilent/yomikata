import fugashi
import pykakasi


class TextProcessor:
    def __init__(self):
        self.tagger = fugashi.Tagger()
        self.kakasi = pykakasi.kakasi()

    def tokenize(self, text):
        results = []
        tokens = self.tagger(text)

        for token in tokens:
            surface = token.surface
            # Get lemma (base form) for dictionary lookups
            lemma = token.feature.lemma if token.feature.lemma else surface

            # Use pykakasi for kana/romaji
            converted = self.kakasi.convert(surface)
            kana = "".join([item["hira"] for item in converted])
            romaji = "".join([item["hepburn"] for item in converted])

            results.append(
                {
                    "surface": surface,
                    "kana": kana,
                    "romaji": romaji,
                    "lemma": lemma,
                    "pos": token.feature.pos1,  # Part of speech
                }
            )
        return results

    def lookup_eijiro(self, word, db_path="yomikata.db"):
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        # Search for the word or its base form
        cursor.execute("SELECT definition FROM dictionary WHERE headword = ?", (word,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else "No definition found."
