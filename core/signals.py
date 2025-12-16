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

    # ---- Navigation History (V0.4.5b) ----
    back_navigation_requested = Signal()
    """
    当用户点击后退时由导航工具栏发出。无参数。
    """

    forward_navigation_requested = Signal()
    """
    当用户点击前进时由导航工具栏发出。无参数。
    """

    nav_history_state_changed = Signal(bool, bool, str)
    """
    由导航历史服务广播当前历史可用性与当前页面。

    Args:
        can_back (bool): 是否可后退
        can_forward (bool): 是否可前进
        current_page (str): 当前页面的相对路径且包含扩展名，如 'Note A.md'；无当前页面时传空字符串
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

    # ---- Panel Context (V0.4.6) ----
    panel_context_changed = Signal(str)
    """
    Emitted when an editor gains focus or performs a local navigation,
    broadcasting the current page to update panels (e.g., backlinks).

    Args:
        page_path (str): The current active page path, relative and including extension
                         (e.g., 'Note A.md').
    """

    # ---- Plugin Lifecycle (V0.4.7) ----
    plugin_enable_requested = Signal(str)
    """
    Emitted to request enabling a plugin.
    
    Args:
        plugin_id (str): The unique identifier (usually filename or dir name) of the plugin.
    """

    plugin_disable_requested = Signal(str)
    """
    Emitted to request disabling a plugin.
    
    Args:
        plugin_id (str): The unique identifier of the plugin.
    """

    plugin_state_changed = Signal(str, bool)
    """
    Broadcasts when a plugin's state changes (enabled/disabled).
    
    Args:
        plugin_id (str): The unique identifier of the plugin.
        enabled (bool): True if enabled, False if disabled.
    """

    plugin_error = Signal(str, str)
    """
    Emitted when a plugin encounters a critical error.
    
    Args:
        plugin_id (str): The unique identifier of the plugin (or 'core'/'unknown').
        error_message (str): A human-readable error description.
    """
# Instantiate the global bus. Import this instance to connect or emit signals.
GlobalSignalBus = _GlobalSignalBus()