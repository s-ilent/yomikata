DARK_STYLE = """
    QMainWindow, QWidget { background-color: #121212; color: #e0e0e0; font-family: 'Meiryo', 'Segoe UI'; }
    QTextEdit {
        background-color: #1e1e1e;
        border: 1px solid #333;
        color: #e0e0e0;
        border-radius: 6px;
        padding: 10px;
        font-size: 14px;
    }
    QScrollArea { border: none; background-color: transparent; }
    QPushButton#AnalyzeBtn {
        background-color: #3d5afe;
        color: white;
        border-radius: 6px;
        padding: 12px;
        font-weight: bold;
        font-size: 14px;
    }
    QPushButton#AnalyzeBtn:hover { background-color: #536dfe; }

    QFrame#TokenCard {
        border: 1px solid #2a2a2a;
        border-radius: 6px;
        background-color: #1e1e1e;
    }
    QFrame#TokenCard:hover { border: 1px solid #3d5afe; background-color: #252525; }
    QLabel#Romaji { color: #777; font-size: 10px; }
    QLabel#Kana { color: #3d5afe; font-size: 12px; font-weight: bold; }
    QLabel#Surface { font-size: 20px; font-weight: 500; margin-top: 2px; }
"""
