
# plugins/plugin_manager/ui.py
import os
import shutil
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QScrollArea, QFrame, 
    QLabel, QPushButton, QHBoxLayout, QCheckBox, 
    QGridLayout, QFileDialog, QMessageBox, QStyle
)
from PySide6.QtCore import Qt, QMimeData, QSize
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QIcon, QFont

from core.signals import GlobalSignalBus
from core.config_manager import load_plugin_config

# Plugin Metadata Registry: Bilingual names and descriptions
PLUGIN_METADATA = {
    "about_command.py": {
        "name_cn": "关于",
        "name_en": "About",
        "desc_cn": "显示应用程序信息",
        "desc_en": "Show app information"
    },
    "backlink_panel.py": {
        "name_cn": "反向链接面板",
        "name_en": "Backlink Panel",
        "desc_cn": "显示引用当前笔记的所有链接",
        "desc_en": "Shows all notes linking to current note"
    },
    "backlink_service.py": {
        "name_cn": "反向链接服务",
        "name_en": "Backlink Service",
        "desc_cn": "后台计算反向链接",
        "desc_en": "Backend for backlink computation"
    },
    "command_palette_command.py": {
        "name_cn": "命令面板",
        "name_en": "Command Palette",
        "desc_cn": "快捷键命令搜索",
        "desc_en": "Quick command search (Ctrl+Shift+P)"
    },
    "command_service.py": {
        "name_cn": "命令服务",
        "name_en": "Command Service",
        "desc_cn": "命令注册与执行系统",
        "desc_en": "Command registration system"
    },
    "completion_service.py": {
        "name_cn": "自动补全服务",
        "name_en": "Completion Service",
        "desc_cn": "[[链接]] 和 {{内容块}} 自动补全",
        "desc_en": "Autocomplete for [[links]] and {{blocks}}"
    },
    "editable_editor": {
        "name_cn": "富文本编辑器",
        "name_en": "Rich Editor",
        "desc_cn": "核心编辑器，支持实时预览",
        "desc_en": "Core editor with live preview"
    },
    "file_browser_plugin.py": {
        "name_cn": "文件浏览器",
        "name_en": "File Browser",
        "desc_cn": "左侧文件树导航",
        "desc_en": "Left sidebar file tree navigation"
    },
    "global_search": {
        "name_cn": "全局搜索",
        "name_en": "Global Search",
        "desc_cn": "全库全文搜索",
        "desc_en": "Full-text search across vault"
    },
    "navigation_toolbar.py": {
        "name_cn": "导航工具栏",
        "name_en": "Navigation Toolbar",
        "desc_cn": "后退/前进导航历史",
        "desc_en": "Back/Forward navigation history"
    },
    "new_note_command.py": {
        "name_cn": "新建笔记",
        "name_en": "New Note",
        "desc_cn": "快速创建新笔记",
        "desc_en": "Quickly create new notes"
    },
    "plugin_manager": {
        "name_cn": "插件管理器",
        "name_en": "Plugin Manager",
        "desc_cn": "管理插件的启用/禁用",
        "desc_en": "Enable/disable plugins"
    },
    "tool_launcher.py": {
        "name_cn": "工具启动器",
        "name_en": "Tool Launcher",
        "desc_cn": "快速访问常用工具",
        "desc_en": "Quick access to common tools"
    },
}

def get_plugin_display_info(plugin_id: str) -> tuple:
    """Returns (display_name, description) for a plugin."""
    meta = PLUGIN_METADATA.get(plugin_id, {})
    name_cn = meta.get("name_cn", plugin_id)
    name_en = meta.get("name_en", plugin_id)
    desc_cn = meta.get("desc_cn", "")
    desc_en = meta.get("desc_en", "")
    
    # Format: "中文名 / English Name"
    display_name = f"{name_cn} / {name_en}" if name_cn != plugin_id else plugin_id
    description = f"{desc_cn}\n{desc_en}" if desc_cn else ""
    return display_name, description

class DropZone(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setFixedHeight(100)
        self.setStyleSheet("QFrame { border: 2px dashed #666; border-radius: 10px; color: #888; } QFrame:hover { border-color: #aaa; color: #ddd; background: #333; }")
        
        layout = QVBoxLayout(self)
        self.label = QLabel("📥 拖入 .py 文件或文件夹以安装插件", self)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet("border: none; color: #888;")
        font = QFont()
        font.setPointSize(12)
        self.label.setFont(font)
        layout.addWidget(self.label)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        files = [u.toLocalFile() for u in event.mimeData().urls()]
        if files:
            self.parent().install_plugins(files)
            event.acceptProposedAction()


class PluginCard(QFrame):
    def __init__(self, plugin_id: str, is_enabled: bool, is_loaded: bool, parent=None):
        super().__init__(parent)
        self.plugin_id = plugin_id
        self.is_enabled_config = is_enabled
        self.is_loaded_runtime = is_loaded
        
        self.setFrameStyle(QFrame.StyledPanel | QFrame.Raised)
        self.setStyleSheet("""
            QFrame { 
                background-color: #2b2b2b; 
                border-radius: 8px; 
                border: 1px solid #3c3c3c;
            } 
            QFrame:hover { border-color: #5c5c5c; }
        """)
        
        layout = QVBoxLayout(self)
        
        # Get display info from metadata registry
        display_name, description = get_plugin_display_info(plugin_id)
        
        # Header: Name + Switch
        header_layout = QHBoxLayout()
        name_label = QLabel(display_name)
        name_label.setStyleSheet("font-weight: bold; font-size: 13px; border: none; color: #eeeeee;")
        name_label.setWordWrap(True)
        header_layout.addWidget(name_label)
        
        header_layout.addStretch()
        
        # Status Indicator
        self.status_indicator = QLabel()
        self.status_indicator.setFixedSize(12, 12)
        self.status_indicator.setStyleSheet(
            f"background-color: {'#4CAF50' if is_loaded else '#9E9E9E'}; border-radius: 6px; border: none;"
        )
        self.status_indicator.setToolTip("Running" if is_loaded else "Not Loaded")
        header_layout.addWidget(self.status_indicator)

        layout.addLayout(header_layout)
        
        # Description (if available)
        if description:
            desc_label = QLabel(description)
            desc_label.setStyleSheet("font-size: 11px; color: #888888; border: none;")
            desc_label.setWordWrap(True)
            layout.addWidget(desc_label)
        
        # Controls
        controls_layout = QHBoxLayout()
        
        self.toggle_switch = QCheckBox("启用")
        self.toggle_switch.setChecked(is_enabled)
        self.toggle_switch.setStyleSheet("border: none;")
        self.toggle_switch.toggled.connect(self.on_toggle)
        controls_layout.addWidget(self.toggle_switch)
        
        controls_layout.addStretch()
        
        # Reload Button (Turbo)
        reload_btn = QPushButton("⚡")
        reload_btn.setFixedSize(24, 24)
        reload_btn.setToolTip("强制热重载 (Hot Reload)")
        reload_btn.clicked.connect(self.on_reload)
        reload_btn.setStyleSheet("""
            QPushButton { 
                background: transparent; border: none; color: #ff9800; font-weight: bold;
            }
            QPushButton:hover { background: #444; border-radius: 4px; }
        """)
        controls_layout.addWidget(reload_btn)

        layout.addLayout(controls_layout)

    def on_toggle(self, checked: bool):
        # Update UI first
        self.is_enabled_config = checked
        
        # Emit signal to request state change
        if checked:
             GlobalSignalBus.plugin_enable_requested.emit(self.plugin_id)
        else:
             GlobalSignalBus.plugin_disable_requested.emit(self.plugin_id)

    def on_reload(self):
        # Force reload: Disable then Enable
        # Note: In a real async system this might race, but here it's sync.
        GlobalSignalBus.plugin_disable_requested.emit(self.plugin_id)
        GlobalSignalBus.plugin_enable_requested.emit(self.plugin_id)
        

class PluginManagerWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(15)

        # Title
        title = QLabel("🏰 God View: Plugins")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #ddd;")
        self.layout.addWidget(title)

        # Drop Zone
        self.drop_zone = DropZone(self)
        self.layout.addWidget(self.drop_zone)

        # Plugin Grid (Scrollable)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("background: transparent; border: none;")
        
        self.grid_container = QWidget()
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setSpacing(10)
        self.grid_layout.setAlignment(Qt.AlignTop)
        
        self.scroll.setWidget(self.grid_container)
        self.layout.addWidget(self.scroll)

        # Listen to updates
        GlobalSignalBus.plugin_state_changed.connect(self.on_plugin_state_changed)
        
        # Initial Load
        self.refresh_list()

    def refresh_list(self):
        # Clear existing
        for i in reversed(range(self.grid_layout.count())): 
            w = self.grid_layout.itemAt(i).widget()
            if w: w.setParent(None)

        # Read Config (Desired State)
        cfg = load_plugin_config()
        disabled_set = set(cfg.get("disabled_plugins", []))
        
        # Scan Dir (Available Sources)
        plugins_dir = Path("plugins")
        if not plugins_dir.exists():
            return
            
        items = sorted([p.name for p in plugins_dir.iterdir() if (p.is_dir() or p.suffix == '.py') and not p.name.startswith('_')])
        
        row = 0
        col = 0
        cols_per_row = 3
        
        for item in items:
            # Determine status
            is_enabled = item not in disabled_set
            
            # How to check if actually loaded runtime? 
            # Ideally PluginManager exposes this. For now we assume enabled = loaded unless failed.
            # Improvement: We could ask PluginManager via signal/method if we had access.
            # Or tracking it loosely.
            is_loaded = is_enabled # Approximation
            
            card = PluginCard(item, is_enabled, is_loaded)
            self.grid_layout.addWidget(card, row, col)
            
            col += 1
            if col >= cols_per_row:
                col = 0
                row += 1

    def on_plugin_state_changed(self, plugin_id: str, enabled: bool):
        # Update config persistence
        # This widget is responsible for updating the JSON Config when state changes!
        # Because PluginManager Backend only reads config on startup, or loads on request.
        # Wait, if we want persistence, we must update JSON here.
        
        cfg = load_plugin_config()
        disabled_list = cfg.get("disabled_plugins", [])
        
        if enabled:
            if plugin_id in disabled_list:
                disabled_list.remove(plugin_id)
        else:
            if plugin_id not in disabled_list:
                disabled_list.append(plugin_id)
                
        cfg["disabled_plugins"] = disabled_list
        from core.config_manager import save_plugin_config
        save_plugin_config(cfg)
        
        # Refresh UI? Or just simple update. 
        # Full refresh is safer to sync everything.
        self.refresh_list()

    def install_plugins(self, file_paths):
        # Copy files to plugins/
        plugins_dir = Path("plugins")
        installed_count = 0
        
        for path in file_paths:
            src = Path(path)
            if not src.exists(): continue
            
            # Security Warning
            # In a real app, use QMessageBox.question(...)
            # But we are the 'God View' - we assume user intent.
            
            try:
                if src.is_dir():
                    shutil.copytree(src, plugins_dir / src.name, dirs_exist_ok=True)
                else:
                    if src.suffix == '.py':
                        shutil.copy2(src, plugins_dir)
                
                installed_count += 1
                # Auto-enable
                GlobalSignalBus.plugin_enable_requested.emit(src.name)
                
            except Exception as e:
                print(f"Error installing {src.name}: {e}")

        if installed_count > 0:
            self.refresh_list()
