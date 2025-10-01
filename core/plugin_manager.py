# core/plugin_manager.py
import os
import importlib
import inspect
import traceback
from typing import Dict, List, Type
from plugins.editor_plugin_interface import EditorPluginInterface

class PluginManager:
    def __init__(self, plugin_folder: str = 'plugins'):
        self.plugin_folder = plugin_folder
        self.loaded_plugins: Dict[str, EditorPluginInterface] = {}

    def discover_and_load_plugins(self):
        """
        扫描插件目录，并安全地加载所有发现的有效插件。
        """
        if not os.path.isdir(self.plugin_folder):
            print(f"警告：插件目录 '{self.plugin_folder}' 不存在。")
            return

        for plugin_name in os.listdir(self.plugin_folder):
            if plugin_name.startswith('_'):
                continue
            plugin_path = os.path.join(self.plugin_folder, plugin_name)
            # 我们只关心目录形式的插件
            if os.path.isdir(plugin_path):
                try:
                    # 动态构建模块导入路径，例如：plugins.editor_placeholder.main
                    module_name = f"{self.plugin_folder}.{plugin_name}.main"
                    plugin_module = importlib.import_module(module_name)

                    # 在模块中查找实现了接口的类
                    for attribute_name in dir(plugin_module):
                        attribute = getattr(plugin_module, attribute_name)
                        if (inspect.isclass(attribute) and
                                issubclass(attribute, EditorPluginInterface) and
                                attribute is not EditorPluginInterface):
                            
                            # 实例化插件
                            plugin_instance = attribute()
                            
                            # 检查插件名称是否冲突
                            if plugin_instance.name in self.loaded_plugins:
                                print(f"错误：插件名称冲突 '{plugin_instance.name}'。跳过加载。")
                                continue

                            print(f"成功加载插件：'{plugin_instance.name}'")
                            self.loaded_plugins[plugin_instance.name] = plugin_instance
                            break # 每个模块只加载第一个找到的插件类
                
                except Exception as e:
                    print(f"错误：加载插件 '{plugin_name}' 失败。")
                    print("="*20 + " 错误详情 " + "="*20)
                    traceback.print_exc()
                    print("="*52)
                    # 关键点：捕获异常后继续加载下一个插件
                    continue

    def get_plugin(self, name: str) -> EditorPluginInterface | None:
        """通过名称获取已加载的插件实例。"""
        return self.loaded_plugins.get(name)

    def get_all_plugins(self) -> List[EditorPluginInterface]:
        """获取所有已成功加载的插件实例列表。"""
        return list(self.loaded_plugins.values())
