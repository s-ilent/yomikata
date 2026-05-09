from ui.style import CATPPUCCIN_MOCHA as CAT
from ui.widgets.cards import (
    JMDictCard,
    JMnedictCard,
    LegacyCard,
    MarkdownCard,
    YomitanCard,
)


class CardFactory:
    @staticmethod
    def create(entry: dict):
        """Create and return the appropriate card type for an entry."""
        source = entry.get("source", "Dictionary")
        content = entry.get("content", "")
        card_type = entry.get("card_type", "yomitan")
        priority = entry.get("priority", 0)

        if card_type == "jmdict":
            return JMDictCard(source, content)
        elif card_type == "jmnedict":
            return JMnedictCard(source, content)
        elif card_type == "legacy":
            return LegacyCard(source, content)
        elif card_type == "markdown":
            return MarkdownCard(source, content)
        else:
            return YomitanCard(source, content, priority)

    @staticmethod
    def get_styled_html(html):
        return f"""
        <style>
            body {{ font-family: 'Shippori Mincho', 'Noto Serif JP', serif; color: {CAT["foreground"]}; line-height: 1.6; }}
            h1 {{ color: {CAT["blue"]}; font-size: 24px; margin: 0 0 8px 0; font-weight: 600; letter-spacing: 0.05em; }}
            h2 {{ color: {CAT["mauve"]}; font-size: 16px; margin: 16px 0 4px 0; border-bottom: 1px solid {CAT["surface_hover"]}; padding-bottom: 4px; }}
            h3 {{ color: {CAT["cyan"]}; font-size: 14px; margin: 12px 0 4px 0; font-weight: 500; }}
            code {{ background-color: {CAT["surface"]}; color: {CAT["mauve"]}; padding: 2px 6px; border-radius: 3px; font-size: 0.95em; }}
            strong {{ color: {CAT["foreground"]}; font-weight: 600; }}
            hr {{ border: 0; border-top: 1px solid {CAT["surface_hover"]}; margin: 12px 0; }}
            a {{ color: {CAT["blue"]}; }}
            p {{ margin: 6px 0; }}
            ul, ol {{ margin: 4px 0; padding-left: 20px; }}
            li {{ margin: 2px 0; }}
            blockquote {{
                border-left: 3px solid {CAT["mauve"]};
                margin: 8px 0;
                padding-left: 12px;
                color: {CAT["comment"]};
            }}
            .pos-badge {{
                display: inline-block;
                background: {CAT["surface"]};
                color: {CAT["cyan"]};
                padding: 2px 8px;
                border-radius: 10px;
                font-size: 11px;
                font-family: sans-serif;
                margin-right: 6px;
            }}
            .dict-entry {{
                background: {CAT["surface"]};
                border-radius: 8px;
                padding: 12px 16px;
                margin: 8px 0;
            }}
            .dict-header {{
                display: flex;
                align-items: center;
                margin-bottom: 8px;
            }}
            .dict-source {{
                font-size: 11px;
                color: {CAT["comment"]};
                margin-left: auto;
            }}
        </style>
        {html}
        """
