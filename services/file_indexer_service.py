import hashlib
import logging
import os
import queue
import sqlite3
import re
import threading
import time
import shutil
from pathlib import Path

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from whoosh.index import create_in, open_dir, exists_in
from whoosh.fields import Schema, TEXT, ID
from whoosh.qparser import QueryParser

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class FileIndexerService:
    def __init__(self, vault_path: str):
        self.vault_path = Path(vault_path)
        # Internal storage root renamed to .EvoNotDB (ST-02 S1)
        self.enotes_path = self.vault_path / ".EvoNotDB"
        self.db_path = self.enotes_path / "index.db"
        self.whoosh_path = self.enotes_path / "whoosh_index"
        
        self.task_queue = queue.Queue()
        self.observer = None
        self.worker_thread = None
        self.running = False
        self.initial_scan_complete = threading.Event()

        # GC scheduling state (P1-10)
        self._gc_idle_interval = 300.0  # seconds
        self._last_gc_time = 0.0
        self._initial_gc_done = False
        self._gc_running = False

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
        """Stops the file indexer service (idempotent and re-entrant)."""
        logging.info("Stopping FileIndexerService...")

        # Stop filesystem observer safely
        try:
            if self.observer is not None:
                self.observer.stop()
                self.observer.join()
                logging.info("File system observer stopped.")
        except Exception as e:
            logging.warning(f"Observer stop encountered an issue: {e}")
        finally:
            self.observer = None

        # Stop worker thread
        self.running = False
        try:
            if self.worker_thread is not None and self.worker_thread.is_alive():
                self.worker_thread.join()
                logging.info("Worker thread stopped.")
        except Exception as e:
            logging.warning(f"Worker thread join encountered an issue: {e}")
        finally:
            self.worker_thread = None

        logging.info("FileIndexerService stopped.")
        
        # Close Whoosh handle
        if hasattr(self, "whoosh_index"):
            try:
                self.whoosh_index.close()
            except Exception:
                pass

    def search(self, query_str: str) -> list[dict]:
        """
        Perform a full-text search on the vault content.
        Returns a list of dicts: {'path': str, 'highlights': str}
        """
        results = []
        if not hasattr(self, "whoosh_index"):
            return results
            
        try:
            with self.whoosh_index.searcher() as searcher:
                parser = QueryParser("content", self.whoosh_index.schema)
                query = parser.parse(query_str)
                hits = searcher.search(query, limit=20)
                
                for hit in hits:
                    results.append({
                        "path": hit["path"],
                        "highlights": hit.highlights("content")
                    })
        except Exception as e:
            logging.error(f"Search failed for '{query_str}': {e}")
        
        return results

    def rebuild_index(self):
        """
        Safely rebuild the internal index and database (.EvoNotDB).
        Steps:
          1) Stop observer and worker threads.
          2) Delete .EvoNotDB directory.
          3) Reset internal state flags.
          4) Reinitialize storage and trigger full rescan.
        """
        logging.info("Rebuilding index: starting teardown...")
        # Ensure services are stopped
        self.stop()
        # Release whoosh handle to avoid file lock/race conditions on Windows
        try:
            self.whoosh_index = None
        except Exception:
            self.whoosh_index = None

        # Remove internal storage directory (.EvoNotDB)
        try:
            if self.enotes_path.exists():
                shutil.rmtree(self.enotes_path, ignore_errors=True)
                logging.info(f"Removed storage directory: {self.enotes_path}")
        except Exception as e:
            logging.error(f"Failed to remove storage directory {self.enotes_path}: {e}")

        # Reset internal state
        try:
            self.initial_scan_complete.clear()
        except Exception:
            # If event not initialized for any reason, ignore
            pass
        self._initial_gc_done = False
        self._gc_running = False
        self._last_gc_time = 0.0

        # Restart services: init storage + initial scan + worker + observer
        logging.info("Rebuilding index: reinitializing services...")
        self.start()
        logging.info("Rebuilding index: completed.")

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
            # Ensure internal storage directories
            self.enotes_path.mkdir(exist_ok=True)
            self.whoosh_path.mkdir(exist_ok=True)

            # Ensure default top-level directories in the vault (ST-02 S3)
            (self.vault_path / "pages").mkdir(exist_ok=True)
            (self.vault_path / "assets").mkdir(exist_ok=True)

            logging.info(f"Ensured directories exist: {self.enotes_path} and {self.whoosh_path}")
            logging.info(f"Ensured vault defaults exist: {self.vault_path / 'pages'} and {self.vault_path / 'assets'}")

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
            # FR-1.1: Create 'blocks' table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS blocks (
                hash TEXT PRIMARY KEY,
                content TEXT NOT NULL
            )
            """)

            # FR-1.2: Create 'blocks_fts' FTS5 virtual table
            try:
                cursor.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS blocks_fts USING fts5(
                    content,
                    content='blocks',
                    content_rowid='rowid'
                )
                """)
                # Create triggers to keep FTS table in sync with 'blocks' table
                cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS blocks_ai AFTER INSERT ON blocks BEGIN
                    INSERT INTO blocks_fts(rowid, content) VALUES (new.rowid, new.content);
                END;
                """)
                cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS blocks_ad AFTER DELETE ON blocks BEGIN
                    INSERT INTO blocks_fts(blocks_fts, rowid, content) VALUES ('delete', old.rowid, old.content);
                END;
                """)
                cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS blocks_au AFTER UPDATE ON blocks BEGIN
                    INSERT INTO blocks_fts(blocks_fts, rowid, content) VALUES ('delete', old.rowid, old.content);
                    INSERT INTO blocks_fts(rowid, content) VALUES (new.rowid, new.content);
                END;
                """)
                self.fts_enabled = True
                logging.info("FTS5 virtual table and triggers for 'blocks' created.")
            except sqlite3.OperationalError as e:
                logging.warning(f"FTS5 is not available. Will fall back to LIKE queries. Error: {e}")
                self.fts_enabled = False

            # Create 'block_instances' table and indexes (FR-1.1)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS block_instances (
                block_hash TEXT NOT NULL,
                file_path TEXT NOT NULL,
                UNIQUE(block_hash, file_path)
            )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_block_instances_hash ON block_instances(block_hash)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_block_instances_path ON block_instances(file_path)")

            conn.commit()
            conn.close()
            logging.info(f"Database schema initialized in {self.db_path}")

            # --- Initialize Whoosh Index ---
            # Use whoosh.exists_in to robustly detect a valid index instead of relying on listdir (handles partial leftovers)
            if not exists_in(self.whoosh_path):
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
            parts = file_path.parts
            # Exclude internal database directories (.EvoNotDB and legacy .enotes) [ST-02 S4]
            if ".EvoNotDB" in parts or ".enotes" in parts:
                continue
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
                elif task_type == "rename_file":
                    self._handle_rename_file(task["src_path"], task["dest_path"])
                elif task_type == "sync_block":
                    self._handle_sync_block(task["old_hash"], task["new_content"])
                elif task_type == "garbage_collect_blocks":
                    self._gc_running = True
                    try:
                        self._handle_garbage_collect_blocks()
                    finally:
                        self._gc_running = False
                        self._last_gc_time = time.time()
                
                self.task_queue.task_done()
            except queue.Empty:
                # Idle period: schedule low-priority GC after initial scan, and then every 5 minutes (P1-10)
                try:
                    if self.initial_scan_complete.is_set() and self.task_queue.empty():
                        now = time.time()
                        if not self._initial_gc_done and not self._gc_running:
                            self.task_queue.put({"type": "garbage_collect_blocks"})
                            self._initial_gc_done = True
                            self._last_gc_time = now
                        elif (now - self._last_gc_time) >= self._gc_idle_interval and not self._gc_running:
                            self.task_queue.put({"type": "garbage_collect_blocks"})
                            self._last_gc_time = now
                except Exception:
                    # Never allow GC scheduling issues to break the worker loop
                    pass
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

            # --- Content Block Indexing (FR-2.1) ---
            # Clear existing block instances for this file before re-indexing (P1-02)
            cursor.execute("DELETE FROM block_instances WHERE file_path = ?", (file_path_str,))
            logging.info(f"Cleared old block instances for file: {file_path_str}")
            # Re-index content blocks and record instances (P1-03)
            self._index_content_blocks(content, cursor, file_path_str)

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

            # 2.5 Delete block_instances records for this file (P1-04)
            cursor.execute("DELETE FROM block_instances WHERE file_path = ?", (file_path_str,))
            logging.info(f"Deleted block instance records for: {file_path_str}")

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

                # Update block_instances file_path mapping (P1-05)
                cursor.execute("UPDATE block_instances SET file_path = ? WHERE file_path = ?", (dest_path_str, src_path_str))
                logging.info(f"Database: Updated block_instances: {src_path_str} -> {dest_path_str}")
                
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

    def _handle_rename_file(self, src_path_str: str, dest_path_str: str) -> None:
        """
        Handles rename_file task:
          1) Physically rename file on disk (src -> dest) with Windows-safe fallbacks
          2) Reuse existing DB/Whoosh update logic via _handle_move
          3) Globally replace all [[old]] references to [[new]] across the vault,
             preserving #anchor and |alias, using atomic writes, and enqueue 'upsert'
        """
        try:
            src = Path(src_path_str)
            dest = Path(dest_path_str)

            # Validation: only .md within vault, src exists and dest not exists
            if src.suffix.lower() != ".md" or dest.suffix.lower() != ".md":
                logging.warning(f"rename_file: only .md supported, got src={src.suffix}, dest={dest.suffix}")
                return

            try:
                vault_root = self.vault_path.resolve(strict=False)
                src_abs = src.resolve(strict=False)
                dest_abs = dest.resolve(strict=False)
            except Exception as e:
                logging.warning(f"rename_file: resolve failed: {e}")
                vault_root = self.vault_path
                src_abs = src
                dest_abs = dest

            def _in_vault(p: Path) -> bool:
                try:
                    p.relative_to(vault_root)
                    return True
                except Exception:
                    return False

            if not (_in_vault(src_abs) and _in_vault(dest_abs)):
                logging.warning(f"rename_file: paths must be within vault: src={src_abs}, dest={dest_abs}")
                return

            if not src.exists():
                logging.warning(f"rename_file: src not found: {src}")
                return
            if dest.exists():
                logging.warning(f"rename_file: dest already exists: {dest}")
                return

            # Ensure destination directory exists
            try:
                dest.parent.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                logging.warning(f"rename_file: failed to ensure dest dir {dest.parent}: {e}")

            # Physical rename with fallback (Windows-friendly)
            try:
                src.rename(dest)
            except Exception as e1:
                logging.warning(f"rename_file: Path.rename failed ({e1}), fallback to shutil.move")
                try:
                    shutil.move(str(src), str(dest))
                except Exception as e2:
                    logging.error(f"rename_file: rename failed {src} -> {dest}: {e2}")
                    return

            # Reuse transactional DB + Whoosh updates
            try:
                self._handle_move(src_path_str, dest_path_str)
            except Exception as e:
                logging.error(f"rename_file: _handle_move failed: {e}")

            # Prepare global link replacement
            old_title = Path(src_path_str).stem
            new_title = Path(dest_path_str).stem

            pattern = re.compile(
                r'\[\[\s*(?:pages/)?(' + re.escape(old_title) + r')(?P<tail>(?:#[^\]|]*)?(?:\|[^\]]*)?)\s*\]\]'
                .replace('<', '<').replace('>', '>')
            )

            updated_files = 0
            for file_path in self.vault_path.rglob("*.md"):
                parts = file_path.parts
                # Exclude internal storage directories
                if ".EvoNotDB" in parts or ".enotes" in parts:
                    continue
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        text = f.read()
                except Exception as e:
                    logging.warning(f"rename_file: cannot read {file_path}: {e}")
                    continue

                def _repl(m):
                    tail = m.group("tail") or ""
                    return f"[[{new_title}{tail}]]"

                new_text, n = pattern.subn(_repl, text)
                if n > 0 and new_text != text:
                    try:
                        self._atomic_write(file_path, new_text)
                        updated_files += 1
                        try:
                            self.task_queue.put({"type": "upsert", "path": str(file_path)})
                        except Exception as e:
                            logging.warning(f"rename_file: failed to enqueue upsert for {file_path}: {e}")
                    except Exception as e:
                        logging.error(f"rename_file: atomic write failed for {file_path}: {e}")

            logging.info(f"rename_file: global replacement completed; updated_files={updated_files}")

            # Final upsert for the new file to ensure full recomputation of links/backrefs
            try:
                self.task_queue.put({"type": "upsert", "path": str(dest)})
            except Exception as e:
                logging.warning(f"rename_file: failed to enqueue final upsert for {dest}: {e}")
        except Exception as e:
            logging.exception(f"rename_file failed: {e}")

    def _index_content_blocks(self, content: str, cursor: sqlite3.Cursor, file_path: str):
        """Extracts, hashes, and indexes content blocks {{...}} into the database, and records instances per file."""
        # A simple but effective regex to find content within {{...}}
        # It handles nested braces by being non-greedy and stopping at the first `}}`
        blocks = re.findall(r"\{\{((?:.|\n)+?)\}\}", content)
        if not blocks:
            return

        logging.info(f"Found {len(blocks)} potential content blocks to index.")
        for block_content in blocks:
            try:
                # Per spec, do not strip or alter the content
                content_hash = hashlib.sha256(block_content.encode('utf-8')).hexdigest()
                
                # Maintain unique block definitions
                cursor.execute(
                    "INSERT OR IGNORE INTO blocks (hash, content) VALUES (?, ?)",
                    (content_hash, block_content)
                )
                # Track instance at file granularity (UNIQUE(block_hash, file_path))
                cursor.execute(
                    "INSERT OR IGNORE INTO block_instances (block_hash, file_path) VALUES (?, ?)",
                    (content_hash, file_path)
                )
                if cursor.rowcount > 0:
                    logging.info(f"Recorded instance for block {content_hash[:8]}... in {file_path}")
            except Exception as e:
                logging.error(f"Failed to index content block: {e}")

    def _atomic_write(self, file_path: Path, content: str):
        """Atomically write content to file using temp file + os.replace (NFR-1, P1-06)."""
        tmp_name = f"{file_path.name}.enotes.tmp-{int(time.time()*1000)}-{threading.get_ident()}"
        tmp_path = file_path.with_name(tmp_name)
        try:
            with open(tmp_path, "w", encoding="utf-8", newline="") as f:
                f.write(content)
                try:
                    f.flush()
                    os.fsync(f.fileno())
                except Exception:
                    # fsync might not be available or necessary; ignore non-fatal errors
                    pass
            os.replace(tmp_path, file_path)
        finally:
            try:
                if tmp_path.exists():
                    tmp_path.unlink(missing_ok=True)
            except Exception:
                pass

    def _handle_sync_block(self, old_hash: str, new_content: str):
        """
        Handles global synchronization of a content block across all files (FR-2.2, P1-07, P1-08).
        - Replaces all occurrences of {{old_content}} with {{new_content}} in affected files using atomic writes.
        - Smart merge: if new_hash exists, reuse it; otherwise create it.
        - Updates block_instances mapping from old_hash -> new_hash.
        - Enqueues 'upsert' for affected files to refresh indexes.
        """
        try:
            new_hash = hashlib.sha256(new_content.encode("utf-8")).hexdigest()
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            # Fetch old content by hash
            cursor.execute("SELECT content FROM blocks WHERE hash = ?", (old_hash,))
            row = cursor.fetchone()
            if not row:
                logging.warning(f"sync_block: old_hash not found in blocks; aborting replacement.")
                conn.close()
                return
            old_content = row[0]
            logging.info(f"sync_block: fetched old_content={repr(old_content)} for hash {old_hash[:8]}")

            # Smart merge: ensure new block exists or reuse
            cursor.execute("SELECT 1 FROM blocks WHERE hash = ?", (new_hash,))
            exists = cursor.fetchone() is not None
            if not exists:
                cursor.execute("INSERT OR IGNORE INTO blocks (hash, content) VALUES (?, ?)", (new_hash, new_content))

            # Determine affected files
            cursor.execute("SELECT DISTINCT file_path FROM block_instances WHERE block_hash = ?", (old_hash,))
            files = [r[0] for r in cursor.fetchall()]
            logging.info(f"sync_block: {len(files)} files to update for hash {old_hash[:8]}...")

            # Prepare regex for exact block replacement (DOTALL to match multi-line)
            # Use re.escape on the content, but keep {{ }} raw
            escaped_content = re.escape(old_content)
            pattern_str = r"\{\{" + escaped_content + r"\}\}"
            pattern = re.compile(pattern_str, flags=re.DOTALL)
            logging.info(f"sync_block: regex pattern='{pattern_str}'")

            updated_files = 0
            for fp in files:
                p = Path(fp)
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        txt = f.read()
                except Exception as e:
                    logging.warning(f"sync_block: cannot read {fp}: {e}")
                    continue

                new_txt, n = pattern.subn("{{" + new_content + "}}", txt)
                if n > 0 and new_txt != txt:
                    try:
                        self._atomic_write(p, new_txt)
                        updated_files += 1
                        # Enqueue reindex for this file
                        self.task_queue.put({"type": "upsert", "path": fp})
                        logging.info(f"sync_block: successfully updated {fp} ({n} replacements)")
                    except Exception as e:
                        logging.error(f"sync_block: atomic write failed for {fp}: {e}")
                else:
                    logging.info(f"sync_block: no occurrences to replace in {fp}. File content sample: {repr(txt[:50])}...")

            # Update block_instances mapping for the affected files (avoid UNIQUE conflicts)
            for fp in files:
                try:
                    cursor.execute(
                        "INSERT OR IGNORE INTO block_instances (block_hash, file_path) VALUES (?, ?)",
                        (new_hash, fp)
                    )
                    cursor.execute(
                        "DELETE FROM block_instances WHERE block_hash = ? AND file_path = ?",
                        (old_hash, fp)
                    )
                except Exception as e:
                    logging.warning(f"sync_block: mapping update failed for {fp}: {e}")

            conn.commit()
            conn.close()
            logging.info(f"sync_block completed: updated_files={updated_files}, new_hash={new_hash[:8]}...")
            
            # Emit signal for each updated file so open editors can reload
            try:
                from core.signals import GlobalSignalBus
                for fp in files:
                    GlobalSignalBus.file_externally_modified.emit(fp)
                    logging.info(f"sync_block: emitted file_externally_modified for {fp}")
            except Exception as e:
                logging.warning(f"sync_block: failed to emit signals: {e}")
        except Exception as e:
            logging.exception(f"sync_block failed: {e}")

    def _handle_garbage_collect_blocks(self):
        """
        Garbage collect orphaned blocks not referenced by any file (FR-2.3, P1-09).
        Uses triggers to keep FTS in sync when deleting from 'blocks'.
        """
        logging.info("GC: scanning for orphan content blocks...")
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT hash FROM blocks
                EXCEPT
                SELECT DISTINCT block_hash FROM block_instances
            """)
            orphans = [r[0] for r in cursor.fetchall()]
            if not orphans:
                logging.info("GC: no orphan blocks found.")
                conn.close()
                return

            logging.info(f"GC: deleting {len(orphans)} orphan blocks...")
            for h in orphans:
                cursor.execute("DELETE FROM blocks WHERE hash = ?", (h,))
            conn.commit()
            conn.close()
            logging.info("GC: completed.")
        except Exception as e:
            logging.exception(f"GC failed: {e}")
            try:
                conn.close()
            except Exception:
                pass

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