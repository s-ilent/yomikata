import pytest
from services.dictionary_service import DictionaryService

def test_dictionary_service_lookup(db_manager, mock_config):
    """Verify dictionary lookup coordination."""
    service = DictionaryService(db_manager)
    # The dictionary might return data if it finds something
    result = service.lookup("食", "食", [])
    assert isinstance(result, str)

def test_dictionary_service_search(db_manager, mock_config):
    """Verify FTS search returns empty results when no data present."""
    service = DictionaryService(db_manager)
    assert service.search_definitions("test", []) == ""
