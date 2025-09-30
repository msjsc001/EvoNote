"""
Core Interaction Test Plugin for EvoNote V0.1
This plugin verifies that plugins can interact with core application
components, like the status bar.
"""

def register(app_context):
    """
    Plugin entry point.
    Accesses the main window's status bar and displays a message.
    """
    status_bar = app_context.main_window.statusBar()
    
    # The message will be shown for 5000 milliseconds (5 seconds).
    status_bar.showMessage("Core Plugin Loaded Successfully.", 5000)
