
# plugins/theme_toggle.py
# V0.5.0: Theme toggle plugin for light/dark mode switching

from PySide6.QtWidgets import QWidget, QPushButton
from PySide6.QtCore import Qt
from core.api import Plugin
from core.theme import ThemeManager
from core.config_manager import load_config, save_config

class ThemeTogglePlugin(Plugin):
    """
    Adds a theme toggle button to the status bar.
    Allows switching between light and dark mode.
    """
    def __init__(self, app_context):
        self.app_context = app_context
        self.name = "Theme Toggle"
        self.status_btn = None

    def get_widget(self) -> QWidget:
        # No dock widget, just status bar button
        return None

    def on_load(self):
        print("Theme Toggle: Loaded.")
        
        # Load saved theme preference
        try:
            cfg = load_config()
            saved_theme = cfg.get("theme", "dark")
            ThemeManager.set_theme(saved_theme)
        except Exception as e:
            print(f"Theme Toggle: Failed to load theme preference: {e}")
        
        # Create toggle button
        current = ThemeManager.get_current_theme()
        icon = "☀️" if current == "dark" else "🌙"
        self.status_btn = QPushButton(f"{icon} 主题")
        self.status_btn.setFlat(True)
        self.status_btn.setToolTip("切换亮色/暗色主题")
        self.status_btn.clicked.connect(self._toggle_theme)
        
        # Add button to status bar (before Plugins button)
        sb = self.app_context.main_window.statusBar()
        sb.addPermanentWidget(self.status_btn)
        
        self._update_button_style()

    def on_unload(self):
        if self.status_btn:
            self.app_context.main_window.statusBar().removeWidget(self.status_btn)
            self.status_btn.deleteLater()

    def _toggle_theme(self):
        """Toggle theme and update button."""
        new_theme = ThemeManager.toggle_theme()
        
        # Update button icon
        icon = "☀️" if new_theme == "dark" else "🌙"
        self.status_btn.setText(f"{icon} 主题")
        
        # Save preference
        try:
            cfg = load_config()
            cfg["theme"] = new_theme
            save_config(cfg)
        except Exception as e:
            print(f"Theme Toggle: Failed to save preference: {e}")
        
        self._update_button_style()
        print(f"Theme Toggle: Switched to {new_theme} mode.")

    def _update_button_style(self):
        """Update button style based on current theme."""
        current = ThemeManager.get_current_theme()
        if current == "dark":
            self.status_btn.setStyleSheet("color: #888; padding: 0 10px;")
        else:
            self.status_btn.setStyleSheet("color: #666; padding: 0 10px;")

def create_plugin(app_context):
    return ThemeTogglePlugin(app_context)
