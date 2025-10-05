# plugins/navigation_toolbar.py
"""
导航工具栏插件（A4）
- 在主窗口添加一个可停靠的 QToolBar，包含“后退”“前进”两个按钮（纯文本）。
- 点击按钮时分别发出全局信号：GlobalSignalBus.back_navigation_requested 与 GlobalSignalBus.forward_navigation_requested。
- 订阅 GlobalSignalBus.nav_history_state_changed，根据 can_back/can_forward 使能或禁用按钮。
- 工具栏允许停靠到顶部或左侧；可移动、可浮动；不做位置/排序持久化。
- 插件在 create_plugin 时即完成工具栏创建与注入：app.main_window.addToolBar(toolbar)。
- 所有 UI 操作与信号连接均使用 try/except 包裹，失败仅打印 WARNING，不抛出异常。
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QObject, Slot, QEvent, QPoint
from PySide6.QtWidgets import QToolBar, QAction, QToolButton

from core.signals import GlobalSignalBus
from core.config_manager import load_config, save_config, get_toolbar_actions, set_toolbar_actions


class NavigationToolbarPlugin(QObject):
    """
    基础导航工具栏插件：职责单一，仅发出/响应全局导航相关信号。
    """

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.toolbar: QToolBar | None = None
        self.back_action: QAction | None = None
        self.forward_action: QAction | None = None

        self._init_toolbar()
        self._subscribe_signals()

    # ---- 初始化 UI ----
    def _init_toolbar(self) -> None:
        # 验证主窗口
        try:
            mw = getattr(self.app, "main_window", None)
            if mw is None or not hasattr(mw, "addToolBar"):
                print("WARNING: NavigationToolbarPlugin: main_window 不可用或不支持 addToolBar；插件未启用。")
                return
        except Exception as e:
            print(f"WARNING: NavigationToolbarPlugin: 检查 main_window 失败：{e}")
            return

        # 创建工具栏
        try:
            self.toolbar = QToolBar("导航", mw)
            self.toolbar.setMovable(True)
            self.toolbar.setFloatable(True)
            self.toolbar.setAllowedAreas(Qt.TopToolBarArea | Qt.LeftToolBarArea)
            self.toolbar.setToolButtonStyle(Qt.ToolButtonTextOnly)
        except Exception as e:
            print(f"WARNING: NavigationToolbarPlugin: 创建或配置 QToolBar 失败：{e}")
            self.toolbar = None
            return

        # 创建两个动作（初始禁用，等待历史服务广播后更新）
        try:
            self.back_action = QAction("后退", self.toolbar)
            self.back_action.setEnabled(False)
            self.forward_action = QAction("前进", self.toolbar)
            self.forward_action.setEnabled(False)
        except Exception as e:
            print(f"WARNING: NavigationToolbarPlugin: 创建 QAction 失败：{e}")
            self.back_action = None
            self.forward_action = None

        # 连接动作触发 &#45;> 发出全局信号
        try:
            if self.back_action is not None:
                self.back_action.triggered.connect(self._on_back_triggered)
            if self.forward_action is not None:
                self.forward_action.triggered.connect(self._on_forward_triggered)
        except Exception as e:
            print(f"WARNING: NavigationToolbarPlugin: 连接 QAction.triggered 失败：{e}")

        # 添加到工具栏（按配置顺序）
        try:
            order = ["back", "forward"]
            try:
                cfg = load_config()
                order = get_toolbar_actions(cfg) or ["back", "forward"]
            except Exception:
                order = ["back", "forward"]
            action_map = {"back": self.back_action, "forward": self.forward_action}
            for key in order:
                act = action_map.get(key)
                if act is not None:
                    self.toolbar.addAction(act)
        except Exception as e:
            print(f"WARNING: NavigationToolbarPlugin: 向 QToolBar 添加动作失败：{e}")

        # 注入到主窗口（默认顶部）
        try:
            mw.addToolBar(self.toolbar)
            print("INFO: NavigationToolbar: 已添加到主窗口。")
        except Exception as e:
            print(f"WARNING: NavigationToolbarPlugin: 调用 main_window.addToolBar 失败：{e}")
        # 安装拖拽重排过滤器（简单DND，仅水平）
        try:
            self._install_dnd_filter()
        except Exception as e:
            print(f"WARNING: NavigationToolbarPlugin: 安装拖拽过滤器失败：{e}")

    # ---- 订阅全局信号 ----
    def _subscribe_signals(self) -> None:
        try:
            GlobalSignalBus.nav_history_state_changed.connect(self._on_nav_state_changed)
        except Exception as e:
            print(f"WARNING: NavigationToolbarPlugin: 订阅 nav_history_state_changed 失败：{e}")

    # ---- 槽：按钮触发 -> 发出全局请求 ----
    @Slot(bool)
    def _on_back_triggered(self, checked: bool = False) -> None:
        try:
            GlobalSignalBus.back_navigation_requested.emit()
        except Exception as e:
            print(f"WARNING: NavigationToolbarPlugin: 发送 back_navigation_requested 失败：{e}")

    @Slot(bool)
    def _on_forward_triggered(self, checked: bool = False) -> None:
        try:
            GlobalSignalBus.forward_navigation_requested.emit()
        except Exception as e:
            print(f"WARNING: NavigationToolbarPlugin: 发送 forward_navigation_requested 失败：{e}")

    # ---- 槽：历史状态变化 -> 更新按钮使能 ----
    @Slot(bool, bool, str)
    def _on_nav_state_changed(self, can_back: bool, can_forward: bool, current_page: str) -> None:
        try:
            if self.back_action is not None:
                self.back_action.setEnabled(bool(can_back))
        except Exception as e:
            print(f"WARNING: NavigationToolbarPlugin: 更新后退按钮状态失败：{e}")
        try:
            if self.forward_action is not None:
                self.forward_action.setEnabled(bool(can_forward))
        except Exception as e:
            print(f"WARNING: NavigationToolbarPlugin: 更新前进按钮状态失败：{e}")
    # ---- 可选：插件卸载清理 ----
    def unload(self) -> None:
        # 断开信号
        try:
            GlobalSignalBus.nav_history_state_changed.disconnect(self._on_nav_state_changed)
        except Exception:
            pass
        # 移除工具栏
        try:
            mw = getattr(self.app, "main_window", None)
            if mw is not None and self.toolbar is not None and hasattr(mw, "removeToolBar"):
                mw.removeToolBar(self.toolbar)
        except Exception:
            pass
        # 移除事件过滤器
        try:
            if hasattr(self, "_dnd_filter"):
                if self.toolbar is not None:
                    try:
                        self.toolbar.removeEventFilter(self._dnd_filter)
                    except Exception:
                        pass
                    for act in self.toolbar.actions():
                        try:
                            w = self.toolbar.widgetForAction(act)
                            if w is not None:
                                w.removeEventFilter(self._dnd_filter)
                        except Exception:
                            pass
        except Exception:
            pass

    # ---- DnD 支持：安装事件过滤器 ----
    def _install_dnd_filter(self) -> None:
        try:
            if self.toolbar is None:
                return
            self._dnd_filter = _ToolbarDnDFilter(self)
            # 监听工具栏与其内部按钮的鼠标事件
            self.toolbar.installEventFilter(self._dnd_filter)
            for act in self.toolbar.actions():
                try:
                    w = self.toolbar.widgetForAction(act)
                    if w is not None:
                        w.installEventFilter(self._dnd_filter)
                except Exception:
                    pass
        except Exception as e:
            print(f"WARNING: NavigationToolbarPlugin: 安装拖拽过滤器失败：{e}")

    # ---- DnD 辅助：索引与持久化 ----
    def _action_to_key(self, action: QAction) -> str | None:
        try:
            if action is self.back_action:
                return "back"
            if action is self.forward_action:
                return "forward"
        except Exception:
            pass
        return None

    def _current_order_keys(self) -> list[str]:
        keys: list[str] = []
        try:
            if self.toolbar is None:
                return ["back", "forward"]
            for act in self.toolbar.actions():
                k = self._action_to_key(act)
                if k and k not in keys:
                    keys.append(k)
            if not keys:
                keys = ["back", "forward"]
        except Exception:
            keys = ["back", "forward"]
        return keys

    def _persist_toolbar_order(self) -> None:
        try:
            cfg = load_config()
            order = self._current_order_keys()
            cfg = set_toolbar_actions(cfg, order)
            save_config(cfg)
        except Exception as e:
            print(f"WARNING: NavigationToolbarPlugin: 持久化工具栏顺序失败：{e}")

    def _action_index_at(self, pos: QPoint) -> int | None:
        try:
            if self.toolbar is None:
                return None
            acts = self.toolbar.actions()
            for i, act in enumerate(acts):
                w = self.toolbar.widgetForAction(act)
                if w is None:
                    continue
                try:
                    if w.isVisible() and w.geometry().contains(pos):
                        return i
                except Exception:
                    continue
        except Exception:
            return None
        return None

    def _compute_drop_index(self, pos: QPoint) -> int | None:
        # 仅按水平坐标推断目标位置；未找到则返回 None
        try:
            if self.toolbar is None:
                return None
            acts = self.toolbar.actions()
            centers: list[tuple[int, int]] = []
            for i, act in enumerate(acts):
                w = self.toolbar.widgetForAction(act)
                if w is None:
                    continue
                r = w.geometry()
                centers.append((i, r.center().x()))
            if not centers:
                return None
            for i, cx in centers:
                if pos.x() <= cx:
                    return i
            return len(centers)  # 放到末尾
        except Exception:
            return None

    def _reorder_actions(self, start_index: int, drop_index: int) -> None:
        try:
            if self.toolbar is None:
                return
            acts = list(self.toolbar.actions())
            if not (0 <= start_index < len(acts)):
                return
            act = acts[start_index]
            remaining = [a for a in acts if a is not act]
            # 计算移除后的插入索引
            new_index = drop_index
            if drop_index > start_index:
                new_index = drop_index - 1
            if new_index < 0:
                new_index = 0
            if new_index > len(remaining):
                new_index = len(remaining)
            # 执行重排
            self.toolbar.removeAction(act)
            anchor = remaining[new_index] if new_index < len(remaining) else None
            if anchor is None:
                self.toolbar.addAction(act)
            else:
                self.toolbar.insertAction(anchor, act)
        except Exception as e:
            print(f"WARNING: NavigationToolbarPlugin: 重排动作失败：{e}")

# ---- 简易水平拖拽事件过滤器 ----
class _ToolbarDnDFilter(QObject):
    """
    捕捉鼠标按下/移动/释放，在水平拖动时根据几何中心计算目标插入位置，释放时进行 remove+insert 重排并持久化。
    - 仅支持水平拖拽；若无法定位目标位置则不重排。
    - 拖动中吞掉事件，避免误触发 QAction.triggered。
    """
    def __init__(self, plugin: NavigationToolbarPlugin) -> None:
        super().__init__()
        self._plugin = plugin
        self._start_idx: int | None = None
        self._start_pos: QPoint | None = None
        self._dragging: bool = False

    def eventFilter(self, obj, event):
        try:
            tb = getattr(self._plugin, "toolbar", None)
            if tb is None:
                return False
            t = event.type()
            if t == QEvent.MouseButtonPress:
                pos = self._map_to_toolbar(obj, event, tb)
                if pos is None:
                    return False
                self._start_idx = self._plugin._action_index_at(pos)
                self._start_pos = pos
                self._dragging = False
                return False
            elif t == QEvent.MouseMove:
                if self._start_pos is None:
                    return False
                pos = self._map_to_toolbar(obj, event, tb)
                if pos is None:
                    return False
                if abs(pos.x() - self._start_pos.x()) > 6:
                    self._dragging = True
                    return True  # 拖拽中：吞掉事件，避免触发点击
                return False
            elif t == QEvent.MouseButtonRelease:
                start_idx = self._start_idx
                self._start_idx = None
                pos = self._map_to_toolbar(obj, event, tb)
                if not self._dragging:
                    self._start_pos = None
                    return False  # 普通点击，交由默认处理
                self._dragging = False
                self._start_pos = None
                if start_idx is None:
                    return True
                drop_idx = self._plugin._compute_drop_index(pos) if pos is not None else None
                if drop_idx is None or drop_idx == start_idx:
                    return True
                self._plugin._reorder_actions(start_idx, drop_idx)
                self._plugin._persist_toolbar_order()
                return True
        except Exception:
            return False
        return False

    def _map_to_toolbar(self, obj, event, toolbar) -> QPoint | None:
        try:
            if hasattr(event, "position"):
                pf = event.position()
                local = QPoint(int(pf.x()), int(pf.y()))
            elif hasattr(event, "pos"):
                p = event.pos()
                local = QPoint(int(p.x()), int(p.y()))
            else:
                return None
            if obj is toolbar:
                return local
            try:
                return obj.mapTo(toolbar, local)
            except Exception:
                return None
        except Exception:
            return None

def create_plugin(app):
    """
    插件入口：创建并返回插件实例。构造过程中即完成工具栏注入。
    """
    return NavigationToolbarPlugin(app)