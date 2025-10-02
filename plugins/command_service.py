# plugins/command_service.py
"""
Command Service Plugin (no UI)

Provides a CommandRegistry with decorator-based registration:
    @app.app_context.commands.register()
    class MyCommand(BaseCommand):
        id = "group.action"
        title = "组：动作"
        def execute(self, app_context): ...

This plugin must load before any command plugins so that the registry is available.
"""

from __future__ import annotations

from typing import Dict, List, Type, Callable, Optional
from PySide6.QtCore import QObject

from core.command import BaseCommand


class CommandRegistry:
    """
    Central registry for commands with a decorator-based registration API.

    Usage:
        registry = CommandRegistry()

        @registry.register()
        class ExampleCommand(BaseCommand):
            id = "example.id"
            title = "示例：命令"
            def execute(self, app_context):
                print("Hello")

    Notes:
        - Each Command class must be a subclass of BaseCommand.
        - Each Command instance must have unique 'id' and a non-empty 'title'.
        - 'execute(app_context)' will be invoked when the command is triggered.
    """

    def __init__(self) -> None:
        self._commands: Dict[str, BaseCommand] = {}

    def register(self) -> Callable[[Type[BaseCommand]], Type[BaseCommand]]:
        """
        Decorator for registering a command class.

        Returns:
            A decorator that validates, instantiates, and registers the command class.
        """

        def _decorator(cls: Type[BaseCommand]) -> Type[BaseCommand]:
            # Validate subclass
            if not isinstance(cls, type) or not issubclass(cls, BaseCommand):
                raise TypeError("Registered command must be a subclass of BaseCommand")

            # Instantiate
            try:
                instance = cls()  # Commands are expected to have no-arg __init__
            except Exception as e:
                raise RuntimeError(f"Failed to instantiate command '{cls.__name__}': {e}") from e

            # Validate required attributes
            cmd_id = getattr(instance, "id", None)
            title = getattr(instance, "title", None)
            if not isinstance(cmd_id, str) or not cmd_id.strip():
                raise ValueError(f"Command '{cls.__name__}' is missing valid 'id' attribute")
            if not isinstance(title, str) or not title.strip():
                raise ValueError(f"Command '{cls.__name__}' is missing valid 'title' attribute")

            if cmd_id in self._commands:
                # Do not override silently; raise to surface conflicts early
                raise ValueError(f"Duplicate command id '{cmd_id}' detected")

            self._commands[cmd_id] = instance
            print(f"INFO: Command registered: {cmd_id} -> {title}")
            return cls

        return _decorator

    def register_instance(self, instance: BaseCommand) -> None:
        """
        Programmatically register an already-instantiated command.
        """
        if not isinstance(instance, BaseCommand):
            raise TypeError("Instance must be a BaseCommand")
        cmd_id = getattr(instance, "id", None)
        title = getattr(instance, "title", None)
        if not isinstance(cmd_id, str) or not cmd_id.strip():
            raise ValueError("Command instance missing valid 'id'")
        if not isinstance(title, str) or not title.strip():
            raise ValueError("Command instance missing valid 'title'")
        if cmd_id in self._commands:
            raise ValueError(f"Duplicate command id '{cmd_id}' detected")
        self._commands[cmd_id] = instance
        print(f"INFO: Command instance registered: {cmd_id} -> {title}")

    def get_all_commands(self) -> List[BaseCommand]:
        """
        Returns all registered commands as a list.
        The list is sorted by command title for stable UI presentation.
        """
        return sorted(self._commands.values(), key=lambda c: getattr(c, "title", "").lower())

    def get_by_id(self, cmd_id: str) -> Optional[BaseCommand]:
        """
        Lookup a command by its unique id.
        """
        return self._commands.get(cmd_id)


class CommandServicePlugin(QObject):
    """
    Service plugin that owns the global CommandRegistry and exposes it via app.app_context.commands.
    """

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.registry = CommandRegistry()

        # Attach registry to the application's AppContext
        app_context = getattr(self.app, "app_context", None)
        if app_context is None:
            # Fail safe: try to build a minimal context if host didn't set it (not expected).
            raise RuntimeError("AppContext is not initialized on the host application")

        # Expose registry via context
        app_context.commands = self.registry
        # Optional convenience alias: allow app.commands if desired by other components
        setattr(self.app, "commands", self.registry)

        print("INFO: Command service initialized and registry attached to app_context.")


def create_plugin(app):
    """
    Plugin entry point expected by PluginManager.
    Ensures the command registry is ready for subsequent command plugins.
    """
    return CommandServicePlugin(app)