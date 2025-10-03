import os
import sqlite3
import logging
from PySide6.QtCore import QObject, QThread, Signal as pyqtSignal, Slot as pyqtSlot
from whoosh.index import open_dir
from whoosh.qparser import MultifieldParser, OrGroup
from whoosh.query import Prefix

from core.signals import GlobalSignalBus

class CompletionWorker(QObject):
    results_ready = pyqtSignal(list)

    def __init__(self, whoosh_path='.enotes/whoosh_index', db_path='.enotes/index.db'):
        super().__init__()
        self.whoosh_path = whoosh_path
        self.db_path = db_path
        self.index = None
        self._is_running = True
        self._init_resources()

    def _init_resources(self):
        if os.path.exists(self.whoosh_path):
            try:
                self.index = open_dir(self.whoosh_path)
            except Exception as e:
                logging.error(f"Failed to open Whoosh index: {e}")
        # Note: SQLite connection should be created per-thread, so we don't connect here.

    @pyqtSlot(str, str)
    def search(self, completion_type, query_text):
        if not self._is_running:
            self.results_ready.emit([])
            return

        if not query_text.strip():
            self.results_ready.emit([])
            return

        try:
            if completion_type == 'page_link':
                self._search_page_links(query_text)
            elif completion_type == 'content_block':
                self._search_content_blocks(query_text)
            else:
                self.results_ready.emit([])
        except Exception as e:
            logging.error(f"Completion search failed for type '{completion_type}': {e}")
            self.results_ready.emit([])

    def _search_page_links(self, query_text):
        if not self.index:
            self.results_ready.emit([])
            return
        query = Prefix("path", query_text)
        with self.index.searcher() as searcher:
            results = searcher.search(query, limit=10)
            paths = [hit['path'] for hit in results]
            if self._is_running:
                self.results_ready.emit(paths)

    def _search_content_blocks(self, query_text):
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            # FTS5 query: match prefixes. The '*' is what makes it a prefix search.
            # Using MATCH instead of LIKE for performance, as requested.
            # We'll try FTS5 first, and fall back to LIKE if the table doesn't exist.
            try:
                # FR-3.2: Query `blocks_fts` virtual table
                cursor.execute(
                    "SELECT content FROM blocks_fts WHERE content MATCH ? LIMIT 10",
                    (f'"{query_text}"*', ) # Using phrase prefix query
                )
                results = [row[0] for row in cursor.fetchall()]
            except sqlite3.OperationalError:
                # Fallback for when FTS5 is not enabled or table is missing
                logging.warning("Falling back to LIKE query for content blocks.")
                cursor.execute(
                    "SELECT content FROM blocks WHERE content LIKE ? LIMIT 10",
                    (f"{query_text}%",)
                )
                results = [row[0] for row in cursor.fetchall()]

            if self._is_running:
                self.results_ready.emit(results)
        finally:
            if conn:
                conn.close()

    def stop(self):
        self._is_running = False

class CompletionServicePlugin(QObject):
    search_requested = pyqtSignal(str, str)

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.completion_type = None
        self.current_query = None

        self.thread = QThread()
        # Derive paths from FileIndexerService to avoid reliance on Qt property
        try:
            fis = getattr(self.app, "file_indexer_service", None)
            if fis is not None:
                whoosh_path = str(getattr(fis, "whoosh_path"))
                db_path = str(getattr(fis, "db_path"))
            else:
                # Fallback to default relative paths
                whoosh_path = os.path.join(".enotes", "whoosh_index")
                db_path = os.path.join(".enotes", "index.db")
        except Exception:
            whoosh_path = os.path.join(".enotes", "whoosh_index")
            db_path = os.path.join(".enotes", "index.db")
        self.worker = CompletionWorker(whoosh_path=whoosh_path, db_path=db_path)
        self.worker.moveToThread(self.thread)

        self.search_requested.connect(self.worker.search)
        self.worker.results_ready.connect(self.on_results_ready)
        GlobalSignalBus.completion_requested.connect(self.on_completion_requested)

        self.thread.start()

    @pyqtSlot(str, str)
    def on_completion_requested(self, completion_type, query_text):
        self.completion_type = completion_type
        self.current_query = query_text
        self.search_requested.emit(completion_type, query_text)

    @pyqtSlot(list)
    def on_results_ready(self, results):
        GlobalSignalBus.completion_results_ready.emit(self.completion_type, self.current_query, results)

    def unload(self):
        """Cleans up resources when the plugin is unloaded."""
        if self.thread.isRunning():
            self.worker.stop()
            self.thread.quit()
            self.thread.wait()
        GlobalSignalBus.completion_requested.disconnect(self.on_completion_requested)

def create_plugin(app):
    return CompletionServicePlugin(app)