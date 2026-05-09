from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QLabel, QVBoxLayout

from ui.widgets.cards import MarkdownCard


def test_dictionary_card_stack_rendering(qtbot):
    """Test that dictionary cards can be added and rendered in the stack."""
    from ui.widgets.cards import JMDictCard, WordHeaderCard

    stack = QFrame()
    layout = QVBoxLayout(stack)
    qtbot.addWidget(stack)
    stack.show()

    # Add a header card
    header = WordHeaderCard("猫", "ねこ", "neko", "猫", "noun")
    layout.insertWidget(0, header)

    # Add a JMDict card with structured data
    structured = [
        {
            "kanji": "猫",
            "kana": "ねこ",
            "senses": [
                {"pos": ["noun (common) (futsuumeishi)"], "gloss": ["cat (domestic)"], "misc": []},
            ],
        }
    ]
    card = JMDictCard("JMDict", structured)
    layout.insertWidget(1, card)

    # Verify widgets were added
    assert stack.findChild(WordHeaderCard) is not None
    assert stack.findChild(JMDictCard) is not None
    assert stack.isVisible()


def test_jmdict_card_structured_rendering(qtbot):
    """Test that JMDictCard renders structured sense data correctly."""
    from ui.widgets.cards import JMDictCard

    structured = [
        {
            "kanji": "猫",
            "kana": "ねこ",
            "senses": [
                {"pos": ["noun (common) (futsuumeishi)"], "gloss": ["cat (domestic)"], "misc": []},
            ],
        }
    ]

    card = JMDictCard("JMDict", structured)
    qtbot.addWidget(card)
    card.show()

    all_labels = card.findChildren(QLabel)
    headword_labels = [lb for lb in all_labels if lb.objectName() == "JMDictHeadword"]
    sense_labels = [lb for lb in all_labels if lb.objectName() == "JMDictSense"]

    assert any("猫" in lb.text() for lb in headword_labels)
    assert any("cat" in lb.text() for lb in sense_labels)
    assert any("noun" in lb.text() for lb in sense_labels)


def test_jmdict_card_fallback_string(qtbot):
    """Test JMDictCard still handles plain string content (legacy fallback)."""
    from ui.widgets.cards import JMDictCard

    card = JMDictCard("JMDict", "Fallback text content")
    qtbot.addWidget(card)
    card.show()

    all_labels = card.findChildren(QLabel)
    content_labels = [lb for lb in all_labels if lb.objectName() != "SourceLabel"]
    assert len(content_labels) > 0
    assert content_labels[0].text() == "Fallback text content"


def test_jmdict_card_handles_real_gloss_strings(qtbot):
    """Test JMDictCard works when gloss values are plain strings (regression for SenseGloss)."""
    from ui.widgets.cards import JMDictCard

    # This simulates data that went through lookup_jmdict_structured with str(g) conversion
    structured = [
        {
            "kanji": "取る",
            "kana": "とる",
            "senses": [
                {"pos": ["v5r", "vt"], "gloss": ["take", "pick up"], "misc": []},
                {"pos": ["v5r", "vt"], "gloss": ["adopt", "assume"], "misc": ["figuratively"]},
            ],
        }
    ]

    card = JMDictCard("JMDict", structured)
    qtbot.addWidget(card)
    card.show()

    all_labels = card.findChildren(QLabel)
    sense_labels = [lb for lb in all_labels if lb.objectName() == "JMDictSense"]

    # Verify both senses rendered correctly
    assert any("1." in lb.text() for lb in sense_labels)
    assert any("take" in lb.text() for lb in sense_labels)
    assert any("2." in lb.text() for lb in sense_labels)
    assert any("adopt" in lb.text() for lb in sense_labels)


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
