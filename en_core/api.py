"""
This module defines the public API that is exposed to all plugins.
For V0.1, this is limited to the AppContext.
"""

class AppContext:
    """
    A context object passed to each plugin upon registration.
    It provides access to core application components.
    
    Attributes:
        main_window: The main QMainWindow instance of the application.
    """
    def __init__(self, main_window):
        self.main_window = main_window
