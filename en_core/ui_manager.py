# en_core/ui_manager.py
from PySide6.QtWidgets import QMainWindow, QDockWidget
from PySide6.QtCore import Qt

class UIManager:
    """
    Manages the UI of the main application window, providing a stable interface
    for plugins to add UI components like dock widgets.
    """
    def __init__(self, main_window: QMainWindow):
        """
        Initializes the UIManager with a reference to the main window.
        
        :param main_window: The main QMainWindow instance of the application.
        """
        if not isinstance(main_window, QMainWindow):
            raise TypeError("main_window must be an instance of QMainWindow")
        self._main_window = main_window

    def add_dock_widget(self, dock_widget: QDockWidget, area: Qt.DockWidgetArea = Qt.DockWidgetArea.LeftDockWidgetArea):
        """
        Adds a QDockWidget to the main window in a specified area.

        :param dock_widget: The QDockWidget instance to add.
        :param area: The Qt.DockWidgetArea to place the widget in. 
                     Defaults to LeftDockWidgetArea.
        """
        if not isinstance(dock_widget, QDockWidget):
            raise TypeError("dock_widget must be an instance of QDockWidget")
        
        self._main_window.addDockWidget(area, dock_widget)