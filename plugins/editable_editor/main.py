# plugins/editable_editor/main.py
import re
import logging
import os
import sqlite3
import hashlib
from PySide6.QtWidgets import QPlainTextEdit, QWidget, QDockWidget, QCompleter, QTextEdit, QPushButton, QHBoxLayout, QLabel, QLineEdit, QToolButton, QStyle
from pathlib import Path
from PySide6.QtCore import Slot, Qt, QStringListModel, QTimer, QMimeData
from PySide6.QtGui import QKeyEvent, QInputMethodEvent, QTextCursor, QTextCharFormat, QColor
from plugins.editor_plugin_interface import EditorPluginInterface
from core.parsing_service import parse_markdown
from core.signals import GlobalSignalBus
from core.image_handler import ImagePasteHandler


class TitleBarWidget(QWidget):
    def __init__(self, dock: QDockWidget, editor):
        super().__init__(dock)
        self.dock = dock
        self.editor = editor

        class _ClickableLabel(QLabel):
            def __init__(self, owner):
                super().__init__(owner)
                self._owner = owner
            def mouseDoubleClickEvent(self, event):
                try:
                    self._owner.enter_edit_mode()
                except Exception:
                    pass
                try:
                    super().mouseDoubleClickEvent(event)
                except Exception:
                    pass

        class _RenameLineEdit(QLineEdit):
            def __init__(self, owner):
                super().__init__(owner)
                self._owner = owner
            def keyPressEvent(self, event: QKeyEvent):
                try:
                    if event.key() == Qt.Key_Escape:
                        self._owner.exit_edit_mode(commit=False)
                        event.accept()
                        return
                    if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                        self._owner.exit_edit_mode(commit=True)
                        event.accept()
                        return
                except Exception:
                    pass
                try:
                    super().keyPressEvent(event)
                except Exception:
                    pass
            def focusOutEvent(self, event):
                try:
                    # Treat focus out as submit
                    self._owner.exit_edit_mode(commit=True)
                except Exception:
                    pass
                try:
                    super().focusOutEvent(event)
                except Exception:
                    pass

        self._label = _ClickableLabel(self)
        self._label.setObjectName("evonoteDockTitle")
        self._label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self._edit = _RenameLineEdit(self)
        self._edit.hide()
        self._edit.returnPressed.connect(lambda: self.exit_edit_mode(commit=True))

        self._btn_float = QToolButton(self)
        self._btn_float.setAutoRaise(True)
        self._btn_float.setToolTip("浮动/停靠")
        self._btn_float.clicked.connect(self._on_float_clicked)

        self._btn_close = QToolButton(self)
        self._btn_close.setAutoRaise(True)
        self._btn_close.setToolTip("关闭")
        try:
            self._btn_close.setIcon(self.style().standardIcon(QStyle.SP_TitleBarCloseButton))
        except Exception:
            pass
        self._btn_close.clicked.connect(lambda: self.dock.close())

        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 2, 8, 2)
        lay.setSpacing(6)
        lay.addWidget(self._label)
        lay.addWidget(self._edit)
        lay.addStretch(1)
        lay.addWidget(self._btn_float)
        lay.addWidget(self._btn_close)

        self._refresh_float_icon()

    def _refresh_float_icon(self):
        try:
            if self.dock.isFloating():
                self._btn_float.setIcon(self.style().standardIcon(QStyle.SP_TitleBarNormalButton))
            else:
                self._btn_float.setIcon(self.style().standardIcon(QStyle.SP_TitleBarMaxButton))
        except Exception:
            pass

    def _on_float_clicked(self):
        try:
            self.dock.setFloating(not self.dock.isFloating())
            self._refresh_float_icon()
        except Exception:
            pass

    def set_title(self, text: str):
        try:
            self._label.setText(text or "")
        except Exception:
            pass
        try:
            self._refresh_float_icon()
        except Exception:
            pass

    def enter_edit_mode(self):
        try:
            self._edit.setText(self._label.text())
            self._label.hide()
            self._edit.show()
            self._edit.setFocus()
            self._edit.selectAll()
        except Exception:
            pass

    def exit_edit_mode(self, commit: bool):
        try:
            if commit:
                new_name = (self._edit.text() or "").strip()
                try:
                    self.editor._commit_rename(new_name)
                except Exception:
                    pass
            self._edit.hide()
            self._label.show()
        except Exception:
            try:
                self._edit.hide()
                self._label.show()
            except Exception:
                pass

class ReactiveEditor(QPlainTextEdit):
    """
    A reactive editor that leverages Qt's native text editing engine.
    It listens for content changes and triggers AST parsing in the background.
    """
    def __init__(self):
        super().__init__()
        self.completer = QCompleter(self)
        self.completer.setWidget(self)
        self.completer.setCompletionMode(QCompleter.PopupCompletion)
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.completer.setFilterMode(Qt.MatchContains)
        self.completer.setMaxVisibleItems(12)
        self.completer.activated[str].connect(self.insert_completion)

        self.completion_model = QStringListModel(self)
        self.completer.setModel(self.completion_model)

        self.document().contentsChanged.connect(self._on_contents_changed)
        GlobalSignalBus.completion_results_ready.connect(self._on_completion_results_ready)
        GlobalSignalBus.active_page_changed.connect(self.on_active_page_changed)
        # ST-16: subscribe to vault state changes
        GlobalSignalBus.vault_state_changed.connect(self.on_vault_state_changed)
         
        self.setPlainText("# Welcome to EvoNote\n\nStart typing...")
        self.last_completion_prefix = None
        # ST-16: initial editor flags (will be updated via vault_state_changed or plugin injection)
        self._has_active_vault = True
        self._completion_enabled = True
        # V0.4.6: Editor scope flags
        self._follow_global_active_page = True # If False, this editor ignores GlobalSignalBus.active_page_changed
        self._handle_navigation_locally = False # If True, [[links]] are handled locally, not via GlobalSignalBus.page_navigation_requested
        # Current active file path for this editor instance (relative, with extension)
        # FR-2: Used to broadcast active page on focus.
        self.current_file_path = "Note A.md"

        # Link rendering state and debounce timer
        self._link_regions = []
        self._render_timer = QTimer(self)
        self._render_timer.setSingleShot(True)
        self._render_timer.timeout.connect(self._recompute_and_apply_link_selections)

        # Enable hover tracking for interactive links
        self.setMouseTracking(True)
        try:
            self.viewport().setMouseTracking(True)
        except Exception:
            pass

        # Initial render for any pre-filled [[links]]
        self._schedule_render_update()

        # V0.4.5 Content Block Sync UI state
        self._db_path = getattr(self, "_db_path", None)
        self._active_block = None  # {'start': int, 'end': int, 'original_content': str, 'original_hash': str}
        self._block_overlay = None
        self._block_debounce_ms = 180
        self._block_timer = QTimer(self)
        self._block_timer.setSingleShot(True)
        self._block_timer.timeout.connect(self._on_block_debounce_timeout)

        # P2-10: Keep overlay anchored on scroll/caret move/viewport updates
        try:
            self.cursorPositionChanged.connect(self._reposition_overlay)
        except Exception:
            pass
        try:
            self.verticalScrollBar().valueChanged.connect(lambda _: self._reposition_overlay())
        except Exception:
            pass

        # E1: Initialize auto-save debounce timer
        try:
            self._autosave_timer = QTimer(self)
            self._autosave_timer.setSingleShot(True)
            self._autosave_timer.timeout.connect(self._perform_autosave)
        except Exception:
            # Timer init failure should not break editor
            self._autosave_timer = None
        self._autosave_interval_ms = 800
        self._autosave_interval_ms = 800
        self._last_saved_hash = None

    def insertFromMimeData(self, source: QMimeData):
        """
        Override standard paste behavior to intercept images.
        """
        if source.hasImage():
            try:
                ctx = getattr(self, "app_context", None)
                idx = getattr(ctx, "file_indexer_service", None) if ctx else None
                vault = getattr(idx, "vault_path", None) if idx else None
                
                if vault:
                    handler = ImagePasteHandler(str(vault))
                    md_link = handler.handle_mime_data(source)
                    if md_link:
                        self.insertPlainText(md_link)
                        return
            except Exception as e:
                print(f"WARNING: Image paste failed: {e}")
        
        # Fallback to default (text/html)
        super().insertFromMimeData(source)

    def keyPressEvent(self, event: QKeyEvent):
        if self.completer.popup().isVisible():
            if event.key() in (Qt.Key_Enter, Qt.Key_Return, Qt.Key_Tab, Qt.Key_Backtab):
                event.ignore()
                return

        # P2-02: capture snapshot of the current {{...}} block before edit
        try:
            self._capture_snapshot_pre_edit()
        except Exception:
            pass

        # B3: F2 triggers dock title rename edit mode
        if event.key() == Qt.Key_F2:
            try:
                self._begin_rename()
            except Exception:
                pass
            event.accept()
            return

        super().keyPressEvent(event)
        # Immediately hide completion when typing a closing brace '}}'
        try:
            if event.text() == "}":
                c = self.textCursor()
                pos = c.position()
                txt = self.toPlainText()
                if pos >= 2 and txt[pos-2:pos] == "}}":
                    try:
                        self.completer.popup().hide()
                    except Exception:
                        pass
        except Exception:
            pass
        # Also trigger completion check from key event to be robust
        self._check_for_completion_trigger()
        # Schedule block change detection debounce (P2-03)
        try:
            self._schedule_block_check()
        except Exception:
            pass

    def inputMethodEvent(self, event: QInputMethodEvent):
        """Ensure IME composition/commit also triggers snapshot and completion checks (ST-08)."""
        # Capture snapshot before the IME commits text
        try:
            self._capture_snapshot_pre_edit()
        except Exception:
            pass
        super().inputMethodEvent(event)
        self._check_for_completion_trigger()
        try:
            self._schedule_block_check()
        except Exception:
            pass

    def focusOutEvent(self, event):
        """On focus loss: hide completion popup, and if {{...}} was modified, default to '转为新块'."""
        self.completer.popup().hide()
        try:
            if getattr(self, "_block_overlay", None) and self._block_overlay.isVisible():
                if getattr(self, "_block_dirty", False):
                    self._on_overlay_new_block_clicked()
                else:
                    self._hide_block_overlay(reset_state=False)
        except Exception:
            try:
                self._hide_block_overlay(reset_state=False)
            except Exception:
                pass
        super().focusOutEvent(event)

    def focusInEvent(self, event):
        """Broadcast active page when the editor gains focus (FR-2)."""
        super().focusInEvent(event)
        # ST-16: Suppress broadcast when no active vault
        if not getattr(self, "_has_active_vault", True):
            return
        # V0.4.6: Only broadcast panel context, not active_page_changed, to avoid global editor sync
        try:
            page_path = getattr(self, "current_file_path", "Note A.md")
        except Exception:
            page_path = "Note A.md"
        GlobalSignalBus.panel_context_changed.emit(page_path)

    @Slot(str)
    def on_active_page_changed(self, page_path: str):
        """
        ST-05: Load file content when the active page changes.
        Expects page_path to be vault-relative and include '.md'.
        V0.4.6: Only loads if _follow_global_active_page is True.
        """
        if not getattr(self, "_follow_global_active_page", True):
            return
        self._load_page_for_self(page_path)

    def _load_page_for_self(self, page_path: str):
        """
        V0.4.6: Internal method to load a page into this editor instance,
        without considering global active page following.
        """
        try:
            svc = getattr(getattr(self, "app_context", None), "file_indexer_service", None)
            vault = getattr(svc, "vault_path", ".")
            base = Path(vault) if vault else Path(".")
        except Exception:
            base = Path(".")
        try:
            abs_path = (base / page_path).resolve(strict=False)
            self._load_file(abs_path)
            self.current_file_path = page_path
            try:
                self.completer.popup().hide()
            except Exception:
                pass
            try:
                self._hide_block_overlay(reset_state=True)
            except Exception:
                pass
            try:
                self._update_parent_dock_title(page_path)
            except Exception:
                pass
            try:
                self._ensure_titlebar_installed()
            except Exception:
                pass
            # E1: Update autosave baseline hash after page load
            try:
                txt = self.toPlainText()
                self._last_saved_hash = hashlib.sha256((txt or "").encode("utf-8")).hexdigest()
            except Exception:
                self._last_saved_hash = None
        except Exception as e:
            logging.warning(f"Failed to load page '{page_path}' for self: {e}")
            try:
                self.setPlainText("")
            except Exception:
                pass

    def _update_parent_dock_title(self, page_path: str) -> None:
        try:
            title = Path(page_path).stem if page_path else ""
        except Exception:
            title = str(page_path or "")
        if not title:
            return
        try:
            w = self
            while w is not None:
                if isinstance(w, QDockWidget):
                    w.setWindowTitle(title)
                    break
                w = w.parentWidget()
        except Exception:
            pass

    def _ensure_titlebar_installed(self) -> None:
        try:
            w = self
            dock = None
            while w is not None:
                if isinstance(w, QDockWidget):
                    dock = w
                    break
                w = w.parentWidget()
            if dock is None:
                return
            tb = getattr(dock, "_ev_custom_titlebar", None)
            if not isinstance(tb, TitleBarWidget):
                tb = TitleBarWidget(dock, self)
                try:
                    dock.setTitleBarWidget(tb)
                except Exception:
                    pass
                dock._ev_custom_titlebar = tb
            try:
                title = dock.windowTitle()
            except Exception:
                title = ""
            if not title:
                try:
                    page_path = getattr(self, "current_file_path", "") or ""
                    title = Path(page_path).stem
                except Exception:
                    title = ""
            try:
                tb.set_title(title)
            except Exception:
                pass
        except Exception:
            pass

    def _begin_rename(self) -> None:
        try:
            self._ensure_titlebar_installed()
            w = self
            dock = None
            while w is not None:
                if isinstance(w, QDockWidget):
                    dock = w
                    break
                w = w.parentWidget()
            if dock and hasattr(dock, "_ev_custom_titlebar"):
                try:
                    dock._ev_custom_titlebar.enter_edit_mode()
                except Exception:
                    pass
        except Exception:
            pass

    def _commit_rename(self, new_name: str) -> bool:
        """
        Validate and enqueue a 'rename_file' task; optimistic UI update on success.
        Returns True if enqueued, else False.
        """
        try:
            old_rel = str(getattr(self, "current_file_path", "") or "").strip()
            if not old_rel:
                return False
            try:
                p_old = Path(old_rel)
                old_stem = p_old.stem
                old_dir = str(p_old.parent)
            except Exception:
                old_stem = Path(old_rel).stem
                old_dir = str(Path(old_rel).parent)

            new_name = (new_name or "").strip()
            if not new_name or new_name == old_stem:
                return False
            if re.search(r'[\/\\:\*\?"<>|]', new_name):
                return False
            if len(new_name) > 255:
                return False

            if old_dir in ("", "."):
                new_rel = f"{new_name}.md"
            else:
                new_rel = f"{old_dir.replace('\\', '/')}/{new_name}.md"

            svc = getattr(getattr(self, "app_context", None), "file_indexer_service", None)
            vault = getattr(svc, "vault_path", None)
            if not vault:
                logging.warning("rename_file: vault_path is missing; aborting and restoring UI")
                try:
                    self._update_parent_dock_title(old_rel)
                    self._ensure_titlebar_installed()
                except Exception:
                    pass
                return False

            src_abs = Path(vault) / old_rel
            dest_abs = Path(vault) / new_rel

            queued = False
            try:
                if svc and hasattr(svc, "task_queue") and getattr(svc, "task_queue"):
                    svc.task_queue.put({
                        "type": "rename_file",
                        "src_path": str(src_abs),
                        "dest_path": str(dest_abs),
                    })
                    queued = True
                else:
                    logging.warning("rename_file: task_queue unavailable; aborting and restoring UI")
            except Exception as e:
                logging.warning(f"rename_file enqueue failed: {e}")
                queued = False

            if not queued:
                try:
                    self._update_parent_dock_title(old_rel)
                    self._ensure_titlebar_installed()
                except Exception:
                    pass
                return False

            self.current_file_path = new_rel
            try:
                self._update_parent_dock_title(new_rel)
            except Exception:
                pass
            try:
                w = self
                dock = None
                while w is not None:
                    if isinstance(w, QDockWidget):
                        dock = w
                        break
                    w = w.parentWidget()
                if dock and hasattr(dock, "_ev_custom_titlebar"):
                    dock._ev_custom_titlebar.set_title(new_name)
            except Exception:
                pass
            return True
        except Exception as e:
            logging.warning(f"_commit_rename error: {e}")
            try:
                self._update_parent_dock_title(getattr(self, "current_file_path", ""))
                self._ensure_titlebar_installed()
            except Exception:
                pass
            return False

    @Slot(bool, str)
    def on_vault_state_changed(self, has_vault: bool, vault_path: str):
        """ST-16: Toggle editor behaviors when vault availability changes."""
        try:
            self._has_active_vault = bool(has_vault)
            self._completion_enabled = bool(has_vault)
        except Exception:
            self._has_active_vault = bool(has_vault)
            self._completion_enabled = bool(has_vault)
        # Always hide completion popup when state flips
        try:
            self.completer.popup().hide()
        except Exception:
            pass
        # Hide any block overlay
        try:
            self._hide_block_overlay(reset_state=True)
        except Exception:
            pass
        if not has_vault:
            # E1: Stop autosave and clear baseline when vault disabled
            try:
                if hasattr(self, "_autosave_timer") and self._autosave_timer:
                    self._autosave_timer.stop()
            except Exception:
                pass
            try:
                self._last_saved_hash = None
            except Exception:
                pass
            # Read-only and welcome banner
            try:
                self.setReadOnly(True)
            except Exception:
                pass
            try:
                self.setPlainText("欢迎使用EvoNote，请通过 工具栏->库管理 选择你的某个文件夹为库")
            except Exception:
                pass
        else:
            # Re-enable editing; do not force-load any page here.
            try:
                self.setReadOnly(False)
            except Exception:
                pass
 
    def _load_file(self, abs_path: Path):
        """Read UTF-8 file and set editor content. On error, clear content; never crash."""
        text = ""
        try:
            with open(abs_path, "r", encoding="utf-8") as f:
                text = f.read()
        except FileNotFoundError:
            # Allow empty new files
            text = ""
        except Exception as e:
            logging.warning(f"Error reading '{abs_path}': {e}")
            text = ""
        self.setPlainText(text)
        try:
            self._schedule_render_update()
        except Exception:
            pass
 
    @Slot()
    def _on_contents_changed(self):
        """
        This slot is called every time the text content of the editor changes.
        """
        # First, handle the AST parsing for the entire document.
        full_text = self.toPlainText()
        try:
            ast = parse_markdown(full_text)
        except Exception as e:
            pass

        # Debounced semantic rendering update for [[links]]
        self._schedule_render_update()

        # Log current token context for diagnostics
        cursor = self.textCursor()
        current_line_text = cursor.block().text()[:cursor.positionInBlock()]
        logging.info(f"contentsChanged; current_line_text='{current_line_text}'")
        

        self._check_for_completion_trigger()

        # Schedule block change detection debounce (P2-03)
        try:
            self._schedule_block_check()
        except Exception:
            pass

        # E1: Debounced auto-save scheduling
        try:
            self._schedule_autosave()
        except Exception:
            pass

    def _check_for_completion_trigger(self):
        """Checks if the text around the cursor should trigger a completion."""
        try:
            # ST-16: Disable completion when no active vault
            if not getattr(self, "_completion_enabled", True):
                try:
                    self.completer.popup().hide()
                except Exception:
                    pass
                self.last_completion_prefix = None
                return

            cursor = self.textCursor()
            if cursor is None:
                # No cursor available; hide UI and bail
                try:
                    self.completer.popup().hide()
                except Exception:
                    pass
                self.last_completion_prefix = None
                return

            # Guard against invalid positionInBlock and block access
            try:
                block = cursor.block()
                line_text = block.text() if block is not None else ""
                pos_in_block = cursor.positionInBlock()
                if not isinstance(pos_in_block, int):
                    pos_in_block = 0
                pos_in_block = max(0, min(pos_in_block, len(line_text)))
                current_line_text = line_text[:pos_in_block]
            except Exception:
                current_line_text = ""

            # Detect both triggers and choose the one closest to caret
            page_link_match = re.search(r'\[\[([^\[\]]*)$', current_line_text)
            content_block_match = re.search(r'\{\{([^\{\}]*)$', current_line_text)

            active_match = None
            completion_type = None
            if page_link_match or content_block_match:
                idx_page = page_link_match.start(0) if page_link_match else -1
                idx_block = content_block_match.start(0) if content_block_match else -1
                if idx_block > idx_page:
                    active_match = content_block_match
                    completion_type = 'content_block'
                elif idx_page > idx_block:
                    active_match = page_link_match
                    completion_type = 'page_link'
                else:
                    active_match = None
                    completion_type = None

            if active_match and completion_type:
                try:
                    prefix = active_match.group(1) or ""
                except Exception:
                    prefix = ""

                # Safety guards
                if ("\n" in prefix) or (len(prefix) > 128):
                    try:
                        self.completer.popup().hide()
                    except Exception:
                        pass
                    self.last_completion_prefix = None
                    return

                logging.info(f"Completion trigger activated: type='{completion_type}', prefix='{prefix}'")

                # Emit search request if the prefix has changed
                if prefix != self.last_completion_prefix:
                    if prefix.strip():
                        GlobalSignalBus.completion_requested.emit(completion_type, prefix)
                    self.last_completion_prefix = prefix

                try:
                    self.completer.setCompletionPrefix(prefix)
                except Exception:
                    # If completer fails, just hide and continue
                    try:
                        self.completer.popup().hide()
                    except Exception:
                        pass
                    self.last_completion_prefix = None
                    return

                self._update_popup_size()
                try:
                    self.completer.complete(self.cursorRect(cursor))
                except Exception:
                    # Popup failure should not affect document content
                    try:
                        self.completer.popup().hide()
                    except Exception:
                        pass
            else:
                # If no pattern matches, hide the popup
                if self.completer.popup().isVisible():
                    try:
                        self.completer.popup().hide()
                    except Exception:
                        pass
                self.last_completion_prefix = None
        except Exception as e:
            logging.warning(f"_check_for_completion_trigger guarded failure: {e}")
            try:
                self.completer.popup().hide()
            except Exception:
                pass
            self.last_completion_prefix = None
            return

    def _update_popup_size(self, strings=None):
        """Adjust the completer popup width based on content."""
        try:
            if strings is None:
                strings = self.completion_model.stringList()
            fm = self.fontMetrics()
            max_w = 0
            for s in strings or []:
                max_w = max(max_w, fm.horizontalAdvance(s))
            # Apply reasonable bounds
            width = max(240, min(600, max_w + 24))
            popup = self.completer.popup()
            popup.setMinimumWidth(width)
        except Exception:
            # Non-fatal sizing issue; ignore
            pass

    @Slot(str, str, list)
    def _on_completion_results_ready(self, completion_type, query_text, results):
        logging.info(f"Received completion results: type={completion_type}, count={len(results)}")
        # ST-16: Ignore completion updates when disabled
        if not getattr(self, "_completion_enabled", True):
            try:
                self.completer.popup().hide()
            except Exception:
                pass
            return
        # FR-4.2: Reuse completion UI for both page links and content blocks
        if completion_type == 'page_link' or completion_type == 'content_block':
            self.completion_model.setStringList(results)
            logging.info(f"Completion model for '{completion_type}' updated with {self.completion_model.rowCount()} items.")
            self._update_popup_size(results)
            # Re-check trigger state before showing results to avoid flicker after closing braces
            self._check_for_completion_trigger()
            if self.last_completion_prefix is not None:
                try:
                    self.completer.complete(self.cursorRect(self.textCursor()))
                except Exception:
                    try:
                        self.completer.popup().hide()
                    except Exception:
                        pass
    
    @Slot(str)
    def insert_completion(self, completion_text):
        """Inserts the selected completion into the text."""
        cursor = self.textCursor()
        
        text_before_cursor = cursor.block().text()[:cursor.positionInBlock()]
        # Check for both page link and content block patterns
        page_link_match = re.search(r'\[\[([^\]\[]*)$', text_before_cursor)
        content_block_match = re.search(r'\{\{([^\{\}]*)$', text_before_cursor)

        match = page_link_match or content_block_match
        
        if match:
            start_pos = match.start(0)
            # Determine the correct wrapper based on which pattern matched
            if page_link_match:
                left, right = "[[", "]]"
            else:
                left, right = "{{", "}}"

            # Select the text from the trigger start to the cursor
            cursor.movePosition(QTextCursor.StartOfBlock)
            cursor.movePosition(QTextCursor.Right, n=start_pos)
            cursor.movePosition(
                QTextCursor.Right,
                QTextCursor.KeepAnchor,
                len(text_before_cursor) - start_pos
            )
            
            # Insert the completed text with the correct wrapper
            cursor.insertText(f"{left}{completion_text}{right}")
            self.setTextCursor(cursor)
            self.completer.popup().hide()

    # --- Content Block Sync UI (V0.4.5) ---

    def _capture_snapshot_pre_edit(self):
        """Capture original content and hash of the {{...}} block under caret before edit (P2-02)."""
        text = self.toPlainText()
        pos = self.textCursor().position()
        span = self._find_block_span_at_pos(pos, text)
        if not span:
            # Left any block; clear state and hide overlay
            self._active_block = None
            self._hide_block_overlay(reset_state=False)
            return
        start, end, content = span
        # If we are still in the same block (identified by start), do not overwrite the original snapshot
        if self._active_block and self._active_block.get("start") == start:
            return
        self._active_block = {
            "start": start,
            "end": end,
            "original_content": content,
            "original_hash": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        }
        # Any new block snapshot should hide stale overlay
        self._hide_block_overlay(reset_state=False)

    def _schedule_block_check(self):
        """Debounce block modification detection (P2-03)."""
        if not self._active_block:
            self._hide_block_overlay(reset_state=False)
            return
        text = self.toPlainText()
        pos = self.textCursor().position()
        span = self._find_block_span_at_pos(pos, text)
        if not span:
            # Leaving the block; if modified, default to '转为新块'
            if getattr(self, "_block_dirty", False):
                try:
                    self._on_overlay_new_block_clicked()
                except Exception:
                    self._hide_block_overlay(reset_state=True)
            else:
                self._hide_block_overlay(reset_state=True)
            return
        _, _, current_content = span
        if current_content != self._active_block.get("original_content", ""):
            try:
                self._block_timer.start(self._block_debounce_ms)
            except Exception:
                pass
        else:
            # No change; ensure overlay hidden
            try:
                self._block_timer.stop()
            except Exception:
                pass
            self._hide_block_overlay(reset_state=False)

    def _get_current_block_content_and_span(self):
        text = self.toPlainText()
        pos = self.textCursor().position()
        return self._find_block_span_at_pos(pos, text)

    def _find_block_span_at_pos(self, pos: int, text: str):
        """Return (start, end, content) for the {{...}} enclosing pos, else None."""
        for m in re.finditer(r"\{\{((?:.|\n)+?)\}\}", text, flags=re.DOTALL):
            if m.start() <= pos < m.end():
                return m.start(), m.end(), m.group(1)
        return None

    def _on_block_debounce_timeout(self):
        """After debounce, if block modified show overlay. '全局更新' is enabled only when meaningful."""
        if not self._active_block:
            return
        current = self._get_current_block_content_and_span()
        if not current:
            # caret moved away; if there is a pending modification, default to '转为新块'
            if getattr(self, "_block_dirty", False):
                try:
                    self._on_overlay_new_block_clicked()
                except Exception:
                    pass
            else:
                self._hide_block_overlay(reset_state=True)
            return
        _, _, current_content = current
        if current_content == self._active_block.get("original_content", ""):
            # no change
            try:
                self._block_dirty = False
            except Exception:
                pass
            self._hide_block_overlay(reset_state=False)
            return

        # Mark dirty and decide whether '全局更新' is meaningful
        try:
            self._block_dirty = True
        except Exception:
            pass

        old_hash = self._active_block.get("original_hash")
        refcount = 0
        try:
            refcount = self._query_block_reference_count(old_hash)
        except Exception as e:
            logging.warning(f"Refcount query failed: {e}")

        exists_elsewhere = False
        # Check if new content already exists as another block in DB
        try:
            if getattr(self, "_db_path", None):
                conn = sqlite3.connect(self._db_path)
                cur = conn.cursor()
                cur.execute("SELECT 1 FROM blocks WHERE content = ? LIMIT 1", (current_content,))
                exists_elsewhere = cur.fetchone() is not None
                conn.close()
        except Exception as e:
            logging.warning(f"Block existence query failed: {e}")
            exists_elsewhere = False

        # '全局更新' allowed only when referenced in more than one file and new content is not already an existing block
        try:
            self._sync_allowed = (refcount > 1) and (not exists_elsewhere)
        except Exception:
            self._sync_allowed = (refcount > 1) and (not exists_elsewhere)

        # Show overlay and update buttons
        self._show_block_overlay()
        try:
            if getattr(self, "_btn_sync", None):
                self._btn_sync.setEnabled(bool(self._sync_allowed))
                if not self._sync_allowed:
                    tip = "此修改不需要全局更新（引用过少或新内容已存在）。"
                else:
                    tip = "将把所有引用此块的文件同步为当前内容。"
                try:
                    self._btn_sync.setToolTip(tip)
                except Exception:
                    pass
        except Exception:
            pass

    def _query_block_reference_count(self, block_hash: str) -> int:
        """Return COUNT(DISTINCT file_path) from block_instances (P2-04)."""
        if not block_hash or not getattr(self, "_db_path", None):
            return 0
        try:
            conn = sqlite3.connect(self._db_path)
            cur = conn.cursor()
            cur.execute("SELECT COUNT(DISTINCT file_path) FROM block_instances WHERE block_hash = ?", (block_hash,))
            row = cur.fetchone()
            conn.close()
            return int(row[0]) if row and row[0] is not None else 0
        except Exception as e:
            logging.warning(f"Failed to query block_instances: {e}")
            return 0

    def _show_block_overlay(self):
        """Create and show semi-transparent overlay with three actions (P2-05/06/07/08/09)."""
        if self._block_overlay is None:
            w = QWidget(self.viewport())
            w.setAttribute(Qt.WA_StyledBackground, True)
            w.setStyleSheet("background: rgba(32,32,32,0.75); border-radius: 6px;")
            layout = QHBoxLayout(w)
            layout.setContentsMargins(8, 4, 8, 4)
            layout.setSpacing(8)

            btn_sync = QPushButton("全局更新", w)
            btn_new = QPushButton("转为新块", w)
            btn_cancel = QPushButton("取消", w)
            for b in (btn_sync, btn_new, btn_cancel):
                b.setCursor(Qt.PointingHandCursor)
                b.setStyleSheet("QPushButton { color: #fafafa; background: rgba(0,0,0,0.2); border: 1px solid rgba(255,255,255,0.2); padding: 4px 8px; border-radius: 4px; } QPushButton:hover { background: rgba(255,255,255,0.15); }")

            layout.addWidget(btn_sync)
            layout.addWidget(btn_new)
            layout.addWidget(btn_cancel)

            btn_cancel.clicked.connect(self._on_overlay_cancel_clicked)
            btn_new.clicked.connect(self._on_overlay_new_block_clicked)
            btn_sync.clicked.connect(self._on_overlay_sync_clicked)

            self._block_overlay = w
            # keep button refs for state updates
            self._btn_sync = btn_sync
            self._btn_new = btn_new
            self._btn_cancel = btn_cancel

        # Update '全局更新' enabled state every time we show it
        try:
            if getattr(self, "_btn_sync", None) is not None:
                self._btn_sync.setEnabled(bool(getattr(self, "_sync_allowed", False)))
        except Exception:
            pass

        self._block_overlay.show()
        self._reposition_overlay()

    def _reposition_overlay(self):
        """Anchor overlay to just below the end of the modified block (P2-05)."""
        try:
            if not self._block_overlay or not self._block_overlay.isVisible() or not self._active_block:
                return
            # Use current block end
            span = self._get_current_block_content_and_span()
            if not span:
                return
            start, end, _ = span
            c = QTextCursor(self.document())
            c.setPosition(end)
            rect = self.cursorRect(c)
            x = max(4, rect.left())
            y = rect.bottom() + 6
            # Clamp within viewport
            vp = self.viewport().rect()
            ow = self._block_overlay.sizeHint().width()
            oh = self._block_overlay.sizeHint().height()
            if x + ow > vp.right() - 4:
                x = max(4, vp.right() - ow - 4)
            if y + oh > vp.bottom() - 4:
                y = max(4, vp.bottom() - oh - 4)
            self._block_overlay.move(x, y)
        except Exception:
            pass

    def _hide_block_overlay(self, reset_state: bool = False):
        try:
            if self._block_overlay:
                self._block_overlay.hide()
        except Exception:
            pass
        if reset_state:
            self._active_block = None
            try:
                self._block_dirty = False
            except Exception:
                pass

    def _replace_current_block_text(self, new_content: str):
        """Replace the current block's content with new_content (without braces management outside)."""
        span = self._get_current_block_content_and_span()
        if not span:
            return
        start, end, _ = span
        c = QTextCursor(self.document())
        c.setPosition(start)
        c.setPosition(end, QTextCursor.KeepAnchor)
        c.insertText("{{" + new_content + "}}")
        self.setTextCursor(c)

    def resizeEvent(self, event):
        """Ensure overlay follows when the editor is resized (P2-10)."""
        super().resizeEvent(event)
        self._reposition_overlay()

    def _on_overlay_cancel_clicked(self):
        """[取消]: revert block to original content and hide overlay (P2-06)."""
        try:
            if self._active_block:
                self._replace_current_block_text(self._active_block.get("original_content", ""))
        except Exception as e:
            logging.warning(f"Cancel revert failed: {e}")
        self._hide_block_overlay(reset_state=True)
        # Persist the revert immediately
        try:
            self._perform_autosave()
        except Exception:
            pass

    def _on_overlay_new_block_clicked(self):
        """[转为新块]: accept current edits and hide overlay (P2-07, default safe behavior)."""
        self._hide_block_overlay(reset_state=True)
        # Persist accepted edits
        try:
            self._perform_autosave()
        except Exception:
            pass

    def _on_overlay_sync_clicked(self):
        """[全局更新]: enqueue 'sync_block' task with old_hash and new_content (P2-08)."""
        try:
            # Safety: if not allowed, ignore click gracefully
            if not bool(getattr(self, "_sync_allowed", False)):
                self._hide_block_overlay(reset_state=True)
                return
            current = self._get_current_block_content_and_span()
            if not current or not self._active_block:
                self._hide_block_overlay(reset_state=True)
                return
            _, _, new_content = current
            old_hash = self._active_block.get("original_hash")
            svc = getattr(getattr(self, "app_context", None), "file_indexer_service", None)
            if svc and hasattr(svc, "task_queue"):
                svc.task_queue.put({"type": "sync_block", "old_hash": old_hash, "new_content": new_content})
                logging.info(f"Enqueued sync_block task for {old_hash[:8]}...")
        except Exception as e:
            logging.warning(f"Failed to enqueue sync_block: {e}")
        self._hide_block_overlay(reset_state=True)
        # Persist local file after enqueuing sync
        try:
            self._perform_autosave()
        except Exception:
            pass

    # --- Live Semantic Rendering for [[Page Links]] ---
    def _schedule_render_update(self):
        """Debounced schedule to recompute and apply link selections."""
        try:
            # 80ms debounce to ensure no typing lag (NFR-1)
            self._render_timer.start(80)
        except Exception:
            # timer might not be ready during early construction
            pass

    def _recompute_and_apply_link_selections(self):
        """Scan document for [[links]] and apply ExtraSelections with distinct style."""
        full_text = self.toPlainText()

        # Extract link spans across entire document using a lightweight regex
        # Pattern: [[...]] without nested brackets and across a single line
        self._link_regions = []
        selections = []

        fmt = QTextCharFormat()
        fmt.setForeground(QColor(30, 136, 229))  # Distinct blue
        fmt.setFontUnderline(True)               # Underline to imply interactivity

        for m in re.finditer(r'\[\[([^\[\]\n]+?)\]\]', full_text):
            start = m.start()
            end = m.end()
            title = m.group(1).strip()
            self._link_regions.append({"start": start, "end": end, "title": title})

            sel = QTextEdit.ExtraSelection()
            c = QTextCursor(self.document())
            c.setPosition(start)
            c.setPosition(end, QTextCursor.KeepAnchor)
            sel.cursor = c
            sel.format = fmt
            selections.append(sel)

        # Apply all link selections at once
        self.setExtraSelections(selections)

    def _hit_test_link(self, doc_pos: int):
        """Return link span dict if document position hits a link, else None."""
        for span in self._link_regions:
            if span["start"] <= doc_pos < span["end"]:
                return span
        return None

    def mouseMoveEvent(self, event):
        """Hover effect: switch cursor to pointing hand when over a link."""
        # ST-16: Disable link hover interactivity when no active vault
        if not getattr(self, "_has_active_vault", True):
            try:
                self.viewport().setCursor(Qt.IBeamCursor)
            except Exception:
                pass
            super().mouseMoveEvent(event)
            return
        try:
            pt = event.position().toPoint()
        except AttributeError:
            pt = event.pos()
        cur = self.cursorForPosition(pt)
        hit = self._hit_test_link(cur.position())
        if hit:
            self.viewport().setCursor(Qt.PointingHandCursor)
        else:
            self.viewport().setCursor(Qt.IBeamCursor)
        super().mouseMoveEvent(event)

    def _resolve_and_ensure_page_local(self, path_or_title: str) -> tuple[str, str]:
        """
        V0.4.6: Local version of _resolve_and_ensure_page, for internal editor use.
        Avoids circular dependency on EvoNoteApp.
        """
        # Base vault path
        base = getattr(getattr(self, "app_context", None), "file_indexer_service", None)
        base = getattr(base, "vault_path", Path("."))
        if not isinstance(base, Path):
            base = Path(str(base or "."))

        txt = str(path_or_title or "").strip()
        if not txt:
            txt = "Untitled"

        p = Path(txt)
        has_ext = p.suffix.lower() == ".md"
        first_seg = (p.parts[0].lower() if p.parts else "")

        if has_ext or first_seg == "pages":
            if not has_ext:
                p = p.with_suffix(".md")
        else:
            p = Path("pages") / p
            if p.suffix.lower() != ".md":
                p = p.with_suffix(".md")

        abs_path = (base / p).resolve(strict=False)

        try:
            rel_path = abs_path.relative_to(base)
        except Exception:
            rel_path = Path(os.path.relpath(str(abs_path), start=str(base)))
        rel_str = rel_path.as_posix()

        if not abs_path.exists():
            try:
                abs_path.parent.mkdir(parents=True, exist_ok=True)
                with open(abs_path, "w", encoding="utf-8", newline="") as f:
                    f.write("")
                logging.info(f"INFO: Created new page at {abs_path}")
            except Exception as e:
                raise RuntimeError(f"Failed to create page file: {abs_path} ({e})")

        return str(abs_path), rel_str

    def _navigate_locally_to(self, page_title: str):
        """
        V0.4.6: Handle navigation within this editor instance only.
        """
        try:
            abs_path, rel_path = self._resolve_and_ensure_page_local(page_title)
            # Enqueue index update to reflect potential creation/update
            try:
                svc = getattr(getattr(self, "app_context", None), "file_indexer_service", None)
                if svc and hasattr(svc, "task_queue"):
                    svc.task_queue.put({"type": "upsert", "path": str(abs_path)})
            except Exception as e:
                logging.warning(f"WARNING: Failed to enqueue upsert for {abs_path}: {e}")
            
            self._load_page_for_self(rel_path)
            GlobalSignalBus.panel_context_changed.emit(rel_path) # Update panels
        except Exception as e:
            logging.warning(f"ERROR: Local navigation failed for '{page_title}': {e}")

    def mousePressEvent(self, event):
        """Click handling: default to '新块' if clicking elsewhere while overlay visible; navigate on [[link]] click."""
        # ST-16: Block all interactions when no active vault
        if not getattr(self, "_has_active_vault", True):
            try:
                self.completer.popup().hide()
            except Exception:
                pass
            try:
                self._hide_block_overlay(reset_state=True)
            except Exception:
                pass
            event.accept()
            return
        if event.button() == Qt.LeftButton:
            try:
                pt_editor = event.position().toPoint()
            except AttributeError:
                pt_editor = event.pos()

            # Map to viewport coordinates for overlay hit testing
            try:
                pt_vp = self.viewport().mapFrom(self, pt_editor)
            except Exception:
                pt_vp = pt_editor

            # P2-09: Default to '转为新块' when clicking outside the overlay
            try:
                if getattr(self, "_block_overlay", None) and self._block_overlay.isVisible():
                    if not self._block_overlay.geometry().contains(pt_vp):
                        self._on_overlay_new_block_clicked()
            except Exception:
                pass

            doc_pos = self.cursorForPosition(pt_editor).position()
            hit = self._hit_test_link(doc_pos)
            if hit:
                # Do not move caret; open in new window on Shift+Click, otherwise navigate in current editor.
                try:
                    mods = event.modifiers()
                except Exception:
                    mods = Qt.NoModifier
                if mods & Qt.ShiftModifier:
                    GlobalSignalBus.page_open_requested.emit(hit["title"])
                elif getattr(self, "_handle_navigation_locally", False): # V0.4.6: Local navigation
                    self._navigate_locally_to(hit["title"])
                else:
                    GlobalSignalBus.page_navigation_requested.emit(hit["title"])
                event.accept()
                return
        super().mousePressEvent(event)

    # --- E1: Auto-save debounce and atomic write ---
    def _schedule_autosave(self):
        try:
            # Gate scheduling while there is a pending block edit/overlay
            try:
                if getattr(self, "_block_dirty", False) or (getattr(self, "_block_overlay", None) and self._block_overlay.isVisible()):
                    return
            except Exception:
                pass
            if not getattr(self, "_has_active_vault", False):
                return
            rel = (getattr(self, "current_file_path", "") or "").strip()
            if not rel:
                return
            t = getattr(self, "_autosave_timer", None)
            if not t:
                return
            try:
                t.stop()
            except Exception:
                pass
            try:
                interval = int(getattr(self, "_autosave_interval_ms", 800) or 800)
            except Exception:
                interval = 800
            try:
                t.start(interval)
            except Exception:
                pass
        except Exception as e:
            logging.warning(f"_schedule_autosave guarded failure: {e}")

    def _perform_autosave(self):
        try:
            # Gate autosave during pending block edits/overlay
            try:
                if getattr(self, "_block_dirty", False) or (getattr(self, "_block_overlay", None) and self._block_overlay.isVisible()):
                    return
            except Exception:
                pass
            if not getattr(self, "_has_active_vault", False):
                return
            rel = (getattr(self, "current_file_path", "") or "").strip()
            if not rel:
                return

            svc = getattr(getattr(self, "app_context", None), "file_indexer_service", None)
            vault = getattr(svc, "vault_path", None)
            if not vault:
                return
            try:
                base = Path(vault)
            except Exception:
                base = Path(str(vault))
            abs_path = base / rel

            # Ensure directory exists
            try:
                abs_path.parent.mkdir(parents=True, exist_ok=True)
            except Exception:
                pass

            txt = self.toPlainText()
            try:
                new_hash = hashlib.sha256((txt or "").encode("utf-8")).hexdigest()
            except Exception:
                new_hash = None

            if new_hash and new_hash == getattr(self, "_last_saved_hash", None):
                return

            wrote = False
            try:
                if svc and hasattr(svc, "_atomic_write"):
                    svc._atomic_write(abs_path, txt)
                    wrote = True
            except Exception as e:
                logging.warning(f"autosave atomic_write failed: {e}")
                wrote = False

            if not wrote:
                try:
                    with open(abs_path, "w", encoding="utf-8", newline="") as f:
                        f.write(txt)
                    wrote = True
                except Exception as e:
                    logging.warning(f"autosave fallback write failed for {abs_path}: {e}")
                    wrote = False

            if wrote:
                try:
                    self._last_saved_hash = new_hash
                except Exception:
                    pass
                try:
                    if svc and hasattr(svc, "task_queue") and getattr(svc, "task_queue"):
                        svc.task_queue.put({"type": "upsert", "path": str(abs_path)})
                except Exception as e:
                    logging.warning(f"autosave enqueue upsert failed: {e}")
        except Exception as e:
            logging.warning(f"_perform_autosave guarded failure: {e}")

class EditableEditorPlugin(EditorPluginInterface):
    def __init__(self, app):
        self.app = app

    @property
    def name(self) -> str:
        return "Reactive Editor"

    @property
    def description(self) -> str:
        return "A robust, reactive editor core based on Qt's native engine."

    def get_widget(self) -> QWidget:
        """
        Creates and returns the editor widget, wrapped in a QDockWidget.
        """
        dock_widget = QDockWidget(self.name)
        editor = ReactiveEditor()
        # P2-01: Inject AppContext and db_path for block reference counting
        try:
            editor.app_context = getattr(self.app, 'app_context', None)
            if editor.app_context and getattr(editor.app_context, 'file_indexer_service', None):
                editor._db_path = str(editor.app_context.file_indexer_service.db_path)
            # ST-16: Initialize editor vault state based on current AppContext
            try:
                cp = getattr(editor.app_context, 'current_vault_path', None) if editor.app_context else None
                editor.on_vault_state_changed(bool(cp), str(cp) if cp else "")
            except Exception:
                pass
        except Exception as e:
            logging.warning(f"Failed to inject app context into editor: {e}")
        dock_widget.setWidget(editor)
        return dock_widget

def create_plugin(app):
    """Plugin entry point."""
    return EditableEditorPlugin(app)