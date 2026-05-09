from unittest.mock import MagicMock
from ui.main_window import YomikataMainWindow

def test_mainwindow_initialization(qtbot):
    # Mock the controller as it's required for initialization
    mock_ai_controller = MagicMock()
    mock_ai_controller.get_template_names.return_value = ["Standard", "Grammar"]

    # Initialize the window
    window = YomikataMainWindow(mock_ai_controller)
    window.show()
    qtbot.addWidget(window)

    # Verify basic attributes
    assert window.windowTitle() == "Yomikata Japanese Assistant"
    assert window.isVisible()

    # Check key UI elements exist
    assert window.input_area is not None
    assert window.matrix_layout is not None
    assert window.card_stack is not None
