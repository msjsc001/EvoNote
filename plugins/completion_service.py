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

    def __init__(self, whoosh_path='.EvoNotDB/whoosh_index', db_path='.EvoNotDB/index.db'):
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
        """
        ST-07: Page link completion based on SQLite files table with stem-prefix matching.
        - Return stems (no .md)
        - Prefer pages/ directory; de-duplicate by stem (pages/ wins)
        - Case-insensitive prefix using str.casefold()
        - When DB missing or query fails, return empty list
        """
        from pathlib import Path
        conn = None
        try:
            # DB not ready -> empty result
            if not os.path.exists(self.db_path):
                if self._is_running:
                    self.results_ready.emit([])
                return

            q = (query_text or "").casefold()

            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()
            # Limit scan to keep latency bounded; Python-side filter/dedup
            cur.execute("SELECT path FROM files LIMIT 500")
            rows = cur.fetchall()

            pages = []
            pages_set = set()
            others = []
            others_set = set()

            for (p,) in rows:
                if not p:
                    continue
                try:
                    stem = Path(p).stem
                except Exception:
                    base = os.path.basename(p)
                    stem = os.path.splitext(base)[0]
                if not stem:
                    continue

                # Case-insensitive prefix
                if q and not stem.casefold().startswith(q):
                    continue

                norm = p.replace("\\", "/").lower()
                in_pages = "/pages/" in norm or norm.startswith("pages/")

                if in_pages:
                    if stem not in pages_set:
                        pages.append(stem)
                        pages_set.add(stem)
                else:
                    if stem not in pages_set and stem not in others_set:
                        others.append(stem)
                        others_set.add(stem)

                # Early stop once buffers are sufficiently large for final top-10
                if len(pages) + len(others) >= 64:
                    break

            results = (pages + [s for s in others if s not in pages_set])[:10]
            if self._is_running:
                self.results_ready.emit(results)
        except Exception as e:
            logging.error(f"SQLite page_link completion failed: {e}")
            if self._is_running:
                self.results_ready.emit([])
        finally:
            try:
                if conn:
                    conn.close()
            except Exception:
                pass

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
                whoosh_path = os.path.join(".EvoNotDB", "whoosh_index")
                db_path = os.path.join(".EvoNotDB", "index.db")
        except Exception:
            whoosh_path = os.path.join(".EvoNotDB", "whoosh_index")
            db_path = os.path.join(".EvoNotDB", "index.db")
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