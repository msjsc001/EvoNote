# core/plugin_manager.py
import os
import importlib
import traceback
import sys
from typing import Dict, List, Optional
from plugins.editor_plugin_interface import EditorPluginInterface
from core.signals import GlobalSignalBus
from core.config_manager import load_plugin_config

class PluginManager:
    """
    Manages the lifecycle of plugins: discovery, loading, unloading, and reloading.
    V0.4.7 Upgrade:
    - Supports plugin_config.json for enabled/disabled state.
    - Supports Safe Mode (skips non-core plugins).
    - Supports dynamic hot-loading/unloading via GlobalSignalBus.
    """
    def __init__(self, plugin_folder: str = 'plugins', safe_mode: bool = False):
        self.plugin_folder = plugin_folder
        self.safe_mode = safe_mode
        self.loaded_plugins: Dict[str, EditorPluginInterface] = {}
        
        # Connect to lifecycle signals
        GlobalSignalBus.plugin_enable_requested.connect(self.enable_plugin)
        GlobalSignalBus.plugin_disable_requested.connect(self.disable_plugin)

    def discover_and_load_plugins(self, app):
        """
        Scans plugin folder and loads plugins based on configuration and Safe Mode.
        """
        self.app_ref = app # Store reference for hot-loading
        
        if not os.path.isdir(self.plugin_folder):
            print(f"WARNING: Plugin folder '{self.plugin_folder}' not found.")
            return

        # Load config
        plugin_cfg = load_plugin_config()
        disabled_plugins = set(plugin_cfg.get("disabled_plugins", []))
        
        candidates = []
        for item in os.listdir(self.plugin_folder):
            if item.startswith('_') or item == '.gitkeep':
                continue

            path = os.path.join(self.plugin_folder, item)
            plugin_id = item
            
            # Determine module name
            if os.path.isdir(path):
                # Directory plugin: plugins.my_plugin.main
                module_name = f"{self.plugin_folder}.{item}.main"
            elif item.endswith('.py'):
                # File plugin: plugins.my_plugin
                plugin_id = item
                module_name = f"{self.plugin_folder}.{item.replace('.py', '')}"
            else:
                continue

            # Safe Mode Check
            # Allow command_service always
            is_core = plugin_id in ["command_service.py", "command_service"]
            
            if self.safe_mode and not is_core:
                print(f"INFO: [Safe Mode] Skipping '{plugin_id}'")
                continue

            # Config Check
            if plugin_id in disabled_plugins:
                print(f"INFO: Plugin '{plugin_id}' is disabled in config. Skipping.")
                continue

            candidates.append((module_name, plugin_id))

        # Priority Sort
        def _priority(entry: tuple[str, str]) -> int:
            _, pid = entry
            if pid in ("command_service.py", "command_service"): return 0
            if pid.endswith("_service.py") or pid.endswith("_service"): return 1
            return 2

        for module_name, plugin_id in sorted(candidates, key=_priority):
            self.load_plugin(module_name, app, plugin_id)

    def load_plugin(self, module_name: str, app, plugin_id: str):
        if plugin_id in self.loaded_plugins:
            print(f"WARNING: Plugin '{plugin_id}' already loaded.")
            return

        try:
            print(f"INFO: Loading plugin '{plugin_id}' ({module_name})...")
            
            # Dynamic Import
            if module_name in sys.modules:
                 plugin_module = importlib.reload(sys.modules[module_name])
            else:
                 plugin_module = importlib.import_module(module_name)

            if hasattr(plugin_module, 'create_plugin'):
                plugin_instance = plugin_module.create_plugin(app)
                
                # Lifecycle Hook
                if hasattr(plugin_instance, 'on_load'):
                    try:
                        plugin_instance.on_load()
                    except Exception as e:
                        print(f"ERROR: Plugin '{plugin_id}' on_load failed: {e}")
                        GlobalSignalBus.plugin_error.emit(plugin_id, f"on_load failed: {e}")

                self.loaded_plugins[plugin_id] = plugin_instance
                print(f"SUCCESS: Loaded '{plugin_id}'")
                
                GlobalSignalBus.plugin_state_changed.emit(plugin_id, True)
            else:
                print(f"WARNING: No 'create_plugin' in '{module_name}'")

        except Exception as e:
            err_msg = f"Failed to load plugin '{plugin_id}': {e}"
            print(f"ERROR: {err_msg}")
            traceback.print_exc()
            GlobalSignalBus.plugin_error.emit(plugin_id, str(e))

    def unload_plugin(self, plugin_id: str):
        """
        Soft unload a plugin:
        1. Call on_unload()
        2. Remove widget from UI (if accessible)
        3. Remove from loaded_plugins
        """
        plugin = self.loaded_plugins.get(plugin_id)
        if not plugin:
            print(f"WARNING: Cannot unload '{plugin_id}', not loaded.")
            return

        print(f"INFO: Unloading plugin '{plugin_id}'...")
        
        # 1. Lifecycle Hook
        if hasattr(plugin, 'on_unload'):
            try:
                plugin.on_unload()
            except Exception as e:
                print(f"ERROR: Plugin '{plugin_id}' on_unload failed: {e}")

        # 2. UI Removal
        # Try to find if this plugin added a widget. 
        # Since PluginInterface has get_widget, we can call it (if idempotent) 
        # or we hope the plugin stored its widget.
        # Ideally, we should have stored the widget reference when loading, but Interface doesn't mandate it.
        # We'll re-call get_widget() assuming it returns the SAME instance or the plugin manages it.
        # CAUTION: If get_widget creates a NEW one, this won't help remove the OLD one.
        # Assumption: plugin.get_widget() returns a persistent reference or we rely on on_unload to trigger cleanup.
        # BUT, for the "God View" goal, we want the manager to be able to kill it.
        # Let's try to pass the widget to remove_widget.
        if hasattr(plugin, 'get_widget'):
            try:
                w = plugin.get_widget()
                if w and hasattr(self, 'app_ref') and hasattr(self.app_ref, 'ui_manager'):
                    self.app_ref.ui_manager.remove_widget(w)
                    print(f"INFO: Removed widget for '{plugin_id}'")
            except Exception as e:
                print(f"WARNING: Failed to remove widget for '{plugin_id}': {e}")

        # 3. Remove reference
        del self.loaded_plugins[plugin_id]
        print(f"SUCCESS: Unloaded '{plugin_id}'")
        GlobalSignalBus.plugin_state_changed.emit(plugin_id, False)

    # ---- Signal Slots ----
    
    def enable_plugin(self, plugin_id: str):
        """
        Slot to handle plugin enable request.
        """
        if not hasattr(self, 'app_ref'):
            print("ERROR: PluginManager has no app reference. Cannot enable plugin.")
            return
            
        # Scan folder to find the matching item
        target_item = None
        for item in os.listdir(self.plugin_folder):
            if item == plugin_id or item == f"{plugin_id}.py":
                target_item = item
                break
        
        if not target_item:
            print(f"ERROR: Plugin source for '{plugin_id}' not found.")
            return

        path = os.path.join(self.plugin_folder, target_item)
        if os.path.isdir(path):
             module_name = f"{self.plugin_folder}.{target_item}.main"
        else:
             module_name = f"{self.plugin_folder}.{target_item.replace('.py', '')}"
             
        self.load_plugin(module_name, self.app_ref, plugin_id)

    def disable_plugin(self, plugin_id: str):
        """Slot to handle plugin disable request."""
        self.unload_plugin(plugin_id)

    def get_plugin(self, name: str) -> Optional[EditorPluginInterface]:
        return self.loaded_plugins.get(name)

    def get_all_plugins(self) -> List[EditorPluginInterface]:
        return list(self.loaded_plugins.values())
