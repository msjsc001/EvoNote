# plugins/tool_launcher.py
"""
工具启动器（Dock 插件，可移动/可隐藏）

- 以 QDockWidget 形式提供一个“命令面板…”入口按钮（点击即打开 Command Palette）
- 提供“面板”下拉菜单，列出当前主窗口内所有 Dock 面板，支持勾选显示/隐藏
- 在主窗口空白区域（无中央部件处）右键弹出上下文菜单，列出所有 Dock（含本启动器）供快速开关
- 默认停靠在底部，可拖动到任意 Dock 区域或浮动

此插件满足用户对“不要锁死在顶部、可自由安排位置、可像编辑器与反向链一样选择有没有它”的需求。
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Qt, QEvent
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QWidget,
    QDockWidget,
    QHBoxLayout,
    QVBoxLayout,
    QPushButton,
    QToolButton,
    QMenu,
    QListWidget,
    QListWidgetItem,
    QLabel,
    QFileDialog,
    QDialog,
    QAbstractItemView,
)
from pathlib import Path
from typing import Optional

from core.config_manager import (
    load_config,
    save_config,
    add_vault,
    remove_vault,
    set_current_vault,
    validate_vault_path,
    ensure_vault_structure,
)


class ToolLauncherPlugin(QObject):
    # 默认停靠到底部区域
    dock_area = Qt.BottomDockWidgetArea

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.dock_widget: QDockWidget | None = None
        self._vault_manager_window: QDialog | None = None
        # 仅在主窗口（无中央部件的空白处）安装 event filter，用于右键菜单
        try:
            self.app.main_window.installEventFilter(self)
            print("INFO: ToolLauncher: 事件过滤器已安装")
        except Exception as e:
            print(f"WARNING: ToolLauncherPlugin failed to install event filter: {e}")

    # ---- 插件对外暴露：供主程序加载 UI ----
    def get_widget(self) -> QDockWidget:
        if self.dock_widget is not None:
            print("INFO: ToolLauncherPlugin.get_widget reused existing dock")
            return self.dock_widget

        self.dock_widget = QDockWidget("工具栏", self.app.main_window)
        print("INFO: ToolLauncher: Dock 创建")
        # 允许移动、浮动与关闭
        self.dock_widget.setFeatures(
            QDockWidget.DockWidgetMovable
            | QDockWidget.DockWidgetFloatable
            | QDockWidget.DockWidgetClosable
        )
        self.dock_widget.setAllowedAreas(
            Qt.LeftDockWidgetArea
            | Qt.RightDockWidgetArea
            | Qt.BottomDockWidgetArea
            | Qt.TopDockWidgetArea
        )

        root = QWidget(self.dock_widget)
        layout = QHBoxLayout(root)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)

        # 按钮：命令面板…
        btn_palette = QPushButton("命令面板…", root)
        btn_palette.clicked.connect(self._open_command_palette)
        layout.addWidget(btn_palette)

        # 按钮：库管理
        btn_vaults = QPushButton("库管理", root)
        btn_vaults.clicked.connect(self._open_vault_manager)
        layout.addWidget(btn_vaults)

        # 下拉：面板（列出现有 Dock 并可勾选显示/隐藏）
        btn_panels = QToolButton(root)
        btn_panels.setText("面板")
        btn_panels.setPopupMode(QToolButton.InstantPopup)
        btn_panels.setMenu(self._build_panels_menu())
        # aboutToShow 时刷新，确保列表实时
        btn_panels.menu().aboutToShow.connect(lambda: self._refresh_panels_menu(btn_panels.menu()))
        layout.addWidget(btn_panels)

        root.setLayout(layout)
        self.dock_widget.setWidget(root)
        print("INFO: ToolLauncher: Dock 就绪")
        return self.dock_widget

    # ---- 事件过滤：在主窗口空白区域右键弹出菜单 ----
    def eventFilter(self, obj, event):
        if obj is self.app.main_window and event.type() == QEvent.ContextMenu:
            # 仅在主窗口本体（非其子部件）触发，以避免干扰其他插件控件的右键菜单
            # 由于当前没有中央部件，空白区域的右键一般会到达主窗口
            menu = self._build_panels_menu(include_self=True)
            menu.exec(event.globalPos())
            return True
        return super().eventFilter(obj, event)

    # ---- 内部：构建/刷新面板菜单 ----
    def _build_panels_menu(self, include_self: bool = True) -> QMenu:
        menu = QMenu(self.app.main_window)
        self._populate_docks_menu(menu, include_self=include_self)
        return menu

    def _refresh_panels_menu(self, menu: QMenu):
        menu.clear()
        self._populate_docks_menu(menu, include_self=True)

    def _populate_docks_menu(self, menu: QMenu, include_self: bool):
        # 列出所有当前 DockWidget，支持勾选显示/隐藏
        docks = self.app.main_window.findChildren(QDockWidget)
        # 排序稳定：按标题名
        docks_sorted = sorted(
            [d for d in docks if (include_self or d is not self.dock_widget)],
            key=lambda d: (d.windowTitle() or "").lower(),
        )

        if not docks_sorted:
            act = QAction("(无可用面板)", menu)
            act.setEnabled(False)
            menu.addAction(act)
            return

        for dock in docks_sorted:
            title = dock.windowTitle() or "Dock"
            act = QAction(title, menu)
            act.setCheckable(True)
            act.setChecked(dock.isVisible())
            # 使用默认参数闭包绑定当前 dock
            act.toggled.connect(lambda checked, d=dock: d.setVisible(checked))
            menu.addAction(act)

    # ---- 内部：打开命令面板 ----
    def _open_command_palette(self):
        """
        优先通过命令注册表执行 'app.command_palette'，若不存在则回退到 app.open_command_palette()
        """
        # 1) 通过命令注册表（解耦调用）
        try:
            registry = getattr(getattr(self.app, "app_context", None), "commands", None)
            if registry is not None:
                cmd = registry.get_by_id("app.command_palette")
                if cmd is not None:
                    print("INFO: ToolLauncher: executing command 'app.command_palette'")
                    cmd.execute(self.app.app_context)
                    return
        except Exception as e:
            print(f"WARNING: ToolLauncher: registry path failed: {e}")

        # 2) 回退：直接调用核心应用入口
        try:
            print("INFO: ToolLauncher: fallback to app.open_command_palette()")
            self.app.open_command_palette()
        except Exception as e:
            print(f"WARNING: Failed to open Command Palette from ToolLauncher: {e}")

    # ---- 库管理：打开顶层窗口 ----
    def _open_vault_manager(self):
        try:
            if getattr(self, "_vault_manager_window", None) is not None and self._vault_manager_window.isVisible():
                self._vault_manager_window.raise_()
                self._vault_manager_window.activateWindow()
                return
        except Exception:
            pass
        try:
            self._vault_manager_window = VaultManagerWindow(self.app)
            try:
                self._vault_manager_window.destroyed.connect(lambda _: setattr(self, "_vault_manager_window", None))
            except Exception:
                pass
            self._vault_manager_window.show()
        except Exception as e:
            print(f"WARNING: Failed to open VaultManagerWindow: {e}")

    # ---- 可选清理 ----
    def unload(self):
        try:
            self.app.main_window.removeDockWidget(self.dock_widget)
        except Exception:
            pass
        try:
            self.app.main_window.removeEventFilter(self)
        except Exception:
            pass


class VaultManagerWindow(QDialog):
    """
    轻量“库管理”窗口：
    - 左侧：库列表（当前库加标记）
    - 右侧：操作按钮（添加/切换/移除/重建索引）
    - 下方：状态提示区（不弹 QMessageBox）
    """
    def __init__(self, app):
        super().__init__(parent=getattr(app, "main_window", None))
        self.app = app
        self.setWindowTitle("库管理")
        try:
            self.setModal(False)
        except Exception:
            pass
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        try:
            self.resize(680, 420)
        except Exception:
            pass

        root = QVBoxLayout(self)

        # 中部：列表 + 按钮
        center = QWidget(self)
        hbox = QHBoxLayout(center)

        self.list = QListWidget(center)
        try:
            self.list.setSelectionMode(QAbstractItemView.SingleSelection)
        except Exception:
            pass
        hbox.addWidget(self.list, 1)

        btns_container = QWidget(center)
        vbox = QVBoxLayout(btns_container)
        self.btn_add = QPushButton("添加库…", btns_container)
        self.btn_switch = QPushButton("切换到所选库", btns_container)
        self.btn_remove = QPushButton("移除所选库", btns_container)
        self.btn_rebuild = QPushButton("清空并重建索引", btns_container)
        vbox.addWidget(self.btn_add)
        vbox.addWidget(self.btn_switch)
        vbox.addWidget(self.btn_remove)
        vbox.addWidget(self.btn_rebuild)
        vbox.addStretch(1)
        btns_container.setLayout(vbox)
        hbox.addWidget(btns_container, 0)

        center.setLayout(hbox)
        root.addWidget(center)

        # 底部：状态提示
        self.status_label = QLabel("", self)
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)

        # 信号
        self.btn_add.clicked.connect(self.on_add_vault)
        self.btn_switch.clicked.connect(self.on_switch_vault)
        self.btn_remove.clicked.connect(self.on_remove_vault)
        self.btn_rebuild.clicked.connect(self.on_rebuild_index)
        self.list.currentItemChanged.connect(lambda cur, prev: self._update_buttons_state())

        # 初始数据
        self.refresh_list()
        self._update_buttons_state()

    def _canon(self, p) -> str:
        try:
            return Path(str(p)).expanduser().resolve(strict=False).as_posix()
        except Exception:
            return str(p or "").strip()

    def _set_status(self, text: str):
        try:
            self.status_label.setText(text or "")
        except Exception:
            print(f"INFO: VaultManager: {text}")

    def refresh_list(self):
        try:
            cfg = load_config()
        except Exception as e:
            self._set_status(f"读取配置失败：{e}")
            cfg = {"vaults": [], "current_vault": None}
        vaults = cfg.get("vaults", []) or []
        cur = cfg.get("current_vault")
        cur_norm = self._canon(cur) if cur else None

        self.list.clear()
        for v in vaults:
            vn = self._canon(v)
            label = v
            if cur_norm and vn == cur_norm:
                label = f"★ {v} (当前)"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, v)
            self.list.addItem(item)
            if cur_norm and vn == cur_norm:
                try:
                    self.list.setCurrentItem(item)
                except Exception:
                    pass
        self._update_buttons_state()

    def _update_buttons_state(self):
        try:
            cfg = load_config()
        except Exception:
            cfg = {"vaults": [], "current_vault": None}
        cur = cfg.get("current_vault")
        cur_norm = self._canon(cur) if cur else None

        item = self.list.currentItem()
        has_sel = item is not None
        sel_path = item.data(Qt.UserRole) if item else None
        sel_norm = self._canon(sel_path) if sel_path else None
        is_current = (cur_norm is not None and sel_norm == cur_norm)

        try:
            self.btn_switch.setEnabled(has_sel and not is_current)
            self.btn_remove.setEnabled(has_sel and not is_current)
            self.btn_rebuild.setEnabled(cur_norm is not None)
        except Exception:
            pass

    def on_add_vault(self):
        try:
            path = QFileDialog.getExistingDirectory(self, "选择库文件夹")
        except Exception as e:
            self._set_status(f"打开目录选择器失败：{e}")
            return
        if not path:
            self._set_status("已取消。")
            return

        app_dir = Path(__file__).resolve().parent.parent
        ok, msg = validate_vault_path(path, app_dir)
        if not ok:
            self._set_status(msg)
            return
        try:
            ensure_vault_structure(Path(path))
        except Exception as e:
            self._set_status(f"确保库结构失败：{e}")
            return
        try:
            cfg = load_config()
            before = {self._canon(x) for x in (cfg.get("vaults") or [])}
            cfg2 = add_vault(cfg, path)
            save_config(cfg2)
            after = {self._canon(x) for x in (cfg2.get("vaults") or [])}
            self.refresh_list()
            added = self._canon(path) in after and self._canon(path) not in before
            self._set_status("已添加库并保存到配置。" if added else "库已存在，已刷新列表。")
        except Exception as e:
            self._set_status(f"保存配置失败：{e}")

    def on_switch_vault(self):
        item = self.list.currentItem()
        if not item:
            self._set_status("请先选择一个库。")
            return
        path = item.data(Qt.UserRole)
        if not path:
            self._set_status("无法解析所选库路径。")
            return

        app_dir = Path(__file__).resolve().parent.parent
        ok, msg = validate_vault_path(path, app_dir)
        if not ok:
            self._set_status(msg)
            return
        try:
            self.app.switch_vault(path)
            self.refresh_list()
            self._set_status(f"已切换到库：{path}")
        except Exception as e:
            self._set_status(f"切换库失败：{e}")

    def on_remove_vault(self):
        item = self.list.currentItem()
        if not item:
            self._set_status("请先选择一个库。")
            return
        path = item.data(Qt.UserRole)
        try:
            cfg = load_config()
        except Exception as e:
            self._set_status(f"读取配置失败：{e}")
            return
        cur = cfg.get("current_vault")
        if cur and self._canon(cur) == self._canon(path):
            self._set_status("请先切换到其他库后再移除当前库。")
            return
        try:
            cfg2 = remove_vault(cfg, path)
            save_config(cfg2)
            self.refresh_list()
            self._set_status("已从配置移除所选库。")
        except Exception as e:
            self._set_status(f"移除失败：{e}")

    def on_rebuild_index(self):
        try:
            cfg = load_config()
        except Exception as e:
            self._set_status(f"读取配置失败：{e}")
            return
        cur = cfg.get("current_vault")
        if not cur:
            self._set_status("当前没有已选择的库，无法重建索引。")
            return
        try:
            self.btn_rebuild.setEnabled(False)
            try:
                self.setCursor(Qt.BusyCursor)
            except Exception:
                pass
            self._set_status("正在重建索引，请稍候…")
            self.app.file_indexer_service.rebuild_index()
            self._set_status("索引已重建完成。")
        except Exception as e:
            self._set_status(f"重建索引失败：{e}")
        finally:
            try:
                self.unsetCursor()
            except Exception:
                pass
            self.btn_rebuild.setEnabled(True)

def create_plugin(app):
    return ToolLauncherPlugin(app)