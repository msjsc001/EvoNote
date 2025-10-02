import sys
import logging
import os
from PySide6.QtWidgets import QApplication, QMainWindow
from PySide6.QtCore import Qt, QEvent, QObject
from PySide6.QtGui import QShortcut, QKeySequence, QAction
from .command_palette import CommandPalette
from .plugin_manager import PluginManager
from .ui_manager import UIManager
from services.file_indexer_service import FileIndexerService
from .signals import GlobalSignalBus
from .api import AppContext

VERSION = "0.4.3"

class _GlobalShortcutFilter(QObject):
    """
    Application-wide key event filter to catch Ctrl/Cmd+P (and Ctrl+Shift+P) reliably,
    avoiding conflicts with widget-level shortcuts or ambiguous QAction bindings.
    """
    def __init__(self, trigger_cb):
        super().__init__()
        self._trigger_cb = trigger_cb

    def eventFilter(self, obj, event):
        t = event.type()
        if t in (QEvent.ShortcutOverride, QEvent.KeyPress):
            try:
                key = event.key()
                mods = event.modifiers()
            except Exception:
                return False
            ctrl_or_meta = bool(mods & (Qt.ControlModifier | Qt.MetaModifier))
            if key == Qt.Key_P and ctrl_or_meta:
                try:
                    event.accept()
                except Exception:
                    pass
                try:
                    self._trigger_cb()
                except Exception as e:
                    print(f"WARNING: Command Palette shortcut filter error: {e}")
                return True
        return False

class MainWindow(QMainWindow):
    """
    EvoNote's main window.
    This window serves as the main container for the application's UI,
    including a dock area for plugins and a status bar.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"EvoNote V{VERSION}")
        self.setCentralWidget(None)  # Prepare for QDockWidget

        # As per FR-1.1, the central area must be a dock area.
        # By default, QMainWindow allows docking widgets. We make it explicit
        # that we don't have a central widget pushing them away.
        self.setDockNestingEnabled(True)

        # As per FR-1.1, a status bar is required.
        self.statusBar()

class EvoNoteApp:
    """
    The core application class for EvoNote.
    It initializes the Qt application and the main window.
    """
    def __init__(self, qt_app=None):
        if qt_app is None:
            self.qt_app = QApplication(sys.argv)
        else:
            self.qt_app = qt_app
        self.main_window = MainWindow()
        self.ui_manager = UIManager(self.main_window)
        self.plugin_manager = PluginManager()
        self.file_indexer_service = FileIndexerService(vault_path=".")
        # Initialize AppContext early; CommandRegistry will attach later via command_service plugin
        self.app_context = AppContext(self.ui_manager, file_indexer_service=self.file_indexer_service, commands=None)

        # Connect global navigation signal (FR-3.1)
        GlobalSignalBus.page_navigation_requested.connect(self.on_page_navigation_requested)
        
        # Global shortcut: Ctrl+P / Cmd+P to open Command Palette
        self.shortcut_cmd_palette_ctrl = QShortcut(QKeySequence("Ctrl+P"), self.main_window)
        self.shortcut_cmd_palette_ctrl.setContext(Qt.ApplicationShortcut)
        self.shortcut_cmd_palette_ctrl.activated.connect(self._on_cmd_palette_shortcut)

        # macOS: Cmd+P (Meta)
        self.shortcut_cmd_palette_cmd = QShortcut(QKeySequence("Meta+P"), self.main_window)
        self.shortcut_cmd_palette_cmd.setContext(Qt.ApplicationShortcut)
        self.shortcut_cmd_palette_cmd.activated.connect(self._on_cmd_palette_shortcut)

        # Fallback: Ctrl+Shift+P (common for command palettes)
        self.shortcut_cmd_palette_ctrl_shift = QShortcut(QKeySequence("Ctrl+Shift+P"), self.main_window)
        self.shortcut_cmd_palette_ctrl_shift.setContext(Qt.ApplicationShortcut)
        self.shortcut_cmd_palette_ctrl_shift.activated.connect(self._on_cmd_palette_shortcut)

        # Optional Tools menu; disabled by default. Enable via EVONOTE_TOOLS_MENU=1
        try:
            if os.getenv("EVONOTE_TOOLS_MENU", "0") in ("1", "true", "True"):
                mb = self.main_window.menuBar()
                mb.setVisible(True)
                tools_menu = mb.addMenu("工具")
                act_cmd_palette = QAction("命令面板…", self.main_window)
                # 留空菜单快捷键，避免与全局 QShortcut 冲突导致“Ambiguous shortcut overload”
                act_cmd_palette.triggered.connect(self.open_command_palette)
                tools_menu.addAction(act_cmd_palette)
            else:
                # 默认隐藏菜单栏，满足“菜单不锁死在顶部”的诉求；可通过 EVONOTE_TOOLS_MENU=1 显示
                self.main_window.menuBar().setVisible(False)
        except Exception as e:
            print(f"WARNING: Failed to create menu item for Command Palette: {e}")

        # Global event filter fallback to capture shortcuts reliably (handles IME/ambiguous conflicts)
        self._cmd_palette_dialog = None
        self._shortcut_filter = _GlobalShortcutFilter(self._on_cmd_palette_shortcut)
        try:
            self.qt_app.installEventFilter(self._shortcut_filter)
            self.main_window.installEventFilter(self._shortcut_filter)
        except Exception as e:
            print(f"WARNING: Failed to install global shortcut filter: {e}")

        # Log ambiguous activations if any
        try:
            self.shortcut_cmd_palette_ctrl.activatedAmbiguously.connect(lambda: print("WARNING: Ctrl+P shortcut ambiguous"))
            self.shortcut_cmd_palette_ctrl_shift.activatedAmbiguously.connect(lambda: print("WARNING: Ctrl+Shift+P shortcut ambiguous"))
            self.shortcut_cmd_palette_cmd.activatedAmbiguously.connect(lambda: print("WARNING: Cmd+P shortcut ambiguous"))
            print("INFO: Command Palette shortcuts registered.")
        except Exception as e:
            print(f"WARNING: Failed to wire shortcut diagnostics: {e}")

        # Global event filter fallback to capture shortcuts reliably (handles IME/ambiguous conflicts)
        self._cmd_palette_dialog = None
        self._shortcut_filter = _GlobalShortcutFilter(self._on_cmd_palette_shortcut)
        try:
            self.qt_app.installEventFilter(self._shortcut_filter)
        except Exception as e:
            print(f"WARNING: Failed to install global shortcut filter: {e}")
        
    def on_page_navigation_requested(self, page_title: str):
        """
        FR-3.2: Respond to navigation requests by logging to console.
        """
        print(f"INFO: Navigation to page '{page_title}' requested.")
        # Normalize to relative path with extension and broadcast active page change
        page_path = page_title if page_title.lower().endswith('.md') else f"{page_title}.md"
        GlobalSignalBus.active_page_changed.emit(page_path)

    def open_command_palette(self):
        """Open the Command Palette dialog centered on the main window."""
        print("INFO: Opening Command Palette...")
        # Reuse existing dialog if already open
        if getattr(self, "_cmd_palette_dialog", None) is not None and self._cmd_palette_dialog.isVisible():
            try:
                self._cmd_palette_dialog.raise_()
                self._cmd_palette_dialog.activateWindow()
                try:
                    # Focus filter input when available
                    self._cmd_palette_dialog.input.setFocus()
                except Exception:
                    pass
            except Exception:
                pass
            return

        dlg = CommandPalette(self.app_context, parent=self.main_window)
        self._cmd_palette_dialog = dlg
        try:
            dlg.finished.connect(self._on_command_palette_closed)
        except Exception:
            pass
        dlg.open_centered(self.main_window)

    def _on_cmd_palette_shortcut(self):
        """Unified handler for command palette shortcut(s)."""
        print("INFO: Shortcut triggered: Command Palette")
        self.open_command_palette()

    def _on_command_palette_closed(self, result):
        """Reset dialog reference after it is closed to allow reopening."""
        self._cmd_palette_dialog = None

    def run(self):
        """
        Loads plugins, shows the main window, and starts the event loop.
        """
        self.file_indexer_service.start()
        self.plugin_manager.discover_and_load_plugins(self)
        
        # In App.__init__ after loading plugins
        all_plugins = self.plugin_manager.get_all_plugins()
        for plugin in all_plugins:
            # Check if the plugin has a get_widget method
            if hasattr(plugin, 'get_widget'):
                widget = plugin.get_widget()
                if widget:
                    # Support plugin-specified dock area when available
                    area = getattr(plugin, 'dock_area', None)
                    if area is None:
                        self.ui_manager.add_widget(widget)
                    else:
                        self.ui_manager.add_dock_widget(widget, area)
        
        self.main_window.show()

        # Broadcast initial active page so panels can request data
        GlobalSignalBus.active_page_changed.emit('Note A.md')

        # Request initial completion list after the UI is fully loaded and shown
        GlobalSignalBus.completion_requested.emit('page_link', '')
        
        exit_code = self.qt_app.exec()
        self.file_indexer_service.stop()
        return exit_code
