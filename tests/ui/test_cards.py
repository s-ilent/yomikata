from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QLabel, QVBoxLayout

from ui.widgets.cards import JMDictCard, MarkdownCard, WordHeaderCard


def test_dictionary_card_stack_rendering(qtbot):
    """Test that dictionary cards can be added and rendered in the stack."""
    stack = QFrame()
    layout = QVBoxLayout(stack)
    qtbot.addWidget(stack)
    stack.show()

    # Add a header card
    header = WordHeaderCard("猫", "ねこ", "neko", "猫", "noun")
    layout.insertWidget(0, header)

    # Add a JMDict card
    card = JMDictCard("JMDict", "A small domesticated carnivorous mammal.")
    layout.insertWidget(1, card)

    # Verify widgets were added
    assert stack.findChild(WordHeaderCard) is not None
    assert stack.findChild(JMDictCard) is not None
    assert stack.isVisible()

def test_card_content_rendering(qtbot):
    """Test that cards render content correctly."""
    # Test JMDictCard
    card = JMDictCard("JMDict", "Test definition content")
    qtbot.addWidget(card)
    card.show()

    # Labels in BaseDictionaryCard are added as children
    all_labels = card.findChildren(QLabel)
    content_labels = [lb for lb in all_labels if lb.objectName() != "SourceLabel"]

    assert len(content_labels) > 0
    assert content_labels[0].text() == "Test definition content"


def test_markdown_card_rendering(qtbot):
    """Test that MarkdownCard sets MarkdownText format."""
    card = MarkdownCard("Personal Note", "**bold** and *italic*")
    qtbot.addWidget(card)
    card.show()

    # Content labels should have MarkdownText format
    content_labels = [lb for lb in card.findChildren(QLabel) if lb.objectName() != "SourceLabel"]
    assert len(content_labels) > 0
    assert content_labels[0].textFormat() == Qt.TextFormat.MarkdownText


def test_card_factory_personal_note(qtbot):
    """Test CardFactory creates MarkdownCard for personal notes."""
    from ui.card_factory import CardFactory

    entry = {"source": "Personal Note", "content": "## Test", "card_type": "markdown"}
    card = CardFactory.create(entry)
    qtbot.addWidget(card)
    card.show()

    assert isinstance(card, MarkdownCard)
