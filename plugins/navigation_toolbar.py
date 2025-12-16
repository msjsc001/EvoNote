
from __future__ import annotations

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QWidget, QHBoxLayout, QToolButton, QStyle, QSizePolicy

from core.signals import GlobalSignalBus
from core.api import Plugin

class NavigationPlugin(Plugin):
    def __init__(self, app_context):
        self.app_context = app_context
        self.name = "Navigation"

    def get_widget(self):
        # Create a generic QWidget to act as the panel content
        # This allows the DockWidget to be resized freely by the user (unlike QToolBar which has fixed size hints)
        panel = QWidget()
        # Explicitly allow vertical resizing so QMainWindow splitter works
        panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        panel.setMinimumHeight(40) # Ensure enough height to be easily grabbed
        
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        
        # Actions/Buttons
        style = self.app_context.main_window.style()
        
        self.btn_back = QToolButton()
        self.btn_back.setIcon(style.standardIcon(QStyle.SP_ArrowBack))
        self.btn_back.setToolTip("后退")
        self.btn_back.setEnabled(False)
        self.btn_back.setIconSize(QSize(20, 20))
        self.btn_back.setAutoRaise(True) # ToolBar look
        
        self.btn_fwd = QToolButton()
        self.btn_fwd.setIcon(style.standardIcon(QStyle.SP_ArrowForward))
        self.btn_fwd.setToolTip("前进")
        self.btn_fwd.setEnabled(False)
        self.btn_fwd.setIconSize(QSize(20, 20))
        self.btn_fwd.setAutoRaise(True)
        
        layout.addWidget(self.btn_back)
        layout.addWidget(self.btn_fwd)
        layout.addStretch() # Push buttons to left
        
        # Connect
        self.btn_back.clicked.connect(self._on_back)
        self.btn_fwd.clicked.connect(self._on_fwd)
        
        # Subscribe
        GlobalSignalBus.nav_history_state_changed.connect(self._on_state_changed)
        
        return panel

    def _on_back(self):
        GlobalSignalBus.back_navigation_requested.emit()

    def _on_fwd(self):
        GlobalSignalBus.forward_navigation_requested.emit()

    def _on_state_changed(self, can_back, can_fwd, page):
        self.btn_back.setEnabled(can_back)
        self.btn_fwd.setEnabled(can_fwd)

    def on_unload(self):
        try:
            GlobalSignalBus.nav_history_state_changed.disconnect(self._on_state_changed)
        except:
            pass

def create_plugin(app_context):
    return NavigationPlugin(app_context)
