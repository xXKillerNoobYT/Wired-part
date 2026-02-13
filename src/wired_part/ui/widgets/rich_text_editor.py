"""Rich text editor widget with formatting toolbar — for notebook pages."""

from pathlib import Path

from PySide6.QtCore import Qt, Signal, QTimer, QUrl
from PySide6.QtGui import (
    QFont,
    QImage,
    QTextCharFormat,
    QTextCursor,
    QTextImageFormat,
    QTextListFormat,
)
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class _InsertLinkDialog(QDialog):
    """Small dialog to collect URL and display text for a hyperlink."""

    def __init__(self, selected_text: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Insert Link")
        self.setMinimumSize(380, 160)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(8)

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://example.com")
        self.url_input.setMinimumHeight(28)
        form.addRow("URL:", self.url_input)

        self.text_input = QLineEdit()
        self.text_input.setPlaceholderText("Link text (optional)")
        self.text_input.setMinimumHeight(28)
        self.text_input.setText(selected_text)
        form.addRow("Text:", self.text_input)

        layout.addLayout(form)

        btns = QHBoxLayout()
        ok_btn = QPushButton("Insert")
        ok_btn.setMinimumHeight(30)
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setMinimumHeight(30)
        cancel_btn.clicked.connect(self.reject)
        btns.addWidget(ok_btn)
        btns.addWidget(cancel_btn)
        layout.addLayout(btns)

    @property
    def url(self) -> str:
        return self.url_input.text().strip()

    @property
    def display_text(self) -> str:
        return self.text_input.text().strip() or self.url


class RichTextEditor(QWidget):
    """QTextEdit with formatting toolbar and auto-save debounce."""

    content_changed = Signal()  # Emitted after debounce period
    image_inserted = Signal(str)  # Emitted with file path when image inserted

    def __init__(self, parent=None):
        super().__init__(parent)
        self._auto_save_timer = QTimer()
        self._auto_save_timer.setSingleShot(True)
        self._auto_save_timer.setInterval(1500)  # 1.5 second debounce
        self._auto_save_timer.timeout.connect(self.content_changed.emit)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # ── Formatting toolbar ────────────────────────────────────
        toolbar = QHBoxLayout()
        toolbar.setSpacing(4)

        _BTN_STYLE = (
            "QPushButton { min-height: 28px; border: 1px solid #45475a; "
            "border-radius: 4px; padding: 2px 6px; } "
            "QPushButton:checked { background: #585b70; border-color: #89b4fa; } "
            "QPushButton:hover { background: #313244; }"
        )

        self.bold_btn = QPushButton("B")
        self.bold_btn.setFixedWidth(32)
        self.bold_btn.setCheckable(True)
        self.bold_btn.setStyleSheet(_BTN_STYLE + " QPushButton { font-weight: bold; }")
        self.bold_btn.setToolTip("Bold (Ctrl+B)")
        self.bold_btn.clicked.connect(self._toggle_bold)
        toolbar.addWidget(self.bold_btn)

        self.italic_btn = QPushButton("I")
        self.italic_btn.setFixedWidth(32)
        self.italic_btn.setCheckable(True)
        self.italic_btn.setStyleSheet(_BTN_STYLE + " QPushButton { font-style: italic; }")
        self.italic_btn.setToolTip("Italic (Ctrl+I)")
        self.italic_btn.clicked.connect(self._toggle_italic)
        toolbar.addWidget(self.italic_btn)

        self.underline_btn = QPushButton("U")
        self.underline_btn.setFixedWidth(32)
        self.underline_btn.setCheckable(True)
        self.underline_btn.setStyleSheet(
            _BTN_STYLE + " QPushButton { text-decoration: underline; }"
        )
        self.underline_btn.setToolTip("Underline (Ctrl+U)")
        self.underline_btn.clicked.connect(self._toggle_underline)
        toolbar.addWidget(self.underline_btn)

        # Separator
        sep1 = QLabel("|")
        sep1.setStyleSheet("color: #45475a; padding: 0 4px;")
        toolbar.addWidget(sep1)

        self.bullet_btn = QPushButton("List")
        self.bullet_btn.setFixedWidth(44)
        self.bullet_btn.setStyleSheet(_BTN_STYLE)
        self.bullet_btn.setToolTip("Bullet List")
        self.bullet_btn.clicked.connect(self._toggle_bullet_list)
        toolbar.addWidget(self.bullet_btn)

        self.numbered_btn = QPushButton("1.")
        self.numbered_btn.setFixedWidth(32)
        self.numbered_btn.setStyleSheet(_BTN_STYLE)
        self.numbered_btn.setToolTip("Numbered List")
        self.numbered_btn.clicked.connect(self._toggle_numbered_list)
        toolbar.addWidget(self.numbered_btn)

        sep2 = QLabel("|")
        sep2.setStyleSheet("color: #45475a; padding: 0 4px;")
        toolbar.addWidget(sep2)

        self.heading_btn = QPushButton("H")
        self.heading_btn.setFixedWidth(32)
        self.heading_btn.setStyleSheet(
            _BTN_STYLE + " QPushButton { font-weight: bold; font-size: 14px; }"
        )
        self.heading_btn.setToolTip("Toggle Heading")
        self.heading_btn.clicked.connect(self._toggle_heading)
        toolbar.addWidget(self.heading_btn)

        sep3 = QLabel("|")
        sep3.setStyleSheet("color: #45475a; padding: 0 4px;")
        toolbar.addWidget(sep3)

        self.link_btn = QPushButton("Link")
        self.link_btn.setFixedWidth(44)
        self.link_btn.setStyleSheet(_BTN_STYLE)
        self.link_btn.setToolTip("Insert Hyperlink")
        self.link_btn.clicked.connect(self._insert_link)
        toolbar.addWidget(self.link_btn)

        self.image_btn = QPushButton("Img")
        self.image_btn.setFixedWidth(38)
        self.image_btn.setStyleSheet(_BTN_STYLE)
        self.image_btn.setToolTip("Insert Image")
        self.image_btn.clicked.connect(self._insert_image)
        toolbar.addWidget(self.image_btn)

        toolbar.addStretch()

        layout.addLayout(toolbar)

        # ── Text editor ──────────────────────────────────────────
        self.editor = QTextEdit()
        self.editor.setAcceptRichText(True)
        self.editor.cursorPositionChanged.connect(
            self._update_toolbar_state
        )
        self.editor.textChanged.connect(self._on_text_changed)
        layout.addWidget(self.editor, 1)

    def _on_text_changed(self):
        """Restart the auto-save debounce timer."""
        self._auto_save_timer.start()

    def _toggle_bold(self):
        fmt = QTextCharFormat()
        fmt.setFontWeight(
            QFont.Bold if self.bold_btn.isChecked() else QFont.Normal
        )
        self.editor.mergeCurrentCharFormat(fmt)

    def _toggle_italic(self):
        fmt = QTextCharFormat()
        fmt.setFontItalic(self.italic_btn.isChecked())
        self.editor.mergeCurrentCharFormat(fmt)

    def _toggle_underline(self):
        fmt = QTextCharFormat()
        fmt.setFontUnderline(self.underline_btn.isChecked())
        self.editor.mergeCurrentCharFormat(fmt)

    def _toggle_bullet_list(self):
        cursor = self.editor.textCursor()
        current_list = cursor.currentList()
        if current_list:
            # Remove from list
            block_fmt = cursor.blockFormat()
            block_fmt.setIndent(0)
            cursor.setBlockFormat(block_fmt)
            # Can't easily remove from list, so just set indent to 0
        else:
            cursor.createList(QTextListFormat.ListDisc)

    def _toggle_numbered_list(self):
        cursor = self.editor.textCursor()
        current_list = cursor.currentList()
        if current_list:
            block_fmt = cursor.blockFormat()
            block_fmt.setIndent(0)
            cursor.setBlockFormat(block_fmt)
        else:
            cursor.createList(QTextListFormat.ListDecimal)

    def _toggle_heading(self):
        cursor = self.editor.textCursor()
        block_fmt = cursor.blockFormat()
        char_fmt = cursor.charFormat()

        # Toggle between normal and heading
        if char_fmt.font().pointSize() > 14:
            # Back to normal
            fmt = QTextCharFormat()
            fmt.setFontPointSize(10)
            fmt.setFontWeight(QFont.Normal)
            cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
            cursor.mergeCharFormat(fmt)
        else:
            fmt = QTextCharFormat()
            fmt.setFontPointSize(16)
            fmt.setFontWeight(QFont.Bold)
            cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
            cursor.mergeCharFormat(fmt)

    def _insert_link(self):
        """Show dialog and insert a hyperlink at the cursor position."""
        cursor = self.editor.textCursor()
        selected = cursor.selectedText()

        dlg = _InsertLinkDialog(selected, self)
        if dlg.exec() != QDialog.Accepted:
            return
        if not dlg.url:
            return

        url = dlg.url
        text = dlg.display_text

        # Insert as HTML anchor
        html = f'<a href="{url}">{text}</a>'
        cursor.insertHtml(html)

    def _insert_image(self):
        """Open file dialog and embed an image into the editor."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Insert Image", "",
            "Images (*.png *.jpg *.jpeg *.gif *.bmp *.webp)"
        )
        if not path:
            return

        # Load image and insert into document
        image = QImage(path)
        if image.isNull():
            return

        # Scale down large images to fit editor width (max 600px)
        max_width = 600
        if image.width() > max_width:
            image = image.scaledToWidth(
                max_width, Qt.TransformationMode.SmoothTransformation
            )

        # Register image resource in the document
        doc = self.editor.document()
        url = QUrl.fromLocalFile(path)
        doc.addResource(doc.ResourceType.ImageResource, url, image)

        # Insert image at cursor
        cursor = self.editor.textCursor()
        img_fmt = QTextImageFormat()
        img_fmt.setName(url.toString())
        img_fmt.setWidth(image.width())
        img_fmt.setHeight(image.height())
        cursor.insertImage(img_fmt)

        # Emit signal so notebook widget can track the file
        self.image_inserted.emit(path)

    def _update_toolbar_state(self):
        """Update toolbar button states based on cursor position."""
        fmt = self.editor.currentCharFormat()
        self.bold_btn.setChecked(fmt.fontWeight() == QFont.Bold)
        self.italic_btn.setChecked(fmt.fontItalic())
        self.underline_btn.setChecked(fmt.fontUnderline())

    # ── Public API ────────────────────────────────────────────────

    def set_html(self, html: str):
        """Set the editor content from HTML."""
        self.editor.blockSignals(True)
        self.editor.setHtml(html or "")
        self.editor.blockSignals(False)

    def get_html(self) -> str:
        """Get the editor content as HTML."""
        return self.editor.toHtml()

    def set_read_only(self, read_only: bool):
        """Set the editor to read-only mode."""
        self.editor.setReadOnly(read_only)
        for btn in (self.bold_btn, self.italic_btn, self.underline_btn,
                     self.bullet_btn, self.numbered_btn, self.heading_btn,
                     self.link_btn, self.image_btn):
            btn.setEnabled(not read_only)

    def set_content(self, html: str):
        """Alias for set_html — used by notebook_widget.switch_job."""
        self.set_html(html)

    def clear(self):
        """Clear the editor content."""
        self.editor.blockSignals(True)
        self.editor.clear()
        self.editor.blockSignals(False)
