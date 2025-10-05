import sys
import logging
import os
from pathlib import Path
from PySide6.QtWidgets import QApplication, QMainWindow, QDockWidget
from PySide6.QtCore import Qt, QEvent, QObject
from PySide6.QtGui import QShortcut, QKeySequence, QAction
from .command_palette import CommandPalette
from .plugin_manager import PluginManager
from .ui_manager import UIManager
from services.file_indexer_service import FileIndexerService
from services.navigation_history_service import NavigationHistoryService
from .signals import GlobalSignalBus
from .api import AppContext
from .config_manager import (
    load_config,
    save_config,
    validate_vault_path,
    ensure_vault_structure,
    perform_one_time_cleanup_if_needed,
    add_vault,
    set_current_vault,
    get_nav_history_maxlen,
)

VERSION = "0.4.7"

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

        # Navigation history service (V0.4.5b)
        self._nav_is_pointer_move = False  # 指针移动保护标志

        # Load global config early and perform one-time cleanup (program directory only)
        app_dir = Path(__file__).resolve().parent.parent
        try:
            cfg = load_config()
        except Exception as e:
            print(f"WARNING: Failed to load config; using defaults. {e}")
            cfg = {"version": "0.4.5a", "vaults": [], "current_vault": None, "flags": {"cleaned_program_dir_v0_4_5a": False}}

        try:
            cfg2 = perform_one_time_cleanup_if_needed(cfg, app_dir)
            if cfg2 != cfg:
                save_config(cfg2)
            cfg = cfg2
        except Exception as e:
            print(f"WARNING: One-time cleanup step encountered error: {e}")

        # Read navigation history max length from config and create service
        nav_max = get_nav_history_maxlen(cfg)
        self.nav_history = NavigationHistoryService(maxlen=nav_max)

        # Resolve initial vault for indexer service
        initial_vault = cfg.get("current_vault")
        vault_for_service = Path(".")
        if isinstance(initial_vault, str) and initial_vault.strip():
            ok, msg = validate_vault_path(initial_vault, app_dir)
            if not ok:
                logging.error(f"Invalid current_vault in config '{initial_vault}': {msg}. Falling back to '.'")
            else:
                try:
                    ensure_vault_structure(Path(initial_vault))
                except Exception as e:
                    logging.warning(f"Failed to ensure vault structure at {initial_vault}: {e}")
                else:
                    vault_for_service = Path(initial_vault)

        self.file_indexer_service = FileIndexerService(vault_path=str(vault_for_service))
        # Initialize AppContext early; CommandRegistry will attach later via command_service plugin
        self.app_context = AppContext(
            self.ui_manager,
            file_indexer_service=self.file_indexer_service,
            commands=None,
            current_vault_path=(str(vault_for_service) if vault_for_service != Path(".") else None),
        )
        # ST-16: Broadcast initial vault availability state
        try:
            has_vault = bool(getattr(self.app_context, "current_vault_path", None))
            GlobalSignalBus.vault_state_changed.emit(
                has_vault,
                getattr(self.app_context, "current_vault_path", "") or ""
            )
        except Exception:
            pass
        # Keep references to child top-level note windows (Shift+Click)
        self._child_note_windows = []

        # Connect global navigation signal (FR-3.1) and open-in-new-window (FR-1.3)
        GlobalSignalBus.page_navigation_requested.connect(self.on_page_navigation_requested)
        GlobalSignalBus.page_open_requested.connect(self.on_page_open_requested)
        GlobalSignalBus.back_navigation_requested.connect(self._on_back_navigation_requested)
        GlobalSignalBus.forward_navigation_requested.connect(self._on_forward_navigation_requested)
        
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
        
    def switch_vault(self, new_path: str) -> None:
        """
        ST-03: 切换当前库（供后续 UI 调用的核心 API）
        步骤：
          1) validate_vault_path 校验（禁止程序目录及其子目录）
          2) 停止旧索引服务
          3) ensure_vault_structure(new_path) 自动确保 pages/ 与 assets/
          4) 创建新的 FileIndexerService 并启动
          5) 更新 AppContext（file_indexer_service 与 current_vault_path）
          6) 保存配置（更新 current_vault，若新库不在 vaults 列表则添加）
          7) 若存在 pages/Note A.md 则广播一次 active_page_changed，否则不广播
        """
        try:
            app_dir = Path(__file__).resolve().parent.parent
        except Exception:
            app_dir = Path(".")

        ok, msg = validate_vault_path(new_path, app_dir)
        if not ok:
            logging.error(f"switch_vault: rejected path '{new_path}': {msg}")
            return

        # 规范化并确保结构
        new_root = Path(new_path).expanduser().resolve(strict=False)
        try:
            ensure_vault_structure(new_root)
        except Exception as e:
            logging.error(f"switch_vault: failed to ensure vault structure at {new_root}: {e}")
            return

        # 停止旧索引服务（幂等）
        try:
            if getattr(self, "file_indexer_service", None):
                self.file_indexer_service.stop()
        except Exception as e:
            logging.warning(f"switch_vault: error stopping previous indexer: {e}")

        # 启动新的索引服务
        self.file_indexer_service = FileIndexerService(vault_path=str(new_root))
        self.file_indexer_service.start()

        # 更新 AppContext
        try:
            self.app_context.file_indexer_service = self.file_indexer_service
            self.app_context.current_vault_path = str(new_root)
        except Exception:
            pass

        # 清空导航历史（避免跨库污染）
        try:
            if getattr(self, "nav_history", None):
                self.nav_history.clear()
        except Exception:
            pass

        # 持久化配置（加入 vaults、设置 current_vault）
        try:
            cfg = load_config()
            cfg = add_vault(cfg, str(new_root))
            cfg = set_current_vault(cfg, str(new_root))
            save_config(cfg)
        except Exception as e:
            logging.warning(f"switch_vault: failed to persist config: {e}")

        # ST-16: Broadcast vault state changed -> active
        try:
            GlobalSignalBus.vault_state_changed.emit(True, str(new_root))
        except Exception:
            pass

        # 可选广播默认页面（若存在）
        try:
            default_rel = "pages/Note A.md"
            if (new_root / default_rel).exists():
                GlobalSignalBus.active_page_changed.emit(default_rel)
                try:
                    GlobalSignalBus.panel_context_changed.emit(default_rel)
                except Exception:
                    pass
        except Exception:
            pass
    def on_page_navigation_requested(self, page_title: str):
        """
        ST-05: Resolve a page title/path to a concrete file under the vault, ensure it exists,
        then broadcast active_page_changed with a vault-relative path including .md.
        Compatible with inputs from editor ([[Title]]) and backlink panel (relative paths with extension).
        """
        # ST-16: Block navigation when no active vault
        try:
            if not getattr(self.app_context, "current_vault_path", None):
                print("INFO: no active vault, ignore navigation")
                return
        except Exception:
            print("INFO: no active vault, ignore navigation")
            return
        print(f"INFO: Navigation to page '{page_title}' requested.")
        try:
            abs_path, rel_path = self._resolve_and_ensure_page(page_title)
            # Enqueue index update to reflect potential creation/update
            try:
                if hasattr(self.file_indexer_service, "task_queue"):
                    self.file_indexer_service.task_queue.put({"type": "upsert", "path": str(abs_path)})
            except Exception as e:
                print(f"WARNING: Failed to enqueue upsert for {abs_path}: {e}")
            GlobalSignalBus.active_page_changed.emit(rel_path)
            try:
                GlobalSignalBus.panel_context_changed.emit(rel_path)
            except Exception:
                pass
            # 历史入栈：排除由指针移动（后退/前进）触发的导航
            try:
                if not getattr(self, "_nav_is_pointer_move", False):
                    if getattr(self, "nav_history", None):
                        self.nav_history.push(rel_path)
            except Exception as e:
                logging.warning(f"navigation history push failed for '{rel_path}': {e}")
        except Exception as e:
            print(f"ERROR: Navigation failed for '{page_title}': {e}")

    def _on_back_navigation_requested(self):
        """
        Handle back navigation requests from toolbar/global signal.
        """
        # ST-16: Block navigation when no active vault
        try:
            if not getattr(self.app_context, "current_vault_path", None):
                print("INFO: no active vault, ignore back navigation")
                return
        except Exception:
            print("INFO: no active vault, ignore back navigation")
            return

        dest = None
        try:
            if getattr(self, "nav_history", None):
                dest = self.nav_history.back()
        except Exception as e:
            print(f"WARNING: back navigation failed: {e}")
            dest = None

        if dest:
            self._nav_is_pointer_move = True
            try:
                GlobalSignalBus.page_navigation_requested.emit(dest)
            finally:
                self._nav_is_pointer_move = False

    def _on_forward_navigation_requested(self):
        """
        Handle forward navigation requests from toolbar/global signal.
        """
        # ST-16: Block navigation when no active vault
        try:
            if not getattr(self.app_context, "current_vault_path", None):
                print("INFO: no active vault, ignore forward navigation")
                return
        except Exception:
            print("INFO: no active vault, ignore forward navigation")
            return

        dest = None
        try:
            if getattr(self, "nav_history", None):
                dest = self.nav_history.forward()
        except Exception as e:
            print(f"WARNING: forward navigation failed: {e}")
            dest = None

        if dest:
            self._nav_is_pointer_move = True
            try:
                GlobalSignalBus.page_navigation_requested.emit(dest)
            finally:
                self._nav_is_pointer_move = False

    def on_page_open_requested(self, page_title: str):
        """
        ST-06: Open the resolved note in a new independent top-level editor window (Shift+Click behavior).
        Window title should be the note name (without .md).
        """
        # ST-16: Block open-in-new-window when no active vault
        try:
            if not getattr(self.app_context, "current_vault_path", None):
                print("INFO: no active vault, ignore open-in-new-window")
                return
        except Exception:
            print("INFO: no active vault, ignore open-in-new-window")
            return
        print(f"INFO: Open in new window requested for page '{page_title}'.")
        try:
            abs_path, rel_path = self._resolve_and_ensure_page(page_title)
            # Keep index up-to-date (creation or touch)
            try:
                if hasattr(self.file_indexer_service, "task_queue"):
                    self.file_indexer_service.task_queue.put({"type": "upsert", "path": str(abs_path)})
            except Exception as e:
                print(f"WARNING: Failed to enqueue upsert for {abs_path}: {e}")
            # Open independent window
            self._open_note_window(rel_path)
            try:
                GlobalSignalBus.panel_context_changed.emit(rel_path)
            except Exception:
                pass
        except Exception as e:
            print(f"ERROR: Open-in-new-window failed for '{page_title}': {e}")

    def _open_note_window(self, rel_path: str):
        """
        Create a floating QDockWidget hosting a ReactiveEditor instance and load the target note.
        The dock title is set to the note name (without .md). It can be dragged back to the dock area.
        """
        try:
            from plugins.editable_editor.main import ReactiveEditor
        except Exception as e:
            print(f"ERROR: Failed to import ReactiveEditor for new dock: {e}")
            return

        # Resolve note name for dock title
        try:
            note_name = Path(rel_path).stem
        except Exception:
            note_name = rel_path

        try:
            dock = QDockWidget(note_name, self.main_window)
            dock.setObjectName(f"note_dock::{rel_path}")  # helpful for future restore
            dock.setAllowedAreas(Qt.AllDockWidgetAreas)
            try:
                dock.setAttribute(Qt.WA_DeleteOnClose, True)  # Ensure close() deletes to avoid residual menu entries
            except Exception:
                pass
            # Optional: keep default features (closable, floatable, movable)
        except Exception as e:
            print(f"ERROR: Failed to create QDockWidget: {e}")
            return

        # Create and wire editor
        editor = None
        try:
            editor = ReactiveEditor()
            # Inject app context for services (db path, indexer, etc.)
            try:
                editor.app_context = self.app_context
                if getattr(self.app_context, 'file_indexer_service', None):
                    editor._db_path = str(self.app_context.file_indexer_service.db_path)
            except Exception:
                pass

            # V0.4.6: Configure editor to isolate from global active page and use local navigation
            try:
                editor._follow_global_active_page = False
                editor._handle_navigation_locally = True
            except Exception:
                pass

            # Load file content into this editor instance only (do not broadcast globally)
            try:
                if hasattr(editor, "_load_page_for_self"):
                    editor._load_page_for_self(rel_path)
                else:
                    editor.on_active_page_changed(rel_path)
            except Exception as e:
                print(f"WARNING: Failed to load page in new dock: {e}")

            dock.setWidget(editor)
        except Exception as e:
            print(f"ERROR: Failed to construct editor in dock: {e}")
            try:
                dock.deleteLater()
            except Exception:
                pass
            return

        # Add to main window dock area then float and show
        try:
            self.main_window.addDockWidget(Qt.RightDockWidgetArea, dock)
            try:
                dock.setFloating(True)
            except Exception:
                pass
            try:
                dock.resize(900, 600)
            except Exception:
                pass
            dock.show()
            try:
                GlobalSignalBus.panel_context_changed.emit(rel_path)
            except Exception:
                pass
        except Exception as e:
            print(f"ERROR: Failed to attach dock to main window: {e}")
            try:
                dock.deleteLater()
            except Exception:
                pass
            return

        # Retain reference to prevent GC; cleanup on destroy
        try:
            if not hasattr(self, "_child_note_windows"):
                self._child_note_windows = []
            self._child_note_windows.append(dock)
            dock.destroyed.connect(
                lambda _: self._child_note_windows.remove(dock) if dock in self._child_note_windows else None
            )
        except Exception:
            pass

    def _resolve_and_ensure_page(self, path_or_title: str) -> tuple[str, str]:
        """
        Resolve an incoming title or relative path to an absolute markdown file under the vault and ensure it exists.

        Returns:
            (abs_path_str, rel_path_str_with_ext)
        Rules:
            - If input has '.md' extension OR starts with 'pages/' path: treat as vault-relative.
            - Otherwise (including inputs with path separators but without '.md'), resolve under 'pages/<title>.md'.
            - Always normalize paths and ensure parent directories exist. Create empty file if missing.
        """
        # Base vault path
        base = getattr(self.file_indexer_service, "vault_path", Path("."))
        if not isinstance(base, Path):
            base = Path(str(base or "."))

        txt = str(path_or_title or "").strip()
        if not txt:
            txt = "Untitled"

        p = Path(txt)
        has_ext = p.suffix.lower() == ".md"
        # Normalize first segment for special-case 'pages/' prefix
        first_seg = (p.parts[0].lower() if p.parts else "")

        # Treat as vault-relative when:
        # - It already has .md extension (typical from Backlink Panel), OR
        # - It explicitly starts with 'pages/' (avoid duplicating the prefix)
        if has_ext or first_seg == "pages":
            if not has_ext:
                p = p.with_suffix(".md")
        else:
            # Default bucket for newly created notes: under pages/
            p = Path("pages") / p
            if p.suffix.lower() != ".md":
                p = p.with_suffix(".md")

        abs_path = (base / p).resolve(strict=False)

        # Compute relative path to vault, including extension
        try:
            rel_path = abs_path.relative_to(base)
        except Exception:
            # Fallback to os.path.relpath when outside base (shouldn't happen)
            rel_path = Path(os.path.relpath(str(abs_path), start=str(base)))
        rel_str = rel_path.as_posix()

        # Ensure file exists
        if not abs_path.exists():
            try:
                abs_path.parent.mkdir(parents=True, exist_ok=True)
                with open(abs_path, "w", encoding="utf-8", newline="") as f:
                    f.write("")
                print(f"INFO: Created new page at {abs_path}")
            except Exception as e:
                raise RuntimeError(f"Failed to create page file: {abs_path} ({e})")

        return str(abs_path), rel_str
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
 
        # Broadcast initial active page so panels can request data (only when a vault is active)
        if getattr(self.app_context, "current_vault_path", None):
            GlobalSignalBus.active_page_changed.emit('Note A.md')
            try:
                GlobalSignalBus.panel_context_changed.emit('Note A.md')
            except Exception:
                pass
        else:
            print("INFO: no active vault, skip initial active_page_changed")

        # Enqueue a low-priority GC task (P3-02)
        try:
            self.file_indexer_service.task_queue.put({"type": "garbage_collect_blocks"})
        except Exception:
            pass

        # Request initial completion list after the UI is fully loaded and shown
        GlobalSignalBus.completion_requested.emit('page_link', '')
        
        exit_code = self.qt_app.exec()
        self.file_indexer_service.stop()
        return exit_code
