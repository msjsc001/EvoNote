"""
UI Test Plugin for EvoNote V0.1
This plugin is used to verify that the core application can load a UI component
from an external plugin.
"""
from PySide6.QtWidgets import QDockWidget, QLabel
from PySide6.QtCore import Qt

def register(app_context):
    """
    Plugin entry point. Called by the PluginManager during loading.
    Creates a simple QDockWidget and adds it to the main window.
    """
    # Create the main widget for the dock
    dock_widget = QDockWidget("UI插件", app_context.main_window)
    
    # Create a label to display a message
    label = QLabel("UI Plugin Loaded Successfully.")
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    
    # Set the label as the content of the dock widget
    dock_widget.setWidget(label)
    
    # Add the dock widget to the main window
    app_context.main_window.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dock_widget)
