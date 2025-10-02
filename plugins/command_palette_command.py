# plugins/command_palette_command.py
"""
Command Palette Command Plugin (no UI)

Registers 'app.command_palette' into the CommandRegistry.
Executing this command opens the Command Palette dialog.

Design:
- Uses decorator-based registration via app_context.commands.register inside create_plugin(app)
  to avoid global init order issues (per Scheme A).
- Primary path calls app.open_command_palette() for consistent behavior/logging.
- Fallback path instantiates CommandPalette directly when open_command_palette is unavailable.
"""

from __future__ import annotations

from PySide6.QtCore import QObject
from core.command import BaseCommand
from core.command_palette import CommandPalette


class _CommandPaletteCommandPlugin(QObject):
    def __init__(self, app):
        super().__init__()
        self.app = app


def create_plugin(app):
    registry = getattr(getattr(app, "app_context", None), "commands", None)
    if registry is None:
        print("ERROR: CommandRegistry not available; CommandPaletteCommand not registered.")
        return _CommandPaletteCommandPlugin(app)

    @registry.register()
    class CommandPaletteCommand(BaseCommand):
        id = "app.command_palette"
        title = "应用：命令面板"

        def execute(self, app_context):
            # Prefer the core application's open_command_palette for unified UX and diagnostics
            try:
                app.open_command_palette()
                return
            except Exception:
                pass

            # Fallback: construct the dialog directly if the app method is unavailable
            try:
                dlg = CommandPalette(app_context, parent=app_context.main_window)
                dlg.open_centered(app_context.main_window)
            except Exception as e:
                print(f"ERROR: Failed to open Command Palette via command: {e}")

    return _CommandPaletteCommandPlugin(app)