"""
This module defines the public API that is exposed to all plugins.
"""
from __future__ import annotations
import typing

if typing.TYPE_CHECKING:
    from .ui_manager import UIManager
    from PySide6.QtWidgets import QMainWindow

class AppContext:
    """
    A context object passed to each plugin upon registration.
    It provides access to core application components.
    
    Attributes:
        ui: The UI manager for adding components like dock widgets.
        file_indexer_service: Optional service providing file indexing/search capabilities.
        commands: The CommandRegistry instance used to register/query commands.
    """
    def __init__(self, ui_manager: 'UIManager', file_indexer_service=None, commands=None):
        # Core UI access
        self.ui = ui_manager
        # Service references exposed for plugins (set by the host app during startup)
        self.file_indexer_service = file_indexer_service
        # Command registry (populated by command_service plugin)
        self.commands = commands

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
