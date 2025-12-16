# plugins/editor_plugin_interface.py
from abc import ABC, abstractmethod
from PySide6.QtWidgets import QWidget

class EditorPluginInterface(ABC):
    """
    所有编辑器插件必须实现的抽象基类接口。
    它定义了插件与主应用程序交互的契约。
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """返回插件的唯一名称。"""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """返回对插件功能的简短描述。"""
        pass

    @abstractmethod
    def get_widget(self) -> QWidget:
        """
        创建并返回此插件的主UI组件（QWidget）。
        主应用程序将把这个小部件集成到其布局中。
        """
        pass

    def on_load(self):
        """
        [可选] 插件加载钩子
        当插件被 PluginManager 加载并初始化后立即调用。
        用于：
        - 订阅 GlobalSignalBus 信号
        - 初始化后台资源
        """
        pass

    def on_unload(self):
        """
        [可选] 插件卸载钩子
        当插件被禁用或应用程序关闭前调用。
        必须：
        - 断开所有已连接的信号 (disconnect)
        - 停止所有后台线程/定时器
        - 清理占用的资源
        注意：get_widget 返回的组件通常由 UIManager 移除，但插件内部引用需自行清理。
        """
        pass