# core/signals.py
from PySide6.QtCore import QObject, Signal

class _GlobalSignalBus(QObject):
    """
    A singleton-like global signal bus for decoupled communication across the application.
    It allows different components (especially plugins) to communicate without direct dependencies.
    """

    # ---- Completion (existing) ----
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

    # ---- Navigation (existing) ----
    page_navigation_requested = Signal(str)
    """
    Emitted when the user requests navigation to a page via clicking a [[Page Link]] in the editor.

    Args:
        page_title (str): The target page title or path to navigate to.
    """

    page_open_requested = Signal(str)
    """
    Emitted when the user requests to open a page in a new independent window (Shift+Click).

    Args:
        page_title (str): The target page title or path to open in a new window.
    """

    # ---- Backlink Panel (new for V0.4.2b) ----
    active_page_changed = Signal(str)
    """
    Broadcasts when the currently active page changes.

    Args:
        page_path (str): The current active page path, relative and including extension
                         (e.g., 'Note A.md').
    """

    backlink_query_requested = Signal(str)
    """
    Emitted to request backlink data for a given page.

    Args:
        page_path (str): The target page path, relative and including extension
                         (e.g., 'Note A.md').
    """

    backlink_results_ready = Signal(str, list)
    """
    Emitted when backlink query results are ready.
 
    Args:
        page_path (str): The original requested page path, relative and including extension.
        results (list): A list of source page paths (relative, including extension)
                        that link to the target page.
    """

    # ---- Vault State (ST-16) ----
    vault_state_changed = Signal(bool, str)
    """
    Broadcasts when the active vault availability changes.

    Args:
        has_vault (bool): Whether there is an active vault.
        vault_path (str): Current vault absolute path; empty string when none.
    """
# Instantiate the global bus. Import this instance to connect or emit signals.
GlobalSignalBus = _GlobalSignalBus()