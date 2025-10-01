from markdown_it import MarkdownIt
from markdown_it.token import Token
from typing import List

def parse_markdown(text: str) -> List[Token]:
    """
    Parses a markdown string into an Abstract Syntax Tree (AST) of tokens.

    Args:
        text: The markdown string to parse.

    Returns:
        A list of Token objects representing the AST.
    """
    md = MarkdownIt()
    tokens = md.parse(text)
    return tokens