import os
from PySide6.QtCore import QObject, QThread, Signal as pyqtSignal, Slot as pyqtSlot
from whoosh.index import open_dir
from whoosh.qparser import MultifieldParser, OrGroup
from whoosh.query import Prefix

from core.signals import GlobalSignalBus

class CompletionWorker(QObject):
    results_ready = pyqtSignal(list)

    def __init__(self, whoosh_path='.enotes/whoosh_index'):
        super().__init__()
        # TODO: Make whoosh_path configurable
        self.whoosh_path = whoosh_path
        self.index = None
        self._is_running = True
        if os.path.exists(self.whoosh_path):
            self.index = open_dir(self.whoosh_path)

    @pyqtSlot(str)
    def search(self, query_text):
        if not self._is_running or not self.index:
            self.results_ready.emit([])
            return

        if not query_text.strip():
            self.results_ready.emit([])
            return
        
        # Use a MultifieldParser to search in both 'path' and 'content'
        # The OrGroup ensures that terms are joined by OR by default
        parser = MultifieldParser(["path", "content"], schema=self.index.schema, group=OrGroup)
        
        # Allow prefix matching for the last term in the query
        # Example: "Note A" becomes "Note Prefix('A')"
        # We manually construct the query to ensure it's a prefix query on the filename part.
        # A simple prefix query on the user's text is often more intuitive for completion.
        # We will search for any document where the 'path' field starts with the query text.
        
        try:
            # We are primarily interested in matching the filename for completion
            query = Prefix("path", query_text)

            with self.index.searcher() as searcher:
                results = searcher.search(query, limit=10) # Limit results for performance
                # Extract the 'path' field from the results
                paths = [hit['path'] for hit in results]
                if self._is_running:
                    self.results_ready.emit(paths)

        except Exception as e:
            # In a real application, this should use a proper logging framework
            print(f"Whoosh search error: {e}")
            self.results_ready.emit([])

    def stop(self):
        self._is_running = False

class CompletionServicePlugin(QObject):
    # Use an internal signal to safely pass the query to the worker thread
    search_requested = pyqtSignal(str)

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.completion_type = None
        self.current_query = None

        # Create a long-running thread and worker
        self.thread = QThread()
        self.worker = CompletionWorker()
        self.worker.moveToThread(self.thread)

        # Connect signals
        self.search_requested.connect(self.worker.search)
        self.worker.results_ready.connect(self.on_results_ready)
        GlobalSignalBus.completion_requested.connect(self.on_completion_requested)

        # Start the thread
        self.thread.start()

    @pyqtSlot(str, str)
    def on_completion_requested(self, completion_type, query_text):
        """
        Slot to receive requests from the UI.
        It simply forwards the query text to the worker thread via a signal.
        """
        self.completion_type = completion_type
        self.current_query = query_text
        self.search_requested.emit(query_text)

    @pyqtSlot(list)
    def on_results_ready(self, results):
        """
        Slot to receive results from the worker thread.
        It broadcasts the results to the application.
        """
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