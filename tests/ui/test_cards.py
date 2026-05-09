from PyQt6.QtWidgets import QLabel, QVBoxLayout
from ui.widgets.cards import DictionaryCardStack, JMDictCard, WordHeaderCard

def test_dictionary_card_stack_rendering(qtbot):
    """Test that dictionary cards can be added and rendered in the stack."""
    stack = DictionaryCardStack()
    qtbot.addWidget(stack)
    stack.show()

    # Add a header card
    header = WordHeaderCard("猫", "ねこ", "neko", "猫", "noun")
    stack.layout().insertWidget(0, header)
    
    # Add a JMDict card
    card = JMDictCard("JMDict", "A small domesticated carnivorous mammal.")
    stack.layout().insertWidget(1, card)

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
    content_labels = [l for l in all_labels if l.objectName() != "SourceLabel"]
    
    assert len(content_labels) > 0
    assert content_labels[0].text() == "Test definition content"
