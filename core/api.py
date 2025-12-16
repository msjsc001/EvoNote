
"""
This module defines the public API that is exposed to all plugins.
"""
from __future__ import annotations
import typing
from typing import Optional, List, Dict, Any

if typing.TYPE_CHECKING:
    from .ui_manager import UIManager
    from services.file_indexer_service import FileIndexerService
    from PySide6.QtWidgets import QMainWindow

class EvoNoteAPI:
    """
    The Stable Facade API for EvoNote.
    Plugins should prefer using this over accessing raw services directly.
    """
    def __init__(self, context: 'AppContext'):
        self._context = context

    def open_note(self, title_or_path: str):
        """
        Opens a note by title (e.g., "My Note") or relative path.
        """
        # Emitting global signal to trigger app navigation
        from .signals import GlobalSignalBus
        GlobalSignalBus.page_navigation_requested.emit(title_or_path)

    def search(self, query: str) -> List[Dict[str, Any]]:
        """
        Performs a full-text search.
        Returns [{'path':..., 'highlights':...}]
        """
        svc = self._context.file_indexer_service
        if hasattr(svc, "search"):
            return svc.search(query)
        return []

    def get_vault_path(self) -> Optional[str]:
        """Returns the absolute path of the current vault."""
        return self._context.current_vault_path

class AppContext:
    """
    A context object passed to each plugin upon registration.
    It provides access to core application components.
    
    Attributes:
        api: The high-level EvoNoteAPI instance.
        ui: The UI manager for adding components like dock widgets.
        file_indexer_service: Optional service providing file indexing/search capabilities.
        commands: The CommandRegistry instance used to register/query commands.
    """
    def __init__(self, ui_manager: 'UIManager', file_indexer_service: 'FileIndexerService'=None, commands=None, current_vault_path: Optional[str] = None):
        # Core UI access
        self.ui = ui_manager
        # Service references exposed for plugins (set by the host app during startup)
        self.file_indexer_service = file_indexer_service
        # Command registry (populated by command_service plugin)
        self.commands = commands
        # Current vault absolute path (or None when not selected)
        self.current_vault_path = current_vault_path
        
        # Initialize the Stable API Facade
        self.api = EvoNoteAPI(self)

    @property
    def main_window(self) -> 'QMainWindow':
        """
        Provides direct access to the main window.
        Note: For adding UI elements like docks, prefer using the `ui` manager.
        """
        return self.ui._main_window


class Plugin:
    """
    Base class for all plugins.
    """
    pass
