# plugins/file_browser_plugin.py
from PySide6.QtWidgets import QDockWidget, QTreeView
from PySide6.QtCore import Qt
from en_core.api import AppContext

def register(app_context: AppContext):
    """
    Registers the file browser plugin.
    """
    # Create the main dock widget for the file browser
    dock_widget = QDockWidget("文件浏览器", app_context.main_window)
    
    # Create the placeholder tree view
    tree_view = QTreeView(dock_widget)
    dock_widget.setWidget(tree_view)
    
    # Add the dock widget to the left area of the main window
    app_context.ui.add_dock_widget(dock_widget, Qt.DockWidgetArea.LeftDockWidgetArea)