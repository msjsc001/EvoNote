# core/command_palette.py
from __future__ import annotations

from typing import List
from PySide6.QtWidgets import QDialog, QLineEdit, QListWidget, QListWidgetItem, QVBoxLayout
from PySide6.QtCore import Qt, Slot, QPoint
from PySide6.QtGui import QShortcut, QKeySequence, QFont

from core.command import BaseCommand
from core.api import AppContext


class CommandPalette(QDialog):
    """
    Modal command palette dialog with live filtering and execution.

    Features (V0.4.3):
      - Modal dialog opened centered on main window
      - QLineEdit for filter input (simple substring match)
      - QListWidget for commands (title displayed, id in tooltip)
      - Keyboard navigation (Up/Down)
      - Enter or double-click to execute selected command and close
      - Escape to close
    """

    def __init__(self, app_context: AppContext, parent=None):
        super().__init__(parent)
        self.app_context = app_context
        self.setWindowTitle("命令面板")
        # Use WindowModal relative to parent to avoid global blocking and parenting issues
        self.setWindowModality(Qt.WindowModal)
        self.setModal(True)
        self.resize(520, 380)

        # UI
        self.input = QLineEdit(self)
        self.input.setPlaceholderText("输入以过滤命令…（子字符串匹配）")
        self.list = QListWidget(self)
        self.list.setSelectionMode(QListWidget.SingleSelection)

        layout = QVBoxLayout(self)
        layout.addWidget(self.input)
        layout.addWidget(self.list)
        self.setLayout(layout)

        # Shortcuts
        QShortcut(QKeySequence("Escape"), self, self.reject)

        # Data
        self._all_commands: List[BaseCommand] = []
        self._load_commands()
        self._refresh_list("")

        # Signals
        self.input.textChanged.connect(self.on_text_changed)
        self.list.itemActivated.connect(self._on_item_activated)

        # Focus: start in input, but ensure a default selection for Enter handling
        if self.list.count() > 0:
            self.list.setCurrentRow(0)

    def _load_commands(self):
        """Load all commands from the registry via app_context."""
        registry = getattr(self.app_context, "commands", None)
        if registry is None:
            self._all_commands = []
            return
        try:
            self._all_commands = registry.get_all_commands() or []
        except Exception:
            self._all_commands = []

    def _refresh_list(self, query: str):
        """
        Refresh visible command list using grouped substring match:
        - Group by id prefix before first '.'; no prefix -> 'misc'
        - Group order: app, file, then remaining alphabetically
        - Each group has a non-selectable header; only matching groups rendered
        """
        self.list.clear()
        q = (query or "").strip().lower()

        # Bucket matched commands into groups
        groups: dict[str, list[BaseCommand]] = {}
        for cmd in self._all_commands:
            title = getattr(cmd, "title", "") or ""
            cid = getattr(cmd, "id", "") or ""
            if not q or (q in title.lower() or q in cid.lower()):
                group = (cid.split(".", 1)[0].lower() if "." in cid else "misc") or "misc"
                groups.setdefault(group, []).append(cmd)

        # Group ordering
        def group_key(g: str):
            if g == "app":
                return (0, "")
            if g == "file":
                return (1, "")
            return (2, g)

        # Render groups with headers and sorted items
        for g in sorted(groups.keys(), key=group_key):
            cmds = sorted(groups[g], key=lambda c: (getattr(c, "title", "") or "").lower())
            # Header
            header = QListWidgetItem(f"[{g}]")
            # Non-selectable header
            header.setFlags(Qt.ItemIsEnabled)
            f: QFont = header.font()
            f.setBold(True)
            header.setFont(f)
            header.setData(Qt.UserRole, None)
            self.list.addItem(header)
            # Items
            for cmd in cmds:
                title = getattr(cmd, "title", "") or ""
                cid = getattr(cmd, "id", "") or ""
                tooltip = f"{title}\nID: {cid}"
                item = QListWidgetItem(title)
                item.setToolTip(tooltip)
                item.setData(Qt.UserRole, cmd)
                # Selectable by default
                self.list.addItem(item)

        self._ensure_selection()

    @Slot(str)
    def on_text_changed(self, text: str):
        self._refresh_list(text)
        # Ensure a real command (not header) is selected
        self._ensure_selection()

    def _current_command(self) -> BaseCommand | None:
        item = self.list.currentItem()
        if not item:
            return None
        cmd = item.data(Qt.UserRole)
        return cmd if cmd else None

    def _execute_selected(self):
        cmd = self._current_command()
        if cmd is None:
            return
        try:
            cmd.execute(self.app_context)
        except Exception as e:
            print(f"ERROR: Command execution failed: {e}")
        self.accept()  # Close dialog

    def keyPressEvent(self, event):
        """Allow Enter from the input field to execute current selection."""
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self._execute_selected()
            return
        # Forward Up/Down from input to list for navigation convenience
        if event.key() in (Qt.Key_Up, Qt.Key_Down) and self.input.hasFocus():
            self.list.setFocus()
            self.list.keyPressEvent(event)
            return
        super().keyPressEvent(event)

    def _on_item_activated(self, item: QListWidgetItem):
        self._execute_selected()

    def open_centered(self, parent):
        """
        Open the dialog centered on the given parent window.
        """
        target_parent = parent or self.parentWidget()
        if target_parent is not None:
            parent_rect = target_parent.geometry()
            center = parent_rect.center()
            top_left = center - QPoint(self.width() // 2, self.height() // 2)
            self.move(top_left)
        # Use non-blocking modal open to avoid reentrancy issues from menu/shortcut triggers
        self.open()
        # Ensure z-order and focus
        try:
            self.raise_()
        except Exception:
            pass
        self.activateWindow()
        self.input.setFocus()

    def _ensure_selection(self):
        """Select the first selectable (non-header) item."""
        for i in range(self.list.count()):
            it = self.list.item(i)
            if it and (it.flags() & Qt.ItemIsSelectable):
                self.list.setCurrentRow(i)
                return