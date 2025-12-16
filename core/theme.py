
import platform
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont, QPalette, QColor
from PySide6.QtCore import Qt

class ThemeManager:
    @staticmethod
    def apply_theme(app: QApplication):
        """
        Applies a modern, clean theme to the application.
        """
        # 1. Platform-specific Fonts
        system = platform.system()
        base_font_size = 10
        if system == "Darwin": # macOS
            font_family = "SF Pro Text, Helvetica Neue, Helvetica, Arial, sans-serif"
            base_font_size = 13
        elif system == "Windows":
            font_family = "Segoe UI, Microsoft YaHei UI, sans-serif"
            base_font_size = 10 
        else: # Linux
            font_family = "Roboto, Oxygen, Ubuntu, Cantarell, Fira Sans, Droid Sans, sans-serif"
            base_font_size = 10

        font = QFont(font_family)
        font.setPointSize(base_font_size)
        app.setFont(font)

        # 2. Modern Palette (Obsidian-like Dark Mode vibe as base, but clean)
        # For now, let's stick to a clean Light/Neutral theme that looks professional, 
        # or a very safe Dark theme if requested. Given "WOW" factor, a sleek Dark theme is often safer.
        # Let's implement a "Professional Dark" palette.
        
        dark_palette = QPalette()
        # Colors
        color_bg = QColor("#202020")
        color_surface = QColor("#2D2D2D")
        color_text = QColor("#E0E0E0")
        color_text_dim = QColor("#A0A0A0")
        color_accent = QColor("#7C4DFF") # Soft Purple/Blue accent
        color_border = QColor("#404040")

        dark_palette.setColor(QPalette.Window, color_bg)
        dark_palette.setColor(QPalette.WindowText, color_text)
        dark_palette.setColor(QPalette.Base, color_surface)
        dark_palette.setColor(QPalette.AlternateBase, color_bg)
        dark_palette.setColor(QPalette.ToolTipBase, color_surface)
        dark_palette.setColor(QPalette.ToolTipText, color_text)
        dark_palette.setColor(QPalette.Text, color_text)
        dark_palette.setColor(QPalette.Button, color_surface)
        dark_palette.setColor(QPalette.ButtonText, color_text)
        dark_palette.setColor(QPalette.BrightText, Qt.red)
        dark_palette.setColor(QPalette.Link, color_accent)
        dark_palette.setColor(QPalette.Highlight, color_accent)
        dark_palette.setColor(QPalette.HighlightedText, Qt.white)

        app.setPalette(dark_palette)

        # 3. Stylesheet (QSS) for specific controls
        # Round corners, padding, nice scrollbars
        qss = f"""
        QMainWindow {{
            background-color: #202020;
        }}
        QDockWidget {{
            titlebar-close-icon: url(close.png);
            titlebar-normal-icon: url(float.png);
            border: 1px solid #404040;
        }}
        QDockWidget::title {{
            background: #2D2D2D;
            text-align: left; 
            padding-left: 8px;
            padding-top: 4px;
            padding-bottom: 4px;
        }}
        
        /* Editor Area */
        QPlainTextEdit, QTextEdit {{
            background-color: #2D2D2D;
            color: #E0E0E0;
            border: none;
            padding: 10px;
            selection-background-color: #4A3880;
            line-height: 1.5; /* Note: QSS line-height support is limited, handled in block format usually */
            font-family: "{font_family}";
            font-size: {base_font_size + 2}pt; /* Slightly larger for writing */
        }}

        /* Scrollbars - The "Invisible" look */
        QScrollBar:vertical {{
            border: none;
            background: #202020;
            width: 8px;
            margin: 0px 0px 0px 0px;
        }}
        QScrollBar::handle:vertical {{
            background: #505050;
            min-height: 20px;
            border-radius: 4px;
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            border: none;
            background: none;
        }}

        /* Completer Popup */
        QListView {{
            background-color: #303030;
            border: 1px solid #505050;
            color: #E0E0E0;
        }}
        QListView::item:selected {{
            background-color: #7C4DFF;
            color: white;
        }}

        /* Status Bar */
        QStatusBar {{
            background: #202020;
            color: #808080;
            border-top: 1px solid #303030;
        }}
        """
        app.setStyleSheet(qss)
