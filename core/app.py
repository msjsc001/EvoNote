import sys
from PySide6.QtWidgets import QApplication, QMainWindow
from .plugin_manager import PluginManager
from .ui_manager import UIManager
from services.file_indexer_service import FileIndexerService
from .signals import GlobalSignalBus

VERSION = "0.4.1"

class MainWindow(QMainWindow):
    """
    EvoNote's main window.
    This window serves as the main container for the application's UI,
    including a dock area for plugins and a status bar.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"EvoNote V{VERSION}")
        self.setCentralWidget(None)  # Prepare for QDockWidget

        # As per FR-1.1, the central area must be a dock area.
        # By default, QMainWindow allows docking widgets. We make it explicit
        # that we don't have a central widget pushing them away.
        self.setDockNestingEnabled(True)

        # As per FR-1.1, a status bar is required.
        self.statusBar()

class EvoNoteApp:
    """
    The core application class for EvoNote.
    It initializes the Qt application and the main window.
    """
    def __init__(self, qt_app=None):
        if qt_app is None:
            self.qt_app = QApplication(sys.argv)
        else:
            self.qt_app = qt_app
        self.main_window = MainWindow()
        self.ui_manager = UIManager(self.main_window)
        self.plugin_manager = PluginManager()
        self.file_indexer_service = FileIndexerService(vault_path=".")

    def run(self):
        """
        Loads plugins, shows the main window, and starts the event loop.
        """
        self.file_indexer_service.start()
        self.plugin_manager.discover_and_load_plugins(self)
        
        # In App.__init__ after loading plugins
        all_plugins = self.plugin_manager.get_all_plugins()
        for plugin in all_plugins:
            # Check if the plugin has a get_widget method
            if hasattr(plugin, 'get_widget'):
                widget = plugin.get_widget()
                if widget:
                    self.ui_manager.add_widget(widget) # Assuming ui_manager has this method
        
        self.main_window.show()

        # Request initial completion list after the UI is fully loaded and shown
        GlobalSignalBus.completion_requested.emit('page_link', '')
        
        exit_code = self.qt_app.exec()
        self.file_indexer_service.stop()
        return exit_code
