"""Dialog for adding and editing categories."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QColorDialog,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from wired_part.database.models import Category
from wired_part.database.repository import Repository


class CategoryDialog(QDialog):
    """Add or edit a category."""

    def __init__(self, repo: Repository, category: Category = None,
                 parent=None):
        super().__init__(parent)
        self.repo = repo
        self.category = category
        self.editing = category is not None
        self.selected_color = category.color if category else "#6c7086"

        self.setWindowTitle(
            "Edit Category" if self.editing else "Add Category"
        )
        self.setFixedSize(400, 300)
        self._setup_ui()
        if self.editing:
            self._populate()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(10)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Category name")
        self.name_input.setMinimumHeight(30)
        form.addRow("Name:", self.name_input)

        self.desc_input = QTextEdit()
        self.desc_input.setPlaceholderText("Description (optional)")
        self.desc_input.setMaximumHeight(80)
        form.addRow("Description:", self.desc_input)

        # Color picker
        color_layout = QHBoxLayout()
        self.color_preview = QLabel("  ")
        self.color_preview.setFixedSize(30, 30)
        self._update_color_preview()
        color_layout.addWidget(self.color_preview)

        color_btn = QPushButton("Pick Color")
        color_btn.clicked.connect(self._pick_color)
        color_layout.addWidget(color_btn)
        color_layout.addStretch()
        form.addRow("Color:", color_layout)

        layout.addLayout(form)

        # Error label
        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: #f38ba8;")
        layout.addWidget(self.error_label)

        # Buttons
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.setMinimumHeight(34)
        save_btn.clicked.connect(self._save)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setMinimumHeight(34)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def _populate(self):
        self.name_input.setText(self.category.name)
        self.desc_input.setPlainText(self.category.description)
        self.selected_color = self.category.color
        self._update_color_preview()

    def _update_color_preview(self):
        self.color_preview.setStyleSheet(
            f"background-color: {self.selected_color}; "
            f"border: 1px solid #6c7086; border-radius: 4px;"
        )

    def _pick_color(self):
        from PySide6.QtGui import QColor
        color = QColorDialog.getColor(
            QColor(self.selected_color), self, "Pick Category Color"
        )
        if color.isValid():
            self.selected_color = color.name()
            self._update_color_preview()

    def _save(self):
        name = self.name_input.text().strip()
        description = self.desc_input.toPlainText().strip()

        if not name:
            self.error_label.setText("Name is required")
            return

        try:
            if self.editing:
                self.category.name = name
                self.category.description = description
                self.category.color = self.selected_color
                self.repo.update_category(self.category)
            else:
                cat = Category(
                    name=name,
                    description=description,
                    is_custom=1,
                    color=self.selected_color,
                )
                cat.id = self.repo.create_category(cat)
                self.category = cat
            self.accept()
        except Exception as e:
            self.error_label.setText(str(e))
