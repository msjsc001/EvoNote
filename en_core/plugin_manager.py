import importlib.util
import logging
from pathlib import Path

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class PluginManager:
    """
    Manages the discovery, loading, and registration of plugins.
    """
    def __init__(self, app_context, plugin_folder="plugins"):
        """
        Initializes the PluginManager.
        Args:
            app_context: The application context to be passed to plugins.
            plugin_folder (str): The name of the folder to scan for plugins.
        """
        self.app_context = app_context
        self.plugins_path = Path(plugin_folder)
        if not self.plugins_path.is_dir():
            logging.warning(f"Plugin folder '{self.plugins_path}' not found. Creating it.")
            self.plugins_path.mkdir(parents=True, exist_ok=True)

    def discover_and_load_plugins(self):
        """
        Scans the plugin folder, loads each valid plugin, and calls its
        register function.
        """
        logging.info(f"Scanning for plugins in '{self.plugins_path.resolve()}'...")
        
        for file_path in self.plugins_path.glob("*.py"):
            if file_path.name.startswith("_"):
                continue  # Skip files like __init__.py

            plugin_name = file_path.stem
            try:
                spec = importlib.util.spec_from_file_location(plugin_name, file_path)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    
                    if hasattr(module, "register"):
                        logging.info(f"Loading plugin: {plugin_name}")
                        module.register(self.app_context)
                    else:
                        logging.warning(f"Plugin '{plugin_name}' does not have a 'register' function. Skipping.")
                else:
                    logging.error(f"Could not create spec for plugin '{plugin_name}'.")

            except Exception as e:
                # Per NFR-2, catch exceptions and continue loading other plugins.
                logging.error(f"Failed to load plugin '{plugin_name}': {e}", exc_info=True)
        
        logging.info("Plugin loading complete.")
