# plugins/editable_editor/main.py
import re
import logging
from PySide6.QtWidgets import QPlainTextEdit, QWidget, QDockWidget, QCompleter
from PySide6.QtCore import Slot, Qt, QStringListModel
from PySide6.QtGui import QKeyEvent, QTextCursor
from plugins.editor_plugin_interface import EditorPluginInterface
from core.parsing_service import parse_markdown
from core.signals import GlobalSignalBus


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
        
        self.setPlainText("# Welcome to EvoNote\n\nStart typing...")
        self.last_completion_prefix = None

    def keyPressEvent(self, event: QKeyEvent):
        if self.completer.popup().isVisible():
            if event.key() in (Qt.Key_Enter, Qt.Key_Return, Qt.Key_Tab, Qt.Key_Backtab):
                event.ignore()
                return

        super().keyPressEvent(event)
        # Also trigger completion check from key event to be robust
        self._check_for_completion_trigger()

    def focusOutEvent(self, event):
        """Hide completion popup when the editor loses focus."""
        self.completer.popup().hide()
        super().focusOutEvent(event)

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

        # Log current token context for diagnostics
        cursor = self.textCursor()
        current_line_text = cursor.block().text()[:cursor.positionInBlock()]
        logging.info(f"contentsChanged; current_line_text='{current_line_text}'")
        
        self._check_for_completion_trigger()

    def _check_for_completion_trigger(self):
        """Checks if the text around the cursor should trigger a completion."""
        cursor = self.textCursor()
        current_line_text = cursor.block().text()[:cursor.positionInBlock()]
        
        match = re.search(r'\[\[([^\]\[]*)$', current_line_text)

        if match:
            prefix = match.group(1)
            logging.info(f"trigger: prefix='{prefix}'")
            # Emit search request whenever prefix changes and is non-empty
            if prefix != (self.last_completion_prefix or ""):
                if prefix.strip():
                    logging.info(f"emit completion_requested for prefix='{prefix}'")
                    GlobalSignalBus.completion_requested.emit('page_link', prefix)
                self.last_completion_prefix = prefix

            self.completer.setCompletionPrefix(prefix)
            # Adjust popup size and show near the cursor
            self._update_popup_size()
            self.completer.complete(self.cursorRect(cursor))
        else:
            # Hide popup and reset prefix tracking when pattern no longer matches
            if self.completer.popup().isVisible():
                 self.completer.popup().hide()
            self.last_completion_prefix = None

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
        if completion_type == 'page_link':
            self.completion_model.setStringList(results)
            logging.info(f"Completion model updated with {self.completion_model.rowCount()} items.")
            self._update_popup_size(results)
            # Force popup refresh with fresh data at current caret
            self.completer.complete(self.cursorRect(self.textCursor()))
            # Also re-check trigger to keep state in sync
            self._check_for_completion_trigger()
    
    @Slot(str)
    def insert_completion(self, completion_text):
        """Inserts the selected completion into the text."""
        cursor = self.textCursor()
        
        text_before_cursor = cursor.block().text()[:cursor.positionInBlock()]
        match = re.search(r'\[\[([^\]\[]*)$', text_before_cursor)

        if match:
            start_pos_in_block = match.start(0)
            
            cursor.movePosition(QTextCursor.StartOfBlock)
            cursor.movePosition(QTextCursor.Right, n=start_pos_in_block)
            
            length_to_select = len(text_before_cursor) - start_pos_in_block
            cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, length_to_select)
            
            cursor.insertText(f"[[{completion_text}]]")
            self.completer.popup().hide()

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
        dock_widget.setWidget(editor)
        return dock_widget

def create_plugin(app):
    """Plugin entry point."""
    return EditableEditorPlugin(app)