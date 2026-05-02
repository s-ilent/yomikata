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
            lemma = token.feature.lemma if token.feature.lemma else surface

            # 1. Use the analyzer's reading (Katakana) if available,
            # it's usually more accurate for Kanji than Kakasi alone.
            reading = (
                token.feature.kana
                if hasattr(token.feature, "kana") and token.feature.kana
                else surface
            )

            converted = self.kakasi.convert(reading)
            kana = "".join([item["hira"] for item in converted])
            romaji = "".join([item["hepburn"] for item in converted])

            results.append(
                {
                    "surface": surface,
                    "kana": kana,
                    "romaji": romaji,
                    "lemma": lemma,
                    "pos": token.feature.pos1,
                }
            )

        # 2. Handle the small 'tsu' (っ) phonetic doubling
        for i in range(len(results) - 1):
            current = results[i]
            # If current token ends with a sokuon
            if current["surface"].endswith(("っ", "ッ")):
                next_token = results[i + 1]
                if next_token["romaji"]:
                    first_char_of_next = next_token["romaji"][0]
                    # Replace 'tsu' or 'xtsu' at the end with the doubled consonant
                    # Most converters return 'tsu'. We strip it and add the leading char of next word.
                    if current["romaji"].endswith("tsu"):
                        results[i]["romaji"] = (
                            current["romaji"][:-3] + first_char_of_next
                        )

        return results
