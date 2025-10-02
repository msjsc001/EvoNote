"""
Defines BaseCommand abstract class for EvoNote command system.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .api import AppContext


class BaseCommand(ABC):
    """
    Abstract base class for all commands executable via the Command Palette.

    Attributes:
        id: Unique identifier (e.g., "file.new_note").
        title: Human-friendly title shown in UI (e.g., "文件：新建笔记").
    """

    id: str
    title: str

    @abstractmethod
    def execute(self, app_context: 'AppContext') -> None:
        """
        Execute the command.
        """
        raise NotImplementedError

    def __repr__(self) -> str:
        return f"<Command id={getattr(self, 'id', '?')} title={getattr(self, 'title', '?')}>"