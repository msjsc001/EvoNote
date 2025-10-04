# plugins/backlink_service.py
"""
Backlink Service Plugin (no UI)
Listens to GlobalSignalBus.backlink_query_requested and performs asynchronous
SQLite queries against .EvoNotDB/index.db to fetch pages linking to the target.
"""

import os
import sqlite3
from pathlib import Path
from typing import List

from PySide6.QtCore import QObject, QThread, Signal as pyqtSignal, Slot as pyqtSlot

from core.signals import GlobalSignalBus


class BacklinkQueryWorker(QObject):
    """
    Worker living in a background thread to query backlinks without blocking UI.
    """
    results_ready = pyqtSignal(str, list)  # (page_path, results)

    def __init__(self, db_path='.EvoNotDB/index.db'):
        super().__init__()
        self.db_path = str(db_path)
        self._is_running = True

    @pyqtSlot(str)
    def query(self, page_path: str):
        """
        Execute a backlink query for the given page_path (relative, with extension).
        Results are emitted back via results_ready(page_path, results).
        """
        if not self._is_running:
            self.results_ready.emit(page_path, [])
            return

        # Convert to stem for matching links.target_path
        try:
            stem = Path(page_path).stem
        except Exception:
            stem = page_path.rsplit('.', 1)[0] if '.' in page_path else page_path

        results: List[str] = []
        try:
            if not os.path.exists(self.db_path):
                self.results_ready.emit(page_path, [])
                return

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT DISTINCT files.path
                FROM links
                JOIN files ON files.id = links.source_id
                WHERE links.target_path = ?
                """,
                (stem,),
            )
            rows = cursor.fetchall()
            results = [row[0] for row in rows if row and row[0]]
            conn.close()
        except Exception:
            # Swallow errors to keep UI responsive; optional logging could be added.
            results = []

        self.results_ready.emit(page_path, results)

    def stop(self):
        self._is_running = False


class BacklinkServicePlugin(QObject):
    """
    Service plugin that provides backlink data via the global signal bus.
    """
    # Internal signal to dispatch queries to the worker thread
    query_requested = pyqtSignal(str)

    def __init__(self, app):
        super().__init__()
        self.app = app

        # Determine db_path from FileIndexerService when available; fallback to default.
        db_path = None
        try:
            db_path = getattr(self.app.file_indexer_service, "db_path", None)
        except Exception:
            db_path = None
        if db_path is None:
            db_path = Path(".EvoNotDB") / "index.db"

        # Thread + worker setup
        self.thread = QThread()
        self.worker = BacklinkQueryWorker(str(db_path))
        self.worker.moveToThread(self.thread)

        # Wire internal and global signals
        self.query_requested.connect(self.worker.query)
        self.worker.results_ready.connect(self.on_results_ready)
        GlobalSignalBus.backlink_query_requested.connect(self.on_query_requested)

        self.thread.start()

    @pyqtSlot(str)
    def on_query_requested(self, page_path: str):
        # Forward query to worker in background thread
        self.query_requested.emit(page_path)

    @pyqtSlot(str, list)
    def on_results_ready(self, page_path: str, results: list):
        # Relay results to the global bus
        GlobalSignalBus.backlink_results_ready.emit(page_path, results)

    def unload(self):
        # Cleanup connections and stop thread
        try:
            GlobalSignalBus.backlink_query_requested.disconnect(self.on_query_requested)
        except Exception:
            pass
        if self.thread.isRunning():
            self.worker.stop()
            self.thread.quit()
            self.thread.wait()


def create_plugin(app):
    return BacklinkServicePlugin(app)