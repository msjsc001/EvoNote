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
    QPushButton,
    QToolButton,
    QMenu,
)


class ToolLauncherPlugin(QObject):
    # 默认停靠到底部区域
    dock_area = Qt.BottomDockWidgetArea

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.dock_widget: QDockWidget | None = None
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

        self.dock_widget = QDockWidget("工具启动器", self.app.main_window)
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


def create_plugin(app):
    return ToolLauncherPlugin(app)