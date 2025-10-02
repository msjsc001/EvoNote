# core/signals.py
from PySide6.QtCore import QObject, Signal

class _GlobalSignalBus(QObject):
    """
    A singleton-like global signal bus for decoupled communication across the application.
    It allows different components (especially plugins) to communicate without direct dependencies.
    """
    completion_requested = Signal(str, str)
    """
    Emitted when a part of the UI requests a completion.
    
    Args:
        completion_type (str): The type of completion requested (e.g., 'page_link').
        query_text (str): The text to search for.
    """
    
    completion_results_ready = Signal(str, str, list)
    """
    Emitted by a service when completion results are available.
    
    Args:
        completion_type (str): The type of completion for which results are provided.
        query_text (str): The original query text that generated these results.
        results (list): A list of completion suggestions.
    """

# Instantiate the global bus. Import this instance to connect or emit signals.
GlobalSignalBus = _GlobalSignalBus()