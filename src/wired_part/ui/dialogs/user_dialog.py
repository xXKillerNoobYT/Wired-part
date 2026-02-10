"""Dialog for adding and editing users."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from wired_part.database.models import User
from wired_part.database.repository import Repository


class UserDialog(QDialog):
    """Add or edit a user."""

    def __init__(self, repo: Repository, user: User = None, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.user = user
        self.editing = user is not None

        self.setWindowTitle("Edit User" if self.editing else "Add User")
        self.setFixedSize(400, 350)

        self._setup_ui()
        if self.editing:
            self._populate()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(10)

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("e.g. jsmith")
        self.username_input.setMinimumHeight(30)
        form.addRow("Username:", self.username_input)

        self.display_name_input = QLineEdit()
        self.display_name_input.setPlaceholderText("e.g. John Smith")
        self.display_name_input.setMinimumHeight(30)
        form.addRow("Display Name:", self.display_name_input)

        self.role_combo = QComboBox()
        self.role_combo.addItems(["admin", "user"])
        self.role_combo.setMinimumHeight(30)
        form.addRow("Role:", self.role_combo)

        # PIN fields (optional when editing)
        pin_label = "New PIN:" if self.editing else "PIN:"
        self.pin_input = QLineEdit()
        self.pin_input.setEchoMode(QLineEdit.Password)
        self.pin_input.setPlaceholderText(
            "Leave blank to keep current" if self.editing else "4-6 digit PIN"
        )
        self.pin_input.setMaxLength(6)
        self.pin_input.setMinimumHeight(30)
        form.addRow(pin_label, self.pin_input)

        self.pin_confirm = QLineEdit()
        self.pin_confirm.setEchoMode(QLineEdit.Password)
        self.pin_confirm.setPlaceholderText("Confirm PIN")
        self.pin_confirm.setMaxLength(6)
        self.pin_confirm.setMinimumHeight(30)
        form.addRow("Confirm:", self.pin_confirm)

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
        self.username_input.setText(self.user.username)
        self.display_name_input.setText(self.user.display_name)
        idx = self.role_combo.findText(self.user.role)
        if idx >= 0:
            self.role_combo.setCurrentIndex(idx)

    def _save(self):
        username = self.username_input.text().strip()
        display_name = self.display_name_input.text().strip()
        role = self.role_combo.currentText()
        pin = self.pin_input.text().strip()
        pin_confirm = self.pin_confirm.text().strip()

        if not username:
            self.error_label.setText("Username is required")
            return
        if not display_name:
            self.error_label.setText("Display name is required")
            return

        # PIN validation
        if not self.editing and not pin:
            self.error_label.setText("PIN is required for new users")
            return
        if pin:
            if len(pin) < 4:
                self.error_label.setText("PIN must be at least 4 digits")
                return
            if not pin.isdigit():
                self.error_label.setText("PIN must contain only digits")
                return
            if pin != pin_confirm:
                self.error_label.setText("PINs do not match")
                return

        # Check username uniqueness
        existing = self.repo.get_user_by_username(username)
        if existing and (not self.editing or existing.id != self.user.id):
            self.error_label.setText("Username already taken")
            return

        try:
            if self.editing:
                self.user.username = username
                self.user.display_name = display_name
                self.user.role = role
                if pin:
                    self.user.pin_hash = Repository.hash_pin(pin)
                self.repo.update_user(self.user)
            else:
                user = User(
                    username=username,
                    display_name=display_name,
                    pin_hash=Repository.hash_pin(pin),
                    role=role,
                    is_active=1,
                )
                user.id = self.repo.create_user(user)
                self.user = user
            self.accept()
        except Exception as e:
            self.error_label.setText(str(e))
