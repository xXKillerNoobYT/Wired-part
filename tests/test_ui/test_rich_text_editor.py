"""pytest-qt tests for the RichTextEditor widget."""

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QTextCursor
from PySide6.QtWidgets import QPushButton

from wired_part.ui.widgets.rich_text_editor import RichTextEditor


class TestRichTextEditorCreation:
    """Test that the editor creates and renders correctly."""

    def test_creates_without_crash(self, qtbot):
        editor = RichTextEditor()
        qtbot.addWidget(editor)
        assert editor is not None

    def test_has_editor_area(self, qtbot):
        editor = RichTextEditor()
        qtbot.addWidget(editor)
        assert editor.editor is not None

    def test_has_formatting_buttons(self, qtbot):
        editor = RichTextEditor()
        qtbot.addWidget(editor)
        assert editor.bold_btn is not None
        assert editor.italic_btn is not None
        assert editor.underline_btn is not None
        assert editor.bullet_btn is not None
        assert editor.heading_btn is not None
        assert editor.link_btn is not None
        assert editor.image_btn is not None


class TestRichTextEditorFormatting:
    """Test formatting toggle behaviors."""

    def test_bold_toggles(self, qtbot):
        """Clicking bold toggles the bold state."""
        editor = RichTextEditor()
        qtbot.addWidget(editor)
        editor.editor.setFocus()
        editor.editor.setPlainText("Hello World")

        # Select all text
        editor.editor.selectAll()

        # Click bold button
        qtbot.mouseClick(editor.bold_btn, Qt.LeftButton)

        # Check that bold is applied
        cursor = editor.editor.textCursor()
        assert cursor.charFormat().fontWeight() == QFont.Bold

    def test_italic_toggles(self, qtbot):
        """Clicking italic toggles the italic state."""
        editor = RichTextEditor()
        qtbot.addWidget(editor)
        editor.editor.setPlainText("Hello World")
        editor.editor.selectAll()

        qtbot.mouseClick(editor.italic_btn, Qt.LeftButton)

        cursor = editor.editor.textCursor()
        assert cursor.charFormat().fontItalic()

    def test_underline_toggles(self, qtbot):
        """Clicking underline toggles the underline state."""
        editor = RichTextEditor()
        qtbot.addWidget(editor)
        editor.editor.setPlainText("Hello World")
        editor.editor.selectAll()

        qtbot.mouseClick(editor.underline_btn, Qt.LeftButton)

        cursor = editor.editor.textCursor()
        assert cursor.charFormat().fontUnderline()


class TestRichTextEditorContent:
    """Test content get/set operations."""

    def test_set_and_get_html(self, qtbot):
        """Can set and retrieve HTML content."""
        editor = RichTextEditor()
        qtbot.addWidget(editor)
        editor.set_html("<b>Bold text</b>")
        html = editor.get_html()
        assert "Bold text" in html

    def test_set_content_alias(self, qtbot):
        """set_content works as an alias for set_html."""
        editor = RichTextEditor()
        qtbot.addWidget(editor)
        editor.set_content("<i>Italic</i>")
        html = editor.get_html()
        assert "Italic" in html

    def test_get_plain_text_via_editor(self, qtbot):
        """Can get plain text through the underlying QTextEdit."""
        editor = RichTextEditor()
        qtbot.addWidget(editor)
        editor.set_html("<p>Plain content</p>")
        text = editor.editor.toPlainText()
        assert "Plain content" in text

    def test_empty_editor(self, qtbot):
        """Empty editor returns empty-ish content."""
        editor = RichTextEditor()
        qtbot.addWidget(editor)
        text = editor.editor.toPlainText().strip()
        assert text == ""


class TestRichTextEditorReadOnly:
    """Test read-only mode."""

    def test_set_read_only_disables_toolbar(self, qtbot):
        """Setting read-only disables toolbar buttons."""
        editor = RichTextEditor()
        qtbot.addWidget(editor)
        editor.set_read_only(True)
        assert not editor.bold_btn.isEnabled()
        assert not editor.italic_btn.isEnabled()
        assert not editor.underline_btn.isEnabled()
        assert not editor.link_btn.isEnabled()
        assert not editor.image_btn.isEnabled()

    def test_unset_read_only_enables_toolbar(self, qtbot):
        """Disabling read-only re-enables toolbar."""
        editor = RichTextEditor()
        qtbot.addWidget(editor)
        editor.set_read_only(True)
        editor.set_read_only(False)
        assert editor.bold_btn.isEnabled()
        assert editor.italic_btn.isEnabled()


class TestRichTextEditorSignals:
    """Test signal emission."""

    def test_content_changed_signal(self, qtbot):
        """Typing in the editor emits content_changed after debounce."""
        editor = RichTextEditor()
        qtbot.addWidget(editor)

        with qtbot.waitSignal(editor.content_changed, timeout=3000):
            editor.editor.setPlainText("trigger change")
            # The signal is debounced (1.5s), wait for it
