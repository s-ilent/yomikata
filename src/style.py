CATPPUCCIN_MOCHA = {
    # Core colors (dark to light)
    "background": "#181825",  # Crust (darkest)
    "surface": "#1e1e2e",  # Base
    "surface_hover": "#313244",  # Surface0
    "foreground": "#cdd6f4",  # Text
    "comment": "#6c7086",  # Overlay0
    # Accent colors
    "cyan": "#89dceb",  # Cyan
    "teal": "#94e2d5",  # Teal
    "mauve": "#cba6f7",  # Mauve
    "green": "#a6e3a1",  # Green
    "red": "#f38ba8",  # Red
    "selection": "#74c7ec",  # Sapphire (selected state)
    "blue": "#89b4fa",  # Blue
    "sapphire": "#74c7ec",  # Sapphire
    "sky": "#89dceb",  # Sky
    "peach": "#fab387",  # Peach
}

FONT_CONFIG = {
    "base": 1.0,
    "kanji": 1.43,
    "kana": 0.86,
    "romaji": 0.71,
}


def get_font_size(element: str, base_size: int = 14) -> int:
    """Calculate element font size from base size using FONT_CONFIG ratios."""
    return int(base_size * FONT_CONFIG.get(element, 1.0))


def hex_to_rgb(hex_color: str) -> tuple:
    """Convert hex color to RGB tuple."""
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))


def build_stylesheet(colors: dict = None, font_base: int = 14) -> str:
    """Generate QSS from color palette.

    Args:
        colors: Optional custom palette (defaults to CATPPUCCIN_MOCHA)
        font_base: Base font size for UI elements
    """
    c = colors or CATPPUCCIN_MOCHA

    # Derive gradient colors from base palette
    surface_rgb = hex_to_rgb(c["surface"])
    bg_rgb = hex_to_rgb(c["background"])
    mauve_rgb = hex_to_rgb(c["mauve"])
    sapphire_rgb = hex_to_rgb(c["sapphire"])
    cyan_rgb = hex_to_rgb(c["cyan"])
    green_rgb = hex_to_rgb(c["green"])

    # Gradient colors: (r,g,b) at alpha 1 and alpha 0
    c["surface_gradient"] = (
        f"rgba({surface_rgb[0]},{surface_rgb[1]},{surface_rgb[2]},1)"
    )
    c["surface_gradient_end"] = f"rgba({bg_rgb[0]},{bg_rgb[1]},{bg_rgb[2]},0)"
    # Subtle accent gradients (alpha 0.25 for top, 0 for bottom)
    c["sapphire_gradient"] = (
        f"rgba({sapphire_rgb[0]},{sapphire_rgb[1]},{sapphire_rgb[2]},0.25)"
    )
    c["sapphire_gradient_end"] = (
        f"rgba({sapphire_rgb[0]},{sapphire_rgb[1]},{sapphire_rgb[2]},0)"
    )
    c["cyan_gradient"] = f"rgba({cyan_rgb[0]},{cyan_rgb[1]},{cyan_rgb[2]},0.25)"
    c["cyan_gradient_end"] = f"rgba({cyan_rgb[0]},{cyan_rgb[1]},{cyan_rgb[2]},0)"
    c["green_gradient"] = f"rgba({green_rgb[0]},{green_rgb[1]},{green_rgb[2]},0.25)"
    c["green_gradient_end"] = f"rgba({green_rgb[0]},{green_rgb[1]},{green_rgb[2]},0)"

    kanji_size = get_font_size("kanji", font_base)
    kana_size = get_font_size("kana", font_base)
    romaji_size = get_font_size("romaji", font_base)

    return f"""
    QMainWindow, QWidget {{
        background-color: {c["background"]};
        color: {c["foreground"]};
        font-family: 'Shippori Mincho', 'Meiryo', 'Segoe UI';
    }}

    QWidget#leftPanel {{
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 {c["surface_gradient"]},
            stop:1 {c["surface_gradient_end"]});
    }}
    QWidget#rightPanel {{
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 {c["surface_gradient"]},
            stop:1 {c["surface_gradient_end"]});
    }}

    QTextEdit {{
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 {c["surface_gradient"]},
            stop:1 {c["surface_gradient_end"]});
        border: 1px solid {c["surface_hover"]};
        color: {c["foreground"]};
        border-radius: 6px;
        padding: 8px;
        font-size: {font_base}px;
    }}
    QScrollArea {{ border: none; background-color: transparent; }}

    QPushButton#AnalyzeBtn, QPushButton.primary-btn {{
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 {c["sapphire_gradient"]},
            stop:1 {c["sapphire_gradient_end"]});
        color: {c["foreground"]};
        border-radius: 6px;
        border: 1px solid {c["surface_hover"]};
        padding: 10px 16px;
        font-weight: bold;
        font-size: {font_base}px;
    }}
    QPushButton#AnalyzeBtn:hover, QPushButton.primary-btn:hover {{
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 {c["cyan_gradient"]},
            stop:1 {c["cyan_gradient_end"]});
    }}
    QPushButton#AnalyzeBtn:disabled, QPushButton.primary-btn:disabled {{
        background: {c["surface"]};
        color: {c["comment"]};
        border: 1px solid {c["surface_hover"]};
    }}

    QPushButton.secondary-btn {{
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 {c["sapphire_gradient"]},
            stop:1 {c["sapphire_gradient_end"]});
        color: {c["foreground"]};
        border-radius: 6px;
        border: 1px solid {c["surface_hover"]};
        padding: 10px 16px;
        font-size: {font_base}px;
    }}
    QPushButton.secondary-btn:hover {{
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 {c["cyan_gradient"]},
            stop:1 {c["cyan_gradient_end"]});
    }}
    QPushButton.secondary-btn:disabled {{
        background: {c["surface"]};
        color: {c["comment"]};
        border: 1px solid {c["surface_hover"]};
    }}

    QPushButton.success-btn {{
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 {c["green_gradient"]},
            stop:1 {c["green_gradient_end"]});
        color: {c["background"]};
        border-radius: 6px;
        border: 1px solid {c["surface_hover"]};
        padding: 10px 16px;
        font-weight: bold;
        font-size: {font_base}px;
    }}
    QPushButton.success-btn:hover {{
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 {c["green_gradient"]},
            stop:1 {c["green_gradient_end"]});
        border: 1px solid {c["green"]};
    }}
    QPushButton.success-btn:disabled {{
        background: {c["surface"]};
        color: {c["comment"]};
        border: 1px solid {c["surface_hover"]};
    }}

    QFrame#TokenCard {{
        border: none;
        border-radius: 4px;
        background-color: {c["surface"]};
    }}
    QFrame#TokenCard:hover {{
        background-color: {c["surface_hover"]};
    }}
    QFrame#TokenCard[selected="true"] {{
        background-color: {c["selection"]};
    }}

    QLabel#Romaji {{ color: {c["comment"]}; font-size: {romaji_size}px; }}
    QLabel#Kana {{ color: {c["cyan"]}; font-size: {kana_size}px; font-weight: bold; }}
    QLabel#Surface {{ color: {c["foreground"]}; font-size: {kanji_size}px; font-weight: 500; }}

    QFrame#TokenCard[selected="true"] QLabel#Romaji {{ color: {c["foreground"]}; }}
    QFrame#TokenCard[selected="true"] QLabel#Kana {{ color: {c["background"]}; }}
    QFrame#TokenCard[selected="true"] QLabel#Surface {{ color: {c["background"]}; }}

    QLineEdit {{
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 {c["surface_gradient"]},
            stop:1 {c["surface_gradient_end"]});
        border: 1px solid {c["surface_hover"]};
        border-radius: 6px;
        padding: 8px;
        color: {c["foreground"]};
        font-size: {font_base}px;
    }}
    QLineEdit:hover {{
        border: 1px solid {c["comment"]};
    }}
    QLineEdit:focus {{
        border: 1px solid {c["selection"]};
    }}
    QLineEdit::placeholder {{
        color: {c["comment"]};
    }}

    QProgressBar {{
        background: {c["surface"]};
        border: none;
        border-radius: 2px;
        height: 4px;
    }}
    QProgressBar::chunk {{
        background: {c["selection"]};
    }}

    QSplitter::handle {{
        background: {c["surface"]};
    }}
    QSplitter::handle:hover {{
        background: {c["selection"]};
    }}
"""


# Default stylesheet using Catpuccin Mocha palette
DARK_STYLE = build_stylesheet()
