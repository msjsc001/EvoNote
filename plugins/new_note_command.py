# plugins/new_note_command.py
"""
New Note Command Plugin (no UI)

Registers 'file.new_note' command into CommandRegistry.
"""

from __future__ import annotations

from PySide6.QtCore import QObject
from core.command import BaseCommand


class _NewNoteCommandPlugin(QObject):
    def __init__(self, app):
        super().__init__()
        self.app = app


def create_plugin(app):
    registry = getattr(app.app_context, "commands", None)
    if registry is None:
        print("ERROR: CommandRegistry not available; NewNoteCommand not registered.")
        return _NewNoteCommandPlugin(app)

    @registry.register()
    class NewNoteCommand(BaseCommand):
        id = "file.new_note"
        title = "文件：新建笔记"

        def execute(self, app_context):
            print("INFO: Executing command: New Note")

    return _NewNoteCommandPlugin(app)