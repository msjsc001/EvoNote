from PySide6.QtGui import QTextDocument, QTextCursor, QTextBlockFormat, QTextCharFormat, QFont

class RenderingService:
    def render(self, document_model) -> QTextDocument:
        """
        Builds a QTextDocument from a list of markdown-it-py AST tokens.

        This function processes paragraph and heading tokens to construct a
        rich text document. All other token types are ignored as per the
        V0.3.1 SRS.

        Args:
            document_model: A Document object containing the AST.

        Returns:
            A QTextDocument object representing the rendered AST.
        """
        document = QTextDocument()
        cursor = QTextCursor(document)
        
        # Ensure the document is not empty to start with
        cursor.insertBlock()

        token_iterator = iter(document_model.ast)

        for token in token_iterator:
            if token.type == 'paragraph_open':
                # Find the corresponding inline token
                inline_token = next(token_iterator, None)
                if inline_token and inline_token.type == 'inline':
                    cursor.insertText(inline_token.content)
                # The next token should be paragraph_close, which we can skip
                next(token_iterator, None)
                # Insert a new block for the next content
                cursor.insertBlock()

            elif token.type == 'heading_open':
                level = int(token.tag[1:])  # h1 -> 1, h2 -> 2, etc.
                
                # Create block format for heading
                block_format = QTextBlockFormat()
                
                # Create char format for heading
                char_format = QTextCharFormat()
                font = QFont()
                font.setBold(True)
                # Set font size based on heading level (h1 largest, h6 smallest)
                font.setPointSize(28 - level * 2)
                char_format.setFont(font)
                
                # Apply formats
                cursor.setBlockFormat(block_format)
                cursor.setCharFormat(char_format)
                
                # Find the corresponding inline token for the heading content
                inline_token = next(token_iterator, None)
                if inline_token and inline_token.type == 'inline':
                    cursor.insertText(inline_token.content)
                
                # The next token should be heading_close, which we can skip
                next(token_iterator, None)
                
                # Reset formats and insert a new block for subsequent content
                cursor.setCharFormat(QTextCharFormat())
                cursor.insertBlock()
                
        # Remove the last empty block if it exists
        if document.lastBlock().length() == 0:
            cursor.movePosition(QTextCursor.MoveOperation.End)
            cursor.deletePreviousChar()


        return document

# Create a singleton instance of the service for plugins to import
rendering_service = RenderingService()
