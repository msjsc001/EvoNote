
import platform
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont, QPalette, QColor
from PySide6.QtCore import Qt

class ThemeManager:
    """
    V0.5.0: Manages application themes with light/dark mode support.
    """
    _current_theme = "dark"  # Default theme
    _app = None
    
    @classmethod
    def get_current_theme(cls) -> str:
        """Returns current theme name: 'dark' or 'light'"""
        return cls._current_theme
    
    @classmethod
    def set_theme(cls, theme: str):
        """Set and apply theme. theme should be 'dark' or 'light'."""
        cls._current_theme = theme
        if cls._app:
            if theme == "light":
                cls._apply_light_theme(cls._app)
            else:
                cls._apply_dark_theme(cls._app)
    
    @classmethod
    def toggle_theme(cls):
        """Toggle between light and dark themes."""
        new_theme = "light" if cls._current_theme == "dark" else "dark"
        cls.set_theme(new_theme)
        return new_theme
    
    @staticmethod
    def apply_theme(app: QApplication, theme: str = "dark"):
        """
        Applies specified theme to the application.
        """
        ThemeManager._app = app
        ThemeManager._current_theme = theme
        if theme == "light":
            ThemeManager._apply_light_theme(app)
        else:
            ThemeManager._apply_dark_theme(app)
    
    @staticmethod
    def _get_font_settings():
        """Get platform-specific font settings."""
        system = platform.system()
        base_font_size = 10
        if system == "Darwin":  # macOS
            font_family = "SF Pro Text, Helvetica Neue, Helvetica, Arial, sans-serif"
            base_font_size = 13
        elif system == "Windows":
            font_family = "Segoe UI, Microsoft YaHei UI, sans-serif"
            base_font_size = 10
        else:  # Linux
            font_family = "Roboto, Oxygen, Ubuntu, Cantarell, Fira Sans, Droid Sans, sans-serif"
            base_font_size = 10
        return font_family, base_font_size
    
    @staticmethod
    def _apply_dark_theme(app: QApplication):
        """Apply dark theme styling."""
        font_family, base_font_size = ThemeManager._get_font_settings()
        
        font = QFont(font_family)
        font.setPointSize(base_font_size)
        app.setFont(font)
        
        # Dark Palette
        dark_palette = QPalette()
        color_bg = QColor("#1E1E1E")
        color_surface = QColor("#2D2D2D")
        color_text = QColor("#E0E0E0")
        color_text_dim = QColor("#A0A0A0")
        color_accent = QColor("#7C4DFF")
        color_border = QColor("#404040")
        
        dark_palette.setColor(QPalette.Window, color_bg)
        dark_palette.setColor(QPalette.WindowText, color_text)
        dark_palette.setColor(QPalette.Base, color_surface)
        dark_palette.setColor(QPalette.AlternateBase, color_bg)
        dark_palette.setColor(QPalette.ToolTipBase, color_surface)
        dark_palette.setColor(QPalette.ToolTipText, color_text)
        dark_palette.setColor(QPalette.Text, color_text)
        dark_palette.setColor(QPalette.Button, QColor("#3C3C3C"))
        dark_palette.setColor(QPalette.ButtonText, QColor("#FFFFFF"))  # Fixed: White text for buttons
        dark_palette.setColor(QPalette.BrightText, Qt.red)
        dark_palette.setColor(QPalette.Link, color_accent)
        dark_palette.setColor(QPalette.Highlight, color_accent)
        dark_palette.setColor(QPalette.HighlightedText, Qt.white)
        
        app.setPalette(dark_palette)
        
        # Dark QSS
        qss = f"""
        QMainWindow {{
            background-color: #1E1E1E;
        }}
        QDockWidget {{
            border: 1px solid #404040;
        }}
        QDockWidget::title {{
            background: #2D2D2D;
            text-align: left;
            padding-left: 8px;
            padding-top: 4px;
            padding-bottom: 4px;
            color: #E0E0E0;
        }}
        
        /* Buttons - Fixed visibility */
        QPushButton {{
            background-color: #3C3C3C;
            color: #FFFFFF;
            border: 1px solid #505050;
            border-radius: 4px;
            padding: 6px 12px;
            min-height: 20px;
        }}
        QPushButton:hover {{
            background-color: #4A4A4A;
            border-color: #7C4DFF;
        }}
        QPushButton:pressed {{
            background-color: #5A5A5A;
        }}
        
        /* Editor Area */
        QPlainTextEdit, QTextEdit {{
            background-color: #2D2D2D;
            color: #E0E0E0;
            border: none;
            padding: 10px;
            selection-background-color: #4A3880;
            font-family: "{font_family}";
            font-size: {base_font_size + 2}pt;
        }}
        
        /* Tree/List Views */
        QTreeView, QListView {{
            background-color: #2D2D2D;
            color: #E0E0E0;
            border: none;
        }}
        QTreeView::item:selected, QListView::item:selected {{
            background-color: #7C4DFF;
            color: white;
        }}
        
        /* Scrollbars */
        QScrollBar:vertical {{
            border: none;
            background: #1E1E1E;
            width: 8px;
            margin: 0px;
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
        
        /* Status Bar */
        QStatusBar {{
            background: #1E1E1E;
            color: #A0A0A0;
            border-top: 1px solid #303030;
        }}
        
        /* Tab Bar */
        QTabBar::tab {{
            background: #2D2D2D;
            color: #A0A0A0;
            padding: 8px 16px;
            border: none;
        }}
        QTabBar::tab:selected {{
            background: #3C3C3C;
            color: #FFFFFF;
        }}
        
        /* Line Edit */
        QLineEdit {{
            background-color: #2D2D2D;
            color: #E0E0E0;
            border: 1px solid #404040;
            border-radius: 4px;
            padding: 4px 8px;
        }}
        QLineEdit:focus {{
            border-color: #7C4DFF;
        }}
        """
        app.setStyleSheet(qss)
    
    @staticmethod
    def _apply_light_theme(app: QApplication):
        """Apply light theme styling."""
        font_family, base_font_size = ThemeManager._get_font_settings()
        
        font = QFont(font_family)
        font.setPointSize(base_font_size)
        app.setFont(font)
        
        # Light Palette
        light_palette = QPalette()
        color_bg = QColor("#F5F5F5")
        color_surface = QColor("#FFFFFF")
        color_text = QColor("#1A1A1A")
        color_text_dim = QColor("#666666")
        color_accent = QColor("#6200EE")
        color_border = QColor("#E0E0E0")
        
        light_palette.setColor(QPalette.Window, color_bg)
        light_palette.setColor(QPalette.WindowText, color_text)
        light_palette.setColor(QPalette.Base, color_surface)
        light_palette.setColor(QPalette.AlternateBase, color_bg)
        light_palette.setColor(QPalette.ToolTipBase, color_surface)
        light_palette.setColor(QPalette.ToolTipText, color_text)
        light_palette.setColor(QPalette.Text, color_text)
        light_palette.setColor(QPalette.Button, QColor("#E8E8E8"))
        light_palette.setColor(QPalette.ButtonText, QColor("#1A1A1A"))
        light_palette.setColor(QPalette.BrightText, Qt.red)
        light_palette.setColor(QPalette.Link, color_accent)
        light_palette.setColor(QPalette.Highlight, color_accent)
        light_palette.setColor(QPalette.HighlightedText, Qt.white)
        
        app.setPalette(light_palette)
        
        # Light QSS
        qss = f"""
        QMainWindow {{
            background-color: #F5F5F5;
        }}
        QDockWidget {{
            border: 1px solid #E0E0E0;
        }}
        QDockWidget::title {{
            background: #FFFFFF;
            text-align: left;
            padding-left: 8px;
            padding-top: 4px;
            padding-bottom: 4px;
            color: #1A1A1A;
        }}
        
        /* Buttons */
        QPushButton {{
            background-color: #E8E8E8;
            color: #1A1A1A;
            border: 1px solid #CCCCCC;
            border-radius: 4px;
            padding: 6px 12px;
            min-height: 20px;
        }}
        QPushButton:hover {{
            background-color: #D0D0D0;
            border-color: #6200EE;
        }}
        QPushButton:pressed {{
            background-color: #C0C0C0;
        }}
        
        /* Editor Area */
        QPlainTextEdit, QTextEdit {{
            background-color: #FFFFFF;
            color: #1A1A1A;
            border: none;
            padding: 10px;
            selection-background-color: #B794F6;
            font-family: "{font_family}";
            font-size: {base_font_size + 2}pt;
        }}
        
        /* Tree/List Views */
        QTreeView, QListView {{
            background-color: #FFFFFF;
            color: #1A1A1A;
            border: none;
        }}
        QTreeView::item:selected, QListView::item:selected {{
            background-color: #6200EE;
            color: white;
        }}
        
        /* Scrollbars */
        QScrollBar:vertical {{
            border: none;
            background: #F5F5F5;
            width: 8px;
            margin: 0px;
        }}
        QScrollBar::handle:vertical {{
            background: #CCCCCC;
            min-height: 20px;
            border-radius: 4px;
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            border: none;
            background: none;
        }}
        
        /* Status Bar */
        QStatusBar {{
            background: #FFFFFF;
            color: #666666;
            border-top: 1px solid #E0E0E0;
        }}
        
        /* Tab Bar */
        QTabBar::tab {{
            background: #F5F5F5;
            color: #666666;
            padding: 8px 16px;
            border: none;
        }}
        QTabBar::tab:selected {{
            background: #FFFFFF;
            color: #1A1A1A;
        }}
        
        /* Line Edit */
        QLineEdit {{
            background-color: #FFFFFF;
            color: #1A1A1A;
            border: 1px solid #E0E0E0;
            border-radius: 4px;
            padding: 4px 8px;
        }}
        QLineEdit:focus {{
            border-color: #6200EE;
        }}
        """
        app.setStyleSheet(qss)
    
    @staticmethod
    def get_rich_text_colors():
        """
        Returns a dictionary of colors for the Live Preview highlighter.
        Adapts to current theme.
        """
        if ThemeManager._current_theme == "light":
            return {
                "h1": "#C2185B",  # Pink
                "h2": "#7B1FA2",  # Purple
                "h3": "#0097A7",  # Cyan
                "h4": "#388E3C",  # Green
                "link": "#0097A7",
                "code": "#E65100",  # Orange
                "quote": "#5C6BC0",  # Blue
                "dim": "#9E9E9E"   # Grey
            }
        else:
            return {
                "h1": "#FF79C6",  # Pink
                "h2": "#BD93F9",  # Purple
                "h3": "#8BE9FD",  # Cyan
                "h4": "#50FA7B",  # Green
                "link": "#8BE9FD",
                "code": "#F1FA8C",  # Yellow
                "quote": "#6272A4",  # Blue Grey
                "dim": "#6272A4"   # Comments/Metadata
            }
