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
# --- Extended tests for content block overlay and autosave gating ---

import re
import queue
import hashlib
from PySide6.QtTest import QTest

def place_cursor_inside_block(editor, offset=4):
    txt = editor.toPlainText()
    m = re.search(r"\{\{((?:.|\n)+?)\}\}", txt, flags=re.DOTALL)
    assert m, "No {{...}} block found"
    pos = m.start() + 2 + int(offset)
    c = editor.textCursor()
    c.setPosition(pos)
    editor.setTextCursor(c)

def test_overlay_shows_for_edits_variants():
    app = ensure_app()
    e = ReactiveEditor()
    e.show()
    e.setFocus()
    app.processEvents()
    QTest.qWait(10)
    e.setPlainText("Seed\n{{这是一个内容}}")
    for insert in ["abc", "123", "字"]:
        e.setPlainText("Seed\n{{这是一个内容}}")
        place_cursor_inside_block(e, offset=4)
        e._capture_snapshot_pre_edit()
        e.insertPlainText(insert)
        app.processEvents()
        QTest.qWait(260)
        app.processEvents()  # > debounce (180ms) to ensure timeout fires
        assert getattr(e, "_block_overlay", None) is not None and e._block_overlay.isVisible(), f"Overlay not visible for insert {insert!r}"
        # '全局更新'应禁用（在测试环境下无引用计数与DB）
        assert getattr(e, "_btn_sync", None) is not None and not e._btn_sync.isEnabled(), "Sync button should be disabled when refcount<=1 or new content already exists"

def test_autosave_gated_while_overlay_visible():
    app = ensure_app()
    e = ReactiveEditor()
    e.show()
    e.setFocus()
    app.processEvents()
    QTest.qWait(10)
    e.setPlainText("{{这是一个内容}}")
    place_cursor_inside_block(e, offset=4)
    e._capture_snapshot_pre_edit()
    e.insertPlainText("abc")
    app.processEvents()
    QTest.qWait(260)
    app.processEvents()
    # Ensure overlay visible and block dirty
    assert getattr(e, "_block_overlay", None) and e._block_overlay.isVisible(), "Overlay should be visible"
    assert getattr(e, "_autosave_timer", None) is not None, "Autosave timer must exist"
    t = e._autosave_timer
    try:
        t.stop()
    except Exception:
        pass
    e._schedule_autosave()
    assert not t.isActive(), "Autosave should be gated when overlay is visible or block_dirty=True"

def test_completion_hides_after_closing_braces():
    app = ensure_app()
    e = ReactiveEditor()
    e.setPlainText("Start {{foo}} end")
    set_cursor_end(e)
    # Trigger once, then type closing brace to ensure it hides
    e._check_for_completion_trigger()
    e.insertPlainText("}")
    app.processEvents()
    e._check_for_completion_trigger()
    assert not e.completer.popup().isVisible(), "Completion popup should hide after '}}' typed"

def test_new_block_commit_calls_autosave():
    app = ensure_app()
    e = ReactiveEditor()
    e.setPlainText("{{这是一个内容}}")
    # Monkey-patch perform_autosave to detect call
    e._test_saved = False
    e._perform_autosave = lambda: setattr(e, "_test_saved", True)
    e._on_overlay_new_block_clicked()
    assert e._test_saved, "New block commit should trigger autosave"

def test_cancel_calls_autosave():
    app = ensure_app()
    e = ReactiveEditor()
    e.show()
    e.setFocus()
    app.processEvents()
    QTest.qWait(10)
    e.setPlainText("{{这是一个内容}}")
    txt = e.toPlainText()
    m = re.search(r"\{\{((?:.|\n)+?)\}\}", txt, flags=re.DOTALL)
    assert m
    e._active_block = {"start": m.start(), "end": m.end(), "original_content": "这是一个内容", "original_hash": "h"}
    e._test_saved = False
    e._perform_autosave = lambda: setattr(e, "_test_saved", True)
    e._on_overlay_cancel_clicked()
    assert e._test_saved, "Cancel should trigger autosave"

def test_sync_calls_autosave():
    app = ensure_app()
    e = ReactiveEditor()
    e.setPlainText("{{old}}")
    txt = e.toPlainText()
    m = re.search(r"\{\{((?:.|\n)+?)\}\}", txt, flags=re.DOTALL)
    assert m
    e._active_block = {"start": m.start(), "end": m.end(), "original_content": "old", "original_hash": hashlib.sha256(b"old").hexdigest()}
    # Modify content to mark dirty and show overlay
    place_cursor_inside_block(e, offset=2)
    e._capture_snapshot_pre_edit()
    e.insertPlainText("X")
    app.processEvents()
    QTest.qWait(260)
    app.processEvents()
    e._sync_allowed = True  # allow sync
    class DummySvc:
        def __init__(self):
            self.task_queue = queue.Queue()
            self.vault_path = "."
    e.app_context = type("Ctx", (), {"file_indexer_service": DummySvc()})()
    e._test_saved = False
    e._perform_autosave = lambda: setattr(e, "_test_saved", True)
    e._on_overlay_sync_clicked()
    assert e._test_saved, "Sync should trigger autosave"