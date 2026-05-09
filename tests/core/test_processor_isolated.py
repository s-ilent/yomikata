import pytest
from core.processor import TextProcessor

@pytest.fixture
def processor():
    return TextProcessor()

def test_tokenize_basic(processor):
    text = "こんにちは"
    tokens = processor.tokenize(text)
    # Depending on dictionary, "こんにちは" might be one token or more.
    # In the previous run it was one token but romaji was 'konnichiha'
    assert tokens[0]["surface"] == "こんにちは"
    assert tokens[0]["kana"] == "こんにちは"
    assert tokens[0]["romaji"] == "konnichiha" # Standard kakasi output for は as particle/end of greeting

def test_tokenize_kanji(processor):
    text = "日本語"
    tokens = processor.tokenize(text)
    # Unidict-lite splits 日本語 into 日本 and 語
    assert len(tokens) == 2
    assert tokens[0]["surface"] == "日本"
    assert tokens[1]["surface"] == "語"

def test_tokenize_sentence(processor):
    text = "猫が好きです。"
    tokens = processor.tokenize(text)
    # 猫 / が / 好き / です / 。
    assert tokens[0]["surface"] == "猫"
    assert tokens[1]["surface"] == "が"
    assert tokens[2]["surface"] == "好き"
    assert tokens[3]["surface"] == "です"
    assert tokens[4]["surface"] == "。"

def test_tokenize_sokuon(processor):
    # Testing small tsu doubling logic
    text = "行って" # ik/te -> it/te
    tokens = processor.tokenize(text)
    # 行っ / て
    assert len(tokens) == 2
    assert tokens[0]["surface"] == "行っ"
    assert tokens[1]["surface"] == "て"
    # Small tsu logic in processor.py:
    # results[i]["romaji"] = current["romaji"][:-3] + first_char_of_next
    # If "行っ" is "itsu" (from kakasi), it becomes "it" because next is "te"
    assert tokens[0]["romaji"] == "it"
