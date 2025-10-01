# plugins/editable_editor/main.py
from PySide6.QtWidgets import QPlainTextEdit, QWidget, QDockWidget
from PySide6.QtCore import Slot
from plugins.editor_plugin_interface import EditorPluginInterface
from core.parsing_service import parse_markdown

class ReactiveEditor(QPlainTextEdit):
    """
    A reactive editor that leverages Qt's native text editing engine.
    It listens for content changes and triggers AST parsing in the background.
    """
    def __init__(self):
        super().__init__()
        
        # Connect the document's contentsChanged signal to our slot.
        # This is the core of the reactive architecture.
        self.document().contentsChanged.connect(self._on_contents_changed)
        
        # Set some initial text for demonstration purposes.
        self.setPlainText("# Welcome to EvoNote\n\nStart typing...")

    @Slot()
    def _on_contents_changed(self):
        """
        This slot is called every time the text content of the editor changes.
        """
        full_text = self.toPlainText()
        try:
            # Pass the full text to the parsing service to get the latest AST.
            ast = parse_markdown(full_text)
            print(f"AST updated. Token count: {len(ast)}")
        except Exception as e:
            # It's good practice to catch potential parsing errors.
            print(f"Error parsing markdown: {e}")

class EditableEditorPlugin(EditorPluginInterface):
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