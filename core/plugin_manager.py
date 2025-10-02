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
        self.loaded_plugins: Dict[str, object] = {}

    def discover_and_load_plugins(self, app):
        """
        扫描插件目录，并安全地加载所有发现的有效插件。
        加载顺序规则：
          1) command_service 优先加载（确保命令注册器就绪）
          2) *_service.py（后台服务）
          3) 其他插件（UI等）
        """
        if not os.path.isdir(self.plugin_folder):
            print(f"警告：插件目录 '{self.plugin_folder}' 不存在。")
            return

        candidates = []
        for item in os.listdir(self.plugin_folder):
            if item.startswith('_') or item == '.gitkeep':
                continue

            path = os.path.join(self.plugin_folder, item)

            if os.path.isdir(path):
                # 目录插件
                module_name = f"{self.plugin_folder}.{item}.main"
                candidates.append((module_name, item))
            elif item.endswith('.py'):
                # 文件插件
                module_name = f"{self.plugin_folder}.{item.replace('.py', '')}"
                candidates.append((module_name, item))

        def _priority(entry: tuple[str, str]) -> int:
            _, plugin_id = entry
            # 文件场景：plugin_id 为文件名；目录场景：为目录名
            name = plugin_id
            if name in ("command_service.py", "command_service"):
                return 0
            if name.endswith("_service.py") or name.endswith("_service"):
                return 1
            return 2

        for module_name, plugin_id in sorted(candidates, key=_priority):
            self.load_plugin(module_name, app, plugin_id)

    def load_plugin(self, module_name: str, app, plugin_id: str):
        try:
            print(f"INFO: PluginManager loading module '{module_name}' (id='{plugin_id}')")
            plugin_module = importlib.import_module(module_name)
            if hasattr(plugin_module, 'create_plugin'):
                plugin_instance = plugin_module.create_plugin(app)
                
                # 使用插件ID作为键，确保唯一性
                if plugin_id in self.loaded_plugins:
                    print(f"错误：插件ID冲突 '{plugin_id}'。跳过加载。")
                    return
                    
                print(f"成功加载插件：'{plugin_id}'")
                self.loaded_plugins[plugin_id] = plugin_instance
            else:
                print(f"警告：在 '{module_name}' 中未找到 'create_plugin' 函数。")

        except Exception as e:
            print(f"错误：加载插件 '{module_name}' 失败。异常：{type(e).__name__}: {e}")
            print("="*20 + " 错误详情 " + "="*20)
            try:
                print(traceback.format_exc())
            except Exception as _e:
                print(f"WARNING: traceback.format_exc failed: {type(_e).__name__}: {_e}")
            print("="*52)

    def get_plugin(self, name: str) -> EditorPluginInterface | None:
        """通过名称获取已加载的插件实例。"""
        return self.loaded_plugins.get(name)

    def get_all_plugins(self) -> List[EditorPluginInterface]:
        """获取所有已成功加载的插件实例列表。"""
        return list(self.loaded_plugins.values())
