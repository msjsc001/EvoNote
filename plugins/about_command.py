# plugins/about_command.py
"""
About Command Plugin (no UI)

Registers 'app.about' command into CommandRegistry.
"""

from __future__ import annotations

from PySide6.QtCore import QObject
from core.command import BaseCommand


class _AboutCommandPlugin(QObject):
    def __init__(self, app):
        super().__init__()
        self.app = app


def create_plugin(app):
    registry = getattr(app.app_context, "commands", None)
    if registry is None:
        print("ERROR: CommandRegistry not available; AboutCommand not registered.")
        return _AboutCommandPlugin(app)

    @registry.register()
    class AboutCommand(BaseCommand):
        id = "app.about"
        title = "关于：EvoNote"

        def execute(self, app_context):
            print("INFO: Executing command: About EvoNote")

    return _AboutCommandPlugin(app)