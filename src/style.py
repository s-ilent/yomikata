DARK_STYLE = """
    QMainWindow, QWidget {
        background-color: #121212;
        color: #e0e0e0;
        font-family: 'Shippori Mincho', 'Meiryo', 'Segoe UI';
    }

    /* Panel backgrounds with subtle top-to-bottom gradient */
    QWidget#leftPanel {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 #1a1a1a,
            stop:1 #121212);
    }
    QWidget#rightPanel {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 #1a1a1a,
            stop:1 #121212);
    }

    QTextEdit {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 #252525,
            stop:1 #1e1e1e);
        border: 1px solid #333;
        color: #e0e0e0;
        border-radius: 6px;
        padding: 8px;
        font-size: 14px;
    }
    QScrollArea { border: none; background-color: transparent; }

    /* PRIMARY BUTTON - Dark blue fading to transparent, pale outline */
    QPushButton#AnalyzeBtn, QPushButton.primary-btn {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 rgba(26,35,126,1),
            stop:1 rgba(26,35,126,0));
        color: white;
        border-radius: 6px;
        border: 1px solid rgba(255,255,255,0.25);
        padding: 10px 16px;
        font-weight: bold;
        font-size: 14px;
    }
    QPushButton#AnalyzeBtn:hover, QPushButton.primary-btn:hover {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 rgba(57,73,171,1),
            stop:1 rgba(57,73,171,0));
    }

    /* SECONDARY BUTTON */
    QPushButton.secondary-btn {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 rgba(26,35,126,1),
            stop:1 rgba(26,35,126,0));
        color: white;
        border-radius: 6px;
        border: 1px solid rgba(255,255,255,0.25);
        padding: 10px 16px;
        font-size: 14px;
    }
    QPushButton.secondary-btn:hover {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 rgba(57,73,171,1),
            stop:1 rgba(57,73,171,0));
    }

    /* SUCCESS BUTTON */
    QPushButton.success-btn {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 rgba(26,35,126,1),
            stop:1 rgba(26,35,126,0));
        color: white;
        border-radius: 6px;
        border: 1px solid rgba(255,255,255,0.25);
        padding: 10px 16px;
        font-weight: bold;
        font-size: 14px;
    }
    QPushButton.success-btn:hover {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 rgba(57,73,171,1),
            stop:1 rgba(57,73,171,0));
    }

    /* TOKEN CARD */
    QFrame#TokenCard {
        border: none;
        border-radius: 4px;
        background-color: #2a2a2a;
    }
    QFrame#TokenCard:hover {
        background-color: #353535;
    }
    QFrame#TokenCard[selected="true"] {
        background-color: #3d5afe;
    }

    /* TOKEN TEXT */
    QLabel#Romaji { color: #aaa; font-size: 10px; }
    QLabel#Kana { color: #8c9eff; font-size: 12px; font-weight: bold; }
    QLabel#Surface { color: #ffffff; font-size: 20px; font-weight: 500; margin-top: 2px; }

    /* SELECTED STATE TEXT CONTRAST */
    QFrame#TokenCard[selected="true"] QLabel#Romaji { color: #e0e0e0; }
    QFrame#TokenCard[selected="true"] QLabel#Kana { color: #ffffff; }
    QFrame#TokenCard[selected="true"] QLabel#Surface { color: #ffffff; }

    /* SEARCH BOX */
    QLineEdit {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 #252525,
            stop:1 #1e1e1e);
        border: 1px solid #333;
        border-radius: 6px;
        padding: 8px;
        color: #e0e0e0;
        font-size: 14px;
    }
    QLineEdit:hover {
        border: 1px solid #444;
    }
    QLineEdit:focus {
        border: 1px solid #3d5afe;
    }
    QLineEdit::placeholder {
        color: #666;
    }

    /* PROGRESS BAR */
    QProgressBar {
        background: #333;
        border: none;
        border-radius: 2px;
        height: 4px;
    }
    QProgressBar::chunk {
        background: #3d5afe;
    }

    /* SPLITTER HANDLE */
    QSplitter::handle {
        background: #333;
    }
    QSplitter::handle:hover {
        background: #3d5afe;
    }
"""