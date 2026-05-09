from src.core.linguistics import LinguisticsManager


def test_get_inflected_forms():
    manager = LinguisticsManager()

    # Test verb inflection
    # 食べた (tabeta) -> 食べる (taberu)
    results = manager.get_inflected_forms("食べた")
    assert "食べる" in results

    # Test simple noun
    results = manager.get_inflected_forms("菓子")
    assert "菓子" in results

    # Test empty input
    assert manager.get_inflected_forms("") == []
