from PySide6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont, QFontDatabase
from PySide6.QtCore import QRegularExpression, Qt

class LivePreviewHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None, editor=None, colors=None):
        super().__init__(parent)
        self.editor = editor
        self.colors = colors or {}
        
        # Formats
        self.fmt_transparent = QTextCharFormat()
        self.fmt_transparent.setForeground(Qt.transparent)
        self.fmt_transparent.setFontPointSize(1)  # Shrink to collapse space

        self.fmt_bold = QTextCharFormat()
        self.fmt_bold.setFontWeight(QFont.Bold)
        self.fmt_bold.setForeground(QColor("#FFFFFF"))  # Pure white for emphasis

        self.fmt_header = QTextCharFormat()
        self.fmt_header.setFontWeight(QFont.Bold)
        self.fmt_header.setForeground(QColor(self.colors.get("h1", "#FF79C6")))
        # Note: altering font size in highlighter is possible but can cause line-height jitters
        # We will try setting it slightly larger.
        self.fmt_header.setFontPointSize(16) 

        self.fmt_dim = QTextCharFormat()
        self.fmt_dim.setForeground(QColor(self.colors.get("dim", "#808080")))
    
    def _cursor_in_range(self, match_start: int, match_end: int) -> bool:
        """Check if cursor is within or adjacent to the given range (relative to block start)."""
        cursor = self.editor.textCursor()
        block = self.currentBlock()
        if cursor.blockNumber() != block.blockNumber():
            return False
        cursor_relative = cursor.position() - block.position()
        return match_start <= cursor_relative <= match_end
    
    def highlightBlock(self, text):
        # 1. Headers (# H1)
        # Pattern: ^(#+)\s+(.*)$
        match = QRegularExpression(r"^(#+)\s+(.*)$").match(text)
        if match.hasMatch():
            # Whole line is header?
            # We hide the # marks if cursor not in line
            hashes_len = match.capturedLength(1)
            is_active = self._cursor_in_range(match.capturedStart(), match.capturedEnd())
            
            if is_active:
                self.setFormat(match.capturedStart(1), hashes_len, self.fmt_dim)
                self.setFormat(match.capturedStart(2), match.capturedLength(2), self.fmt_header)
            else:
                # Hide hashes
                self.setFormat(match.capturedStart(1), hashes_len + 1, self.fmt_transparent) # +1 for space
                # Content in Header
                self.setFormat(match.capturedStart(2), match.capturedLength(2), self.fmt_header)
                
        # 2. Bold (**text**)
        # Pattern: (\*\*)(.+?)(\*\*)
        iter = QRegularExpression(r"(\*\*)(.+?)(\*\*)").globalMatch(text)
        while iter.hasNext():
            match = iter.next()
            
            # Element-level reveal: only show syntax if cursor is within THIS specific element
            is_active = self._cursor_in_range(match.capturedStart(), match.capturedEnd())
            
            if is_active:
                # Show source (Dim the syntax)
                self.setFormat(match.capturedStart(1), 2, self.fmt_dim)
                self.setFormat(match.capturedStart(3), 2, self.fmt_dim)
                self.setFormat(match.capturedStart(2), match.capturedLength(2), self.fmt_bold)
            else:
                # Hide syntax
                self.setFormat(match.capturedStart(1), 2, self.fmt_transparent)
                self.setFormat(match.capturedStart(3), 2, self.fmt_transparent)
                self.setFormat(match.capturedStart(2), match.capturedLength(2), self.fmt_bold)

        # 3. Links ([[Note Name]])
        # Pattern: (\[\[)(.+?)(\]\])
        self.fmt_link = QTextCharFormat()
        self.fmt_link.setForeground(QColor(self.colors.get("link", "#8BE9FD")))
        self.fmt_link.setUnderlineStyle(QTextCharFormat.SingleUnderline)
        
        iter_link = QRegularExpression(r"(\[\[)(.+?)(\]\])").globalMatch(text)
        while iter_link.hasNext():
            match = iter_link.next()
            is_active = self._cursor_in_range(match.capturedStart(), match.capturedEnd())
            
            if is_active:
                self.setFormat(match.capturedStart(1), 2, self.fmt_dim)
                self.setFormat(match.capturedStart(3), 2, self.fmt_dim)
                self.setFormat(match.capturedStart(2), match.capturedLength(2), self.fmt_link)
            else:
                self.setFormat(match.capturedStart(1), 2, self.fmt_transparent)
                self.setFormat(match.capturedStart(3), 2, self.fmt_transparent)
                self.setFormat(match.capturedStart(2), match.capturedLength(2), self.fmt_link)

        # 4. Blockquotes (> Text)
        # Pattern: ^(>\s+)(.*)$
        self.fmt_quote = QTextCharFormat()
        self.fmt_quote.setForeground(QColor(self.colors.get("quote", "#6272A4")))
        
        match_quote = QRegularExpression(r"^(>\s+)(.*)$").match(text)
        if match_quote.hasMatch():
            is_active = self._cursor_in_range(match_quote.capturedStart(), match_quote.capturedEnd())
            
            if is_active:
                self.setFormat(match_quote.capturedStart(1), match_quote.capturedLength(1), self.fmt_dim)
                self.setFormat(match_quote.capturedStart(2), match_quote.capturedLength(2), self.fmt_quote)
            else:
                # Hide the "> " logic?
                # Actually, for blockquotes, hiding "> " might make it look like normal text if we don't have a border.
                # Since we can't easily draw a border in QSyntaxHighlighter (needs QPainter in paintEvent),
                # We will just Dim the "> " extremely or make it a specific color, but NOT hide it completely for now
                # to avoid confusion. Or we can hide it and assume italic/gray is enough.
                # Let's hide it to be consistent with "Live Preview".
                self.setFormat(match_quote.capturedStart(1), match_quote.capturedLength(1), self.fmt_transparent)
                self.setFormat(match_quote.capturedStart(2), match_quote.capturedLength(2), self.fmt_quote)

        # 5. Italic (*text* or _text_) - Must run AFTER bold to avoid conflicts
        # Pattern: (?<!\*)(\*)([^\*]+?)(\*)(?!\*) and (?<!_)(_)([^_]+?)(_)(?!_)
        fmt_italic = QTextCharFormat()
        fmt_italic.setFontItalic(True)
        fmt_italic.setForeground(QColor("#E0E0E0"))
        
        # *italic* (single asterisk, not part of **)
        iter_italic = QRegularExpression(r"(?<!\*)(\*)([^\*]+?)(\*)(?!\*)").globalMatch(text)
        while iter_italic.hasNext():
            match = iter_italic.next()
            is_active = self._cursor_in_range(match.capturedStart(), match.capturedEnd())
            
            if is_active:
                self.setFormat(match.capturedStart(1), 1, self.fmt_dim)
                self.setFormat(match.capturedStart(3), 1, self.fmt_dim)
                self.setFormat(match.capturedStart(2), match.capturedLength(2), fmt_italic)
            else:
                self.setFormat(match.capturedStart(1), 1, self.fmt_transparent)
                self.setFormat(match.capturedStart(3), 1, self.fmt_transparent)
                self.setFormat(match.capturedStart(2), match.capturedLength(2), fmt_italic)

        # _italic_ (underscore)
        iter_italic_u = QRegularExpression(r"(?<!_)(_)([^_]+?)(_)(?!_)").globalMatch(text)
        while iter_italic_u.hasNext():
            match = iter_italic_u.next()
            is_active = self._cursor_in_range(match.capturedStart(), match.capturedEnd())
            
            if is_active:
                self.setFormat(match.capturedStart(1), 1, self.fmt_dim)
                self.setFormat(match.capturedStart(3), 1, self.fmt_dim)
                self.setFormat(match.capturedStart(2), match.capturedLength(2), fmt_italic)
            else:
                self.setFormat(match.capturedStart(1), 1, self.fmt_transparent)
                self.setFormat(match.capturedStart(3), 1, self.fmt_transparent)
                self.setFormat(match.capturedStart(2), match.capturedLength(2), fmt_italic)

        # 6. Strikethrough (~~text~~)
        fmt_strike = QTextCharFormat()
        fmt_strike.setFontStrikeOut(True)
        fmt_strike.setForeground(QColor("#808080"))
        
        iter_strike = QRegularExpression(r"(~~)(.+?)(~~)").globalMatch(text)
        while iter_strike.hasNext():
            match = iter_strike.next()
            is_active = self._cursor_in_range(match.capturedStart(), match.capturedEnd())
            
            if is_active:
                self.setFormat(match.capturedStart(1), 2, self.fmt_dim)
                self.setFormat(match.capturedStart(3), 2, self.fmt_dim)
                self.setFormat(match.capturedStart(2), match.capturedLength(2), fmt_strike)
            else:
                self.setFormat(match.capturedStart(1), 2, self.fmt_transparent)
                self.setFormat(match.capturedStart(3), 2, self.fmt_transparent)
                self.setFormat(match.capturedStart(2), match.capturedLength(2), fmt_strike)

        # 7. Inline Code (`code`)
        fmt_code = QTextCharFormat()
        fmt_code.setForeground(QColor(self.colors.get("code", "#F1FA8C")))
        fmt_code.setFontFamily("Consolas, Monaco, monospace")
        
        iter_code = QRegularExpression(r"(`)([^`]+)(`)").globalMatch(text)
        while iter_code.hasNext():
            match = iter_code.next()
            is_active = self._cursor_in_range(match.capturedStart(), match.capturedEnd())
            
            if is_active:
                self.setFormat(match.capturedStart(1), 1, self.fmt_dim)
                self.setFormat(match.capturedStart(3), 1, self.fmt_dim)
                self.setFormat(match.capturedStart(2), match.capturedLength(2), fmt_code)
            else:
                self.setFormat(match.capturedStart(1), 1, self.fmt_transparent)
                self.setFormat(match.capturedStart(3), 1, self.fmt_transparent)
                self.setFormat(match.capturedStart(2), match.capturedLength(2), fmt_code)

        # 8. Standard Links [text](url)
        fmt_url_link = QTextCharFormat()
        fmt_url_link.setForeground(QColor("#8BE9FD"))
        fmt_url_link.setUnderlineStyle(QTextCharFormat.SingleUnderline)
        
        iter_std_link = QRegularExpression(r"(\[)([^\]]+)(\])(\()([^\)]+)(\))").globalMatch(text)
        while iter_std_link.hasNext():
            match = iter_std_link.next()
            is_active = self._cursor_in_range(match.capturedStart(), match.capturedEnd())
            
            if is_active:
                # Show all syntax dimmed
                self.setFormat(match.capturedStart(1), 1, self.fmt_dim)  # [
                self.setFormat(match.capturedStart(3), 1, self.fmt_dim)  # ]
                self.setFormat(match.capturedStart(4), 1, self.fmt_dim)  # (
                self.setFormat(match.capturedStart(6), 1, self.fmt_dim)  # )
                self.setFormat(match.capturedStart(2), match.capturedLength(2), fmt_url_link)  # text
                self.setFormat(match.capturedStart(5), match.capturedLength(5), self.fmt_dim)  # url
            else:
                # Hide syntax, only show link text
                self.setFormat(match.capturedStart(1), 1, self.fmt_transparent)
                self.setFormat(match.capturedStart(3), match.capturedLength(3) + match.capturedLength(4) + match.capturedLength(5) + match.capturedLength(6), self.fmt_transparent)
                self.setFormat(match.capturedStart(2), match.capturedLength(2), fmt_url_link)

        # 9. Unordered Lists (- item or * item)
        fmt_list_marker = QTextCharFormat()
        fmt_list_marker.setForeground(QColor("#FF79C6"))  # Pink marker
        
        match_ul = QRegularExpression(r"^(\s*)([-\*])\s+(.*)$").match(text)
        if match_ul.hasMatch():
            cursor = self.editor.textCursor()
            block = self.currentBlock()
            cursor_in_block = (cursor.blockNumber() == block.blockNumber())
            
            # Always show the marker, just color it
            self.setFormat(match_ul.capturedStart(2), match_ul.capturedLength(2), fmt_list_marker)

        # 10. Ordered Lists (1. item)
        match_ol = QRegularExpression(r"^(\s*)(\d+\.)\s+(.*)$").match(text)
        if match_ol.hasMatch():
            self.setFormat(match_ol.capturedStart(2), match_ol.capturedLength(2), fmt_list_marker)

        # 11. Horizontal Rules (---, ***, ___)
        match_hr = QRegularExpression(r"^(\s*)([-\*_]{3,})\s*$").match(text)
        if match_hr.hasMatch():
            fmt_hr = QTextCharFormat()
            fmt_hr.setForeground(QColor("#6272A4"))
            self.setFormat(match_hr.capturedStart(2), match_hr.capturedLength(2), fmt_hr)

        # 12. Content Blocks ({{content}}) - Distinct from [[]] links
        # Pattern: (\{\{)(.+?)(\}\})
        fmt_block = QTextCharFormat()
        fmt_block.setForeground(QColor("#FFB86C"))  # Orange/Golden - distinct from cyan links
        fmt_block.setFontWeight(QFont.Bold)
        
        iter_block = QRegularExpression(r"(\{\{)(.+?)(\}\})").globalMatch(text)
        while iter_block.hasNext():
            match = iter_block.next()
            is_active = self._cursor_in_range(match.capturedStart(), match.capturedEnd())
            
            if is_active:
                self.setFormat(match.capturedStart(1), 2, self.fmt_dim)  # {{
                self.setFormat(match.capturedStart(3), 2, self.fmt_dim)  # }}
                self.setFormat(match.capturedStart(2), match.capturedLength(2), fmt_block)
            else:
                self.setFormat(match.capturedStart(1), 2, self.fmt_transparent)
                self.setFormat(match.capturedStart(3), 2, self.fmt_transparent)
                self.setFormat(match.capturedStart(2), match.capturedLength(2), fmt_block)
