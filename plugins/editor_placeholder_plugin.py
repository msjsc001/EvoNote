# plugins/editor_placeholder_plugin.py
from PySide6.QtWidgets import QDockWidget, QPlainTextEdit
from PySide6.QtCore import Qt
from en_core.api import AppContext

def register(app_context: AppContext):
    """
    Registers the editor placeholder plugin.
    """
    # Create the main dock widget for the editor
    dock_widget = QDockWidget("编辑器", app_context.main_window)
    
    # Create the placeholder text edit
    text_edit = QPlainTextEdit(dock_widget)
    text_edit.setPlaceholderText("This is the main editor area...")
    dock_widget.setWidget(text_edit)
    
    # Add the dock widget to the main window
    # By placing it in the same area as the file browser, they will be tabbed
    # initially. Let's place it on the right to have them side-by-side.
    app_context.ui.add_dock_widget(dock_widget, Qt.DockWidgetArea.RightDockWidgetArea)