
# plugins/navigation_toolbar.py
"""
导航面板插件（A4 - Refined）
- 将导航栏改为 QDockWidget，解决 QToolBar 拖拽卡顿问题，并支持与其他面板自由组合（Tabbing）。
- 内部包含一个 QToolBar 或简单的按钮组。
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QObject, Slot, QSize
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QDockWidget, QToolBar, QWidget, QVBoxLayout, QStyle

from core.signals import GlobalSignalBus
from core.api import Plugin

class NavigationDock(QDockWidget):
    def __init__(self, parent=None):
        super().__init__("导航", parent)
        self.setAllowedAreas(Qt.AllDockWidgetAreas)
        self.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable | QDockWidget.DockWidgetClosable)
        
        # Internal container
        # We use a QToolBar inside the dock to keep the "toolbar look" but gain "dock behavior"
        self.toolbar = QToolBar(self)
        self.toolbar.setFloatable(False) # The dock floats, not the toolbar inside
        self.toolbar.setMovable(False)   # The dock moves
        self.toolbar.setIconSize(QSize(24, 24))
        self.setWidget(self.toolbar)

class NavigationPlugin(Plugin):
    def __init__(self, app_context):
        self.app_context = app_context
        self.name = "Navigation"
        # We don't define 'get_widget' to return a widget for auto-docking logic in App 
        # because we want full control over the Dock creation to ensure it wraps a Toolbar nicely?
        # Actually standard Plugin interface uses get_widget() and App wraps it in a Dock.
        # BUT, standard App wrapping makes a generic Dock.
        # If we want a QToolBar *inside* the generic dock, get_widget() returning QToolBar works?
        # Let's try returning the QToolBar itself. App will wrap it in a QDockWidget.
        # This is exactly what we want!
        # Wait, if App wraps it, App sets the Dock title.
        # So I just need to return a QToolBar widget.
        pass

    def get_widget(self):
        # Create a QToolBar
        # The App logic will wrap this QToolBar in a QDockWidget.
        # This achieves the "Dock" behavior (movable window) with "Toolbar" look.
        tb = QToolBar()
        tb.setFloatable(False) # Inner toolbar shouldn't float out of the dock
        tb.setMovable(False)
        tb.setIconSize(QSize(16, 16))
        
        # Actions
        style = self.app_context.main_window.style()
        self.act_back = QAction(style.standardIcon(QStyle.SP_ArrowBack), "后退", tb)
        self.act_fwd = QAction(style.standardIcon(QStyle.SP_ArrowForward), "前进", tb)
        self.act_back.setEnabled(False)
        self.act_fwd.setEnabled(False)
        
        # Connect
        self.act_back.triggered.connect(self._on_back)
        self.act_fwd.triggered.connect(self._on_fwd)
        
        tb.addAction(self.act_back)
        tb.addAction(self.act_fwd)
        
        # Subscribe
        GlobalSignalBus.nav_history_state_changed.connect(self._on_state_changed)
        
        return tb

    def _on_back(self):
        GlobalSignalBus.back_navigation_requested.emit()

    def _on_fwd(self):
        GlobalSignalBus.forward_navigation_requested.emit()

    def _on_state_changed(self, can_back, can_fwd, page):
        self.act_back.setEnabled(can_back)
        self.act_fwd.setEnabled(can_fwd)

    def on_unload(self):
        try:
            GlobalSignalBus.nav_history_state_changed.disconnect(self._on_state_changed)
        except:
            pass

def create_plugin(app_context):
    return NavigationPlugin(app_context)