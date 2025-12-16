
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLineEdit, QListWidget, 
                               QListWidgetItem, QPushButton, QLabel, QHBoxLayout)
from PySide6.QtCore import Qt
from core.api import Plugin
from core.signals import GlobalSignalBus

class GlobalSearchWidget(QWidget):
    def __init__(self, app_context):
        super().__init__()
        self.app_context = app_context
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(4, 4, 4, 4)
        
        # Search Bar
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search all notes...")
        self.search_input.returnPressed.connect(self.do_search)
        
        self.btn_search = QPushButton("Search")
        self.btn_search.clicked.connect(self.do_search)
        
        top_layout = QHBoxLayout()
        top_layout.addWidget(self.search_input)
        top_layout.addWidget(self.btn_search)
        
        self.layout.addLayout(top_layout)
        
        # Results List
        self.result_list = QListWidget()
        self.result_list.itemClicked.connect(self.on_item_clicked)
        self.layout.addWidget(self.result_list)
        
        # Status
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #888;")
        self.layout.addWidget(self.status_label)

    def do_search(self):
        query = self.search_input.text().strip()
        if not query:
            return
            
        service = getattr(self.app_context, "file_indexer_service", None)
        if not service:
            self.status_label.setText("Error: Indexer not available")
            return
            
        self.status_label.setText("Searching...")
        self.result_list.clear()
        
        try:
            results = service.search(query)
            if not results:
                self.status_label.setText("No results found.")
                return
                
            for res in results:
                path = res['path']
                highlights = res.get('highlights', '')
                
                # Create item
                # Label: Filename
                # Tooltip: Highlights
                import os
                filename = os.path.basename(path)
                
                item = QListWidgetItem(f"{filename}")
                item.setToolTip(highlights) # Simple tooltip for now
                item.setData(Qt.UserRole, path)
                
                # HTML styling for highlights in the list item itself would require a custom delegate
                # For now, just show filename
                self.result_list.addItem(item)
                
            self.status_label.setText(f"Found {len(results)} results.")
            
        except AttributeError:
             self.status_label.setText("Error: Indexer does not support search.")
        except Exception as e:
            self.status_label.setText(f"Error: {e}")

    def on_item_clicked(self, item):
        path = item.data(Qt.UserRole)
        if path:
            # Convert absolute path to vault-relative for navigation
            # Or just send the absolute path if navigation supports it? 
            # App.on_page_navigation_requested calls _resolve_and_ensure_page 
            # which works with "pages/Title.md".
            # We should try to pass the filename relative to 'pages' if possible, or just the filename?
            # Let's try sending the filename (stem) as "Title"
            
            # Better: Make 'on_page_navigation_requested' robust enough to handle absolute paths?
            # Currently checks 'pages/' prefix or .md extension.
            # Let's verify what `_resolve_and_ensure_page` does.
            # It calculates relative path if absolute is given! 
            # But `on_page_navigation_requested` takes `page_title: str`.
            
            # Let's modify the plugin to send the STEM if inside pages, or relative path.
            import os
            from pathlib import Path
            p = Path(path)
            # Assumption: all notes are in pages/
            # Send just the stem (Title)
            page_title = p.stem 
            GlobalSignalBus.page_navigation_requested.emit(page_title)


def create_plugin(app_context):
    return GlobalSearchPlugin(app_context)

class GlobalSearchPlugin(Plugin):
    def __init__(self, app_context):
        self.app_context = app_context
        self.name = "Global Search"
        self.dock_area = Qt.LeftDockWidgetArea # Place in left dock

    def get_widget(self):
        return GlobalSearchWidget(self.app_context)
