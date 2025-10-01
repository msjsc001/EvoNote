import sys
from PySide6.QtWidgets import QApplication, QMainWindow
from .plugin_manager import PluginManager
from .api import AppContext
from .ui_manager import UIManager

class MainWindow(QMainWindow):
    """
    EvoNote's main window.
    This window serves as the main container for the application's UI,
    including a dock area for plugins and a status bar.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("EvoNote V0.2")
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
    def __init__(self):
        self.qt_app = QApplication(sys.argv)
        self.main_window = MainWindow()
        self.ui_manager = UIManager(self.main_window)
        self.app_context = AppContext(self.ui_manager)
        self.plugin_manager = PluginManager(self.app_context)

    def run(self):
        """
        Loads plugins, shows the main window, and starts the event loop.
        """
        self.plugin_manager.discover_and_load_plugins()
        """
        Shows the main window and starts the application's event loop.
        """
        self.main_window.show()
        return self.qt_app.exec()
