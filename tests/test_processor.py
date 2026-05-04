import pytest
from processor import TextProcessor

def test_processor_tokenization():
    """Verify basic morphological analysis functionality."""
    processor = TextProcessor()
    # Mocking or using actual fugashi if available
    tokens = processor.tokenize("食べる")
    assert isinstance(tokens, list)
    assert len(tokens) > 0

def test_empty_string():
    processor = TextProcessor()
    tokens = processor.tokenize("")
    assert tokens == []
