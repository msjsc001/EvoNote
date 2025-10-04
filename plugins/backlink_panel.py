# plugins/backlink_panel.py
"""
Backlink Panel UI Plugin
- Provides a QDockWidget titled "反向链接" with a QListWidget inside.
- Listens to GlobalSignalBus.active_page_changed to request backlinks.
- Emits GlobalSignalBus.backlink_query_requested to trigger async query.
- Listens to GlobalSignalBus.backlink_results_ready to populate the list.
- Clicking an item emits GlobalSignalBus.page_navigation_requested to navigate.
"""

import os
from pathlib import Path

from PySide6.QtCore import Qt, Slot, QObject
from PySide6.QtWidgets import QDockWidget, QListWidget, QListWidgetItem

from core.signals import GlobalSignalBus


class BacklinkPanelPlugin(QObject):
    """
    UI plugin for displaying backlinks to the current active page.
    """
    # Dock to the right side per specification
    dock_area = Qt.RightDockWidgetArea

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.dock_widget: QDockWidget | None = None
        self.list_widget: QListWidget | None = None
        self.current_page_path: str | None = None

        # Connect global signals
        GlobalSignalBus.active_page_changed.connect(self.on_active_page_changed)
        GlobalSignalBus.backlink_results_ready.connect(self.on_backlink_results_ready)

    def get_widget(self) -> QDockWidget:
        """
        Creates and returns the dock widget.
        """
        if self.dock_widget is None:
            self.dock_widget = QDockWidget("反向链接")
            self.list_widget = QListWidget(self.dock_widget)
            self.list_widget.setSelectionMode(QListWidget.SingleSelection)
            self.list_widget.itemActivated.connect(self._on_item_activated)
            self.list_widget.itemClicked.connect(self._on_item_activated)
            self.dock_widget.setWidget(self.list_widget)
        return self.dock_widget

    @Slot(str)
    def on_active_page_changed(self, page_path: str):
        """
        When active page changes:
        - Clear the current list
        - Request backlinks asynchronously via the global signal
        """
        self.current_page_path = page_path
        if self.list_widget is not None:
            self.list_widget.clear()
        # Immediately request backlink query
        GlobalSignalBus.backlink_query_requested.emit(page_path)

    @Slot(str, list)
    def on_backlink_results_ready(self, page_path: str, results: list):
        """
        When backlink results arrive, ensure they correspond to the
        current active page, then populate the list.
        """
        if page_path != self.current_page_path:
            return
        if self.list_widget is None:
            return

        self.list_widget.clear()
        for src_path in results or []:
            label = os.path.splitext(os.path.basename(src_path))[0] if src_path else ""
            item = QListWidgetItem(label or "")
            item.setToolTip(src_path)
            # Store full relative path (with extension) for navigation
            item.setData(Qt.UserRole, src_path)
            self.list_widget.addItem(item)

    def _on_item_activated(self, item: QListWidgetItem):
        """
        Emits page navigation request when an item is clicked/activated.
        """
        if not item:
            return
        src_path = item.data(Qt.UserRole) or item.text()
        if src_path:
            GlobalSignalBus.page_navigation_requested.emit(src_path)

    def unload(self):
        """
        Optional cleanup if the host supports unloading.
        """
        try:
            GlobalSignalBus.active_page_changed.disconnect(self.on_active_page_changed)
        except Exception:
            pass
        try:
            GlobalSignalBus.backlink_results_ready.disconnect(self.on_backlink_results_ready)
        except Exception:
            pass


def create_plugin(app):
    return BacklinkPanelPlugin(app)