import logging
import os
import queue
import sqlite3
import re
import threading
import time
from pathlib import Path

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from whoosh.index import create_in, open_dir
from whoosh.fields import Schema, TEXT, ID

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class FileIndexerService:
    def __init__(self, vault_path: str):
        self.vault_path = Path(vault_path)
        self.enotes_path = self.vault_path / ".enotes"
        self.db_path = self.enotes_path / "index.db"
        self.whoosh_path = self.enotes_path / "whoosh_index"
        
        self.task_queue = queue.Queue()
        self.observer = None
        self.worker_thread = None
        self.running = False
        self.initial_scan_complete = threading.Event()

    def start(self):
        """Starts the file indexer service."""
        logging.info("Starting FileIndexerService...")
        self.running = True
        
        self._init_storage()
        
        # Start the background thread for initial scan
        initial_scan_thread = threading.Thread(target=self._initial_scan)
        initial_scan_thread.daemon = True
        initial_scan_thread.start()
        
        # Start the worker thread
        self.worker_thread = threading.Thread(target=self._process_tasks)
        self.worker_thread.daemon = True
        self.worker_thread.start()

        # Start the file system observer
        event_handler = EventHandler(self.task_queue)
        self.observer = Observer()
        self.observer.schedule(event_handler, str(self.vault_path), recursive=True)
        self.observer.start()
        logging.info(f"Started watching directory: {self.vault_path}")
        
        logging.info("FileIndexerService started.")

    def stop(self):
        """Stops the file indexer service."""
        logging.info("Stopping FileIndexerService...")
        
        if self.observer:
            self.observer.stop()
            self.observer.join()
            logging.info("File system observer stopped.")

        self.running = False
        if self.worker_thread:
            self.worker_thread.join()
            logging.info("Worker thread stopped.")
        
        logging.info("FileIndexerService stopped.")

    def wait_for_idle(self):
        """Waits until the initial scan is complete and the task queue is empty."""
        logging.info("Waiting for initial scan to complete...")
        self.initial_scan_complete.wait()
        logging.info("Initial scan task queuing complete. Waiting for queue to be processed...")
        self.task_queue.join()
        logging.info("Task queue is empty. Indexer is idle.")

    def _init_storage(self):
        """Initializes the database and index directory."""
        logging.info("Initializing storage...")
        try:
            self.enotes_path.mkdir(exist_ok=True)
            self.whoosh_path.mkdir(exist_ok=True)
            logging.info(f"Ensured directories exist: {self.enotes_path} and {self.whoosh_path}")

            # --- Initialize SQLite Database ---
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY,
                path TEXT UNIQUE NOT NULL,
                modified_time REAL NOT NULL
            )
            """)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS links (
                source_id INTEGER NOT NULL,
                target_path TEXT NOT NULL,
                FOREIGN KEY (source_id) REFERENCES files (id) ON DELETE CASCADE
            )
            """)
            conn.commit()
            conn.close()
            logging.info(f"Database schema initialized in {self.db_path}")

            # --- Initialize Whoosh Index ---
            if not os.path.exists(self.whoosh_path) or not os.listdir(self.whoosh_path):
                schema = Schema(path=ID(stored=True, unique=True), content=TEXT(stored=True))
                self.whoosh_index = create_in(self.whoosh_path, schema)
                logging.info(f"Whoosh index created in {self.whoosh_path}")
            else:
                self.whoosh_index = open_dir(self.whoosh_path)
                logging.info(f"Whoosh index opened from {self.whoosh_path}")

        except Exception as e:
            logging.error(f"Failed to initialize storage: {e}")

    def _initial_scan(self):
        """Performs an initial scan of the vault and populates the task queue."""
        logging.info("Starting initial vault scan...")
        for file_path in self.vault_path.rglob("*.md"):
            if ".enotes" not in file_path.parts:
                task = {"type": "upsert", "path": str(file_path)}
                self.task_queue.put(task)
        logging.info("Initial vault scan complete. Tasks are queued for processing.")
        self.initial_scan_complete.set()

    def _process_tasks(self):
        """The main loop for the worker thread."""
        while self.running:
            try:
                task = self.task_queue.get(timeout=1)
                task_type = task.get("type")
                
                if task_type == "upsert":
                    self._handle_upsert(task["path"])
                elif task_type == "delete":
                    self._handle_delete(task["path"])
                elif task_type == "move":
                    self._handle_move(task["src_path"], task["dest_path"])
                
                self.task_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                logging.error(f"Error processing task {task}: {e}")

    def _handle_upsert(self, file_path_str: str):
        """Handles file creation and modification."""
        logging.warning("<<<<< EXECUTING MODIFIED UPSERT HANDLER >>>>>")
        logging.info(f"Processing upsert for: {file_path_str}")
        file_path = Path(file_path_str)
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            modified_time = file_path.stat().st_mtime

            # --- Database Operations ---
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            file_id = None
            cursor.execute("SELECT id FROM files WHERE path = ?", (file_path_str,))
            result = cursor.fetchone()

            if result:
                file_id = result[0]
                cursor.execute("UPDATE files SET modified_time = ? WHERE id = ?", (modified_time, file_id))
                logging.info(f"Updated existing file record for ID: {file_id}, Path: {file_path_str}")
            else:
                cursor.execute("INSERT INTO files (path, modified_time) VALUES (?, ?)", (file_path_str, modified_time))
                file_id = cursor.lastrowid
                logging.info(f"Inserted new file record with ID: {file_id}, Path: {file_path_str}")
            
            # Clear existing links for this file using the obtained file_id
            cursor.execute("DELETE FROM links WHERE source_id = ?", (file_id,))
            logging.info(f"Cleared old links for file ID: {file_id}")
            
            # Find and insert new links
            links = re.findall(r"\[\[(.+?)\]\]", content)
            for target_path in links:
                cursor.execute("INSERT INTO links (source_id, target_path) VALUES (?, ?)", (file_id, target_path))
            logging.info(f"Inserted {len(links)} new links for file ID: {file_id}")

            conn.commit()
            conn.close()
            logging.info(f"Updated database for: {file_path_str}")

            # --- Whoosh Index Operation ---
            writer = self.whoosh_index.writer()
            writer.update_document(path=file_path_str, content=content)
            writer.commit()
            logging.info(f"Updated Whoosh index for: {file_path_str}")


        except FileNotFoundError:
            logging.warning(f"File not found during upsert: {file_path_str}. It might have been deleted quickly.")
        except Exception as e:
            logging.exception(f"Failed to handle upsert for {file_path_str}")

    def _handle_delete(self, file_path_str: str):
        """Handles file deletion."""
        logging.info(f"Processing delete for: {file_path_str}")
        try:
            # --- Database Operations ---
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 1. Query file_id before deleting files table record
            file_id = None
            cursor.execute("SELECT id FROM files WHERE path = ?", (file_path_str,))
            result = cursor.fetchone()
            if result:
                file_id = result
                logging.info(f"Found file_id: {file_id} for path: {file_path_str}")
            else:
                logging.warning(f"File ID not found for path: {file_path_str}. No links to delete.")

            # 2. Delete related links records if file_id was found
            if file_id:
                cursor.execute("DELETE FROM links WHERE source_id = ?", (file_id,))
                logging.info(f"Deleted links records for source_id: {file_id}")

            # 3. Delete the file record
            cursor.execute("DELETE FROM files WHERE path = ?", (file_path_str,))
            logging.info(f"Deleted file record for path: {file_path_str}")
            
            conn.commit()
            conn.close()
            logging.info(f"Database operations completed for delete of: {file_path_str}")

            # --- Whoosh Index Operation ---
            writer = self.whoosh_index.writer()
            writer.delete_by_term('path', file_path_str)
            writer.commit()
            logging.info(f"Deleted from Whoosh index: {file_path_str}")


        except Exception as e:
            logging.error(f"Failed to handle delete for {file_path_str}: {e}")

    def _handle_move(self, src_path_str: str, dest_path_str: str):
        """Handles file renaming and moving."""
        logging.info(f"Processing move from {src_path_str} to {dest_path_str}")
        try:
            # --- Database Operations (in a single transaction) ---
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            conn.isolation_level = None # Enable autocommit mode, or manage transactions manually

            try:
                cursor.execute("BEGIN") # Start a transaction
                
                # Update the path in the 'files' table
                cursor.execute("UPDATE files SET path = ? WHERE path = ?", (dest_path_str, src_path_str))
                logging.info(f"Database: Updated files table: {src_path_str} -> {dest_path_str}")
                
                # Extract target names without .md extension
                old_target_name = Path(src_path_str).stem
                new_target_name = Path(dest_path_str).stem
                
                # Update any links that were pointing to the old path
                cursor.execute("UPDATE links SET target_path = ? WHERE target_path = ?", (new_target_name, old_target_name))
                logging.info(f"Database: Updated links table: {old_target_name} -> {new_target_name}")
                
                cursor.execute("COMMIT") # Commit the transaction
                logging.info(f"Database: Transaction committed for move from {src_path_str} to {dest_path_str}")

            except Exception as db_e:
                cursor.execute("ROLLBACK") # Rollback on error
                logging.error(f"Database: Transaction rolled back due to error: {db_e}")
                raise db_e # Re-raise the exception to be caught by the outer try-except
            finally:
                conn.close()
                logging.info("Database: Connection closed.")

            # --- Whoosh Index Operations ---
            logging.info(f"Whoosh: Processing index update for move from {src_path_str} to {dest_path_str}")
            writer = self.whoosh_index.writer()
            try:
                # Delete old document
                writer.delete_by_term('path', src_path_str)
                logging.info(f"Whoosh: Deleted old document for path: {src_path_str}")

                # Add new document
                dest_file_path = Path(dest_path_str)
                with open(dest_file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                writer.add_document(path=dest_path_str, content=content)
                logging.info(f"Whoosh: Added new document for path: {dest_path_str}")
                
                writer.commit()
                logging.info(f"Whoosh: Index committed for move.")
            except Exception as whoosh_e:
                writer.abort()
                logging.error(f"Whoosh: Index update aborted due to error: {whoosh_e}")
                raise whoosh_e # Re-raise the exception to be caught by the outer try-except
        except Exception as e:
            logging.error(f"Failed to handle move from {src_path_str} to {dest_path_str}: {e}")

class EventHandler(FileSystemEventHandler):
    def __init__(self, task_queue: queue.Queue):
        self.task_queue = task_queue

    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith(".md"):
            logging.info(f"File created: {event.src_path}")
            self.task_queue.put({"type": "upsert", "path": event.src_path})

    def on_modified(self, event):
        if not event.is_directory and event.src_path.endswith(".md"):
            logging.info(f"File modified: {event.src_path}")
            self.task_queue.put({"type": "upsert", "path": event.src_path})

    def on_deleted(self, event):
        if not event.is_directory and event.src_path.endswith(".md"):
            logging.info(f"File deleted: {event.src_path}")
            self.task_queue.put({"type": "delete", "path": event.src_path})

    def on_moved(self, event):
        if not event.is_directory and event.dest_path.endswith(".md"):
            logging.info(f"File moved: from {event.src_path} to {event.dest_path}")
            self.task_queue.put({"type": "move", "src_path": event.src_path, "dest_path": event.dest_path})