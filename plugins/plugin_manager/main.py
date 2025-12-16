
# plugins/plugin_manager/main.py
from PySide6.QtWidgets import QWidget, QDialog, QVBoxLayout, QPushButton, QLabel
from PySide6.QtCore import Qt
from core.api import Plugin
from .ui import PluginManagerWidget

class PluginManagerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Plugin Manager")
        self.resize(800, 600)
        self.layout = QVBoxLayout(self)
        
        self.widget = PluginManagerWidget()
        self.layout.addWidget(self.widget)
        
        self.widget.refresh_list()

class PluginManagerPlugin(Plugin):
    def __init__(self, app_context):
        self.app_context = app_context
        self.name = "Plugin Manager"
        self._dialog = None

    def get_widget(self) -> QWidget:
        # Return None to avoid creating a DockWidget automatically
        return None

    def on_load(self):
        print("Plugin Manager: Loaded (Background Mode).")
        # Add a button to the status bar to open the manager
        # Or ideally, register a command. 
        # For now, let's use the status bar as a reachable entry point.
        self.status_btn = QPushButton("🧩 Plugins")
        self.status_btn.setFlat(True)
        self.status_btn.setStyleSheet("color: #888; padding: 0 10px;")
        self.status_btn.clicked.connect(self.open_dialog)
        
        # Add to status bar
        sb = self.app_context.main_window.statusBar()
        sb.addPermanentWidget(self.status_btn)

    def on_unload(self):
        if hasattr(self, 'status_btn'):
            self.app_context.main_window.statusBar().removeWidget(self.status_btn)
            self.status_btn.deleteLater()
        if self._dialog:
            self._dialog.close()

    def open_dialog(self):
        if not self._dialog:
            self._dialog = PluginManagerDialog(self.app_context.main_window)
            self._dialog.finished.connect(self._on_dialog_closed)
        
        self._dialog.show()
        self._dialog.raise_()
        self._dialog.activateWindow()

    def _on_dialog_closed(self):
        self._dialog = None

def create_plugin(app_context):
    return PluginManagerPlugin(app_context)
