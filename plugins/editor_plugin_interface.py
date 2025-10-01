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