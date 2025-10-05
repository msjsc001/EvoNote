import os

# Force headless Qt platform for CI/Windows.
# Prefer 'minimal' which is broadly available; users can override via env beforehand.
os.environ.setdefault("QT_QPA_PLATFORM", "minimal")

import sys
import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QTextCursor

# Ensure project root on sys.path for direct test invocation
sys.path.append(os.getcwd())

from plugins.editable_editor.main import ReactiveEditor  # noqa: E402


def ensure_app():
    """
    Create QApplication in headless mode robustly:
    - Try current platform plugin (default set to 'minimal' above).
    - On failure, fall back to 'offscreen'.
    - If仍失败，跳过测试以适配CI/本机平台差异。
    """
    app = QApplication.instance()
    if app is not None:
        return app
    try:
        return QApplication([])
    except Exception as e1:
        try:
            os.environ["QT_QPA_PLATFORM"] = "offscreen"
            return QApplication([])
        except Exception as e2:
            pytest.skip(f"Qt platform plugin initialization failed; skipping test. e1={e1}, e2={e2}")


def set_cursor_end(editor):
    c = editor.textCursor()
    c.movePosition(QTextCursor.End)
    editor.setTextCursor(c)


def test_curly_brace_input_does_not_clear():
    app = ensure_app()
    e = ReactiveEditor()
    e.setPlainText("Seed content")
    sequences = ["{{", "{{1", "{{12", "{{", "{{abc", "{{\n", "{{}}", "{{{{", "{{12}}", "{{12}{", "{{", "}}"]
    for seq in sequences:
        set_cursor_end(e)
        e.insertPlainText(seq)
        app.processEvents()
        assert e.toPlainText() != "", f"Document cleared by sequence: {seq!r}"


def test_check_for_completion_guarded_on_odd_inputs():
    app = ensure_app()
    e = ReactiveEditor()
    e.setPlainText("Start ")
    odd_inputs = ["{{", "{{12", "{{" * 50, "[[" * 10 + "bad"]
    for seq in odd_inputs:
        set_cursor_end(e)
        e.insertPlainText(seq)
        app.processEvents()
        # Directly exercise the guarded path
        e._check_for_completion_trigger()
        assert e.toPlainText() != "", f"Guard failed on input: {seq!r}"