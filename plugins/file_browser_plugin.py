
from PySide6.QtWidgets import QTreeView, QFileSystemModel, QHeaderView
from PySide6.QtCore import Qt, QDir
from core.api import Plugin

class FileBrowserWidget(QTreeView):
    def __init__(self, app_context):
        super().__init__()
        self.app_context = app_context
        
        self.setHeaderHidden(True)
        self.setAnimated(True)
        self.setIndentation(20)
        self.setSortingEnabled(True)
        
        # Setup File System Model
        self.model = QFileSystemModel()
        # Filter for .md and folders
        self.model.setNameFilters(["*.md"])
        self.model.setNameFilterDisables(False) # Hide others
        
        # Determine vault path
        vault_path = self.app_context.api.get_vault_path()
        if not vault_path:
             # Fallback if no vault loaded (shouldn't happen in normal run)
             vault_path = "."
        
        self.model.setRootPath(vault_path)
        self.setModel(self.model)
        self.setRootIndex(self.model.index(vault_path))
        
        # Hide Size/Type/Date columns
        for i in range(1, 4):
            self.setColumnHidden(i, True)
            
        # Events
        self.doubleClicked.connect(self.on_double_click)

    def on_double_click(self, index):
        file_path = self.model.filePath(index)
        if self.model.isDir(index):
            return
            
        # Convert to relative path or just pass absolute?
        # API handles absolute too.
        self.app_context.api.open_note(file_path)

def create_plugin(app_context):
    return FileBrowserPlugin(app_context)

class FileBrowserPlugin(Plugin):
    def __init__(self, app_context):
        self.app_context = app_context
        self.name = "Files"
        self.dock_area = Qt.LeftDockWidgetArea

    def get_widget(self):
        return FileBrowserWidget(self.app_context)