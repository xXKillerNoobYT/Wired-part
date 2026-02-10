"""Login dialog with PIN authentication and first-run admin setup."""

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


class LoginDialog(QDialog):
    """PIN-based login screen."""

    def __init__(self, repo: Repository, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.authenticated_user = None

        self.setWindowTitle("Wired-Part — Login")
        self.setFixedSize(400, 250)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowContextHelpButtonHint
        )

        self._setup_ui()
        self._load_users()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        # Title
        title = QLabel("Wired-Part")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        layout.addWidget(title)

        subtitle = QLabel("Enter your credentials to continue")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("color: #6c7086;")
        layout.addWidget(subtitle)

        # Form
        form = QFormLayout()
        form.setSpacing(10)

        self.user_combo = QComboBox()
        self.user_combo.setMinimumHeight(32)
        form.addRow("User:", self.user_combo)

        self.pin_input = QLineEdit()
        self.pin_input.setEchoMode(QLineEdit.Password)
        self.pin_input.setPlaceholderText("Enter PIN")
        self.pin_input.setMinimumHeight(32)
        self.pin_input.setMaxLength(6)
        self.pin_input.returnPressed.connect(self._attempt_login)
        form.addRow("PIN:", self.pin_input)

        layout.addLayout(form)

        # Buttons
        btn_layout = QHBoxLayout()
        self.login_btn = QPushButton("Login")
        self.login_btn.setMinimumHeight(36)
        self.login_btn.setDefault(True)
        self.login_btn.clicked.connect(self._attempt_login)
        btn_layout.addWidget(self.login_btn)
        layout.addLayout(btn_layout)

        # Error label
        self.error_label = QLabel("")
        self.error_label.setAlignment(Qt.AlignCenter)
        self.error_label.setStyleSheet("color: #f38ba8;")
        layout.addWidget(self.error_label)

    def _load_users(self):
        users = self.repo.get_all_users(active_only=True)
        self.user_combo.clear()
        for user in users:
            self.user_combo.addItem(
                f"{user.display_name} ({user.username})", user.username
            )

    def _attempt_login(self):
        if self.user_combo.count() == 0:
            self.error_label.setText("No users found")
            return

        username = self.user_combo.currentData()
        pin = self.pin_input.text().strip()

        if not pin:
            self.error_label.setText("Please enter your PIN")
            return

        user = self.repo.authenticate_user(username, pin)
        if user:
            self.authenticated_user = user
            self.accept()
        else:
            self.error_label.setText("Invalid PIN")
            self.pin_input.clear()
            self.pin_input.setFocus()


class FirstRunDialog(QDialog):
    """Dialog to create the initial admin user on first launch."""

    def __init__(self, repo: Repository, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.created_user = None

        self.setWindowTitle("Wired-Part — First Time Setup")
        self.setFixedSize(450, 350)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowContextHelpButtonHint
        )

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        title = QLabel("Welcome to Wired-Part")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        layout.addWidget(title)

        subtitle = QLabel(
            "No users found. Create an admin account to get started."
        )
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color: #6c7086;")
        layout.addWidget(subtitle)

        # Form
        form = QFormLayout()
        form.setSpacing(10)

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("e.g. admin")
        self.username_input.setMinimumHeight(32)
        form.addRow("Username:", self.username_input)

        self.display_name_input = QLineEdit()
        self.display_name_input.setPlaceholderText("e.g. Bob Smith")
        self.display_name_input.setMinimumHeight(32)
        form.addRow("Display Name:", self.display_name_input)

        self.pin_input = QLineEdit()
        self.pin_input.setEchoMode(QLineEdit.Password)
        self.pin_input.setPlaceholderText("4-6 digit PIN")
        self.pin_input.setMinimumHeight(32)
        self.pin_input.setMaxLength(6)
        form.addRow("PIN:", self.pin_input)

        self.pin_confirm = QLineEdit()
        self.pin_confirm.setEchoMode(QLineEdit.Password)
        self.pin_confirm.setPlaceholderText("Confirm PIN")
        self.pin_confirm.setMinimumHeight(32)
        self.pin_confirm.setMaxLength(6)
        self.pin_confirm.returnPressed.connect(self._create_admin)
        form.addRow("Confirm PIN:", self.pin_confirm)

        layout.addLayout(form)

        # Button
        self.create_btn = QPushButton("Create Admin Account")
        self.create_btn.setMinimumHeight(36)
        self.create_btn.clicked.connect(self._create_admin)
        layout.addWidget(self.create_btn)

        # Error label
        self.error_label = QLabel("")
        self.error_label.setAlignment(Qt.AlignCenter)
        self.error_label.setStyleSheet("color: #f38ba8;")
        layout.addWidget(self.error_label)

    def _create_admin(self):
        username = self.username_input.text().strip()
        display_name = self.display_name_input.text().strip()
        pin = self.pin_input.text().strip()
        pin_confirm = self.pin_confirm.text().strip()

        if not username:
            self.error_label.setText("Username is required")
            return
        if not display_name:
            self.error_label.setText("Display name is required")
            return
        if not pin or len(pin) < 4:
            self.error_label.setText("PIN must be at least 4 digits")
            return
        if not pin.isdigit():
            self.error_label.setText("PIN must contain only digits")
            return
        if pin != pin_confirm:
            self.error_label.setText("PINs do not match")
            return

        user = User(
            username=username,
            display_name=display_name,
            pin_hash=Repository.hash_pin(pin),
            role="admin",
            is_active=1,
        )
        try:
            user_id = self.repo.create_user(user)
            user.id = user_id
            # Auto-assign Admin hat to the first user
            admin_hat = self.repo.get_hat_by_name("Admin")
            if admin_hat:
                self.repo.assign_hat(user_id, admin_hat.id)
            self.created_user = user
            self.accept()
        except Exception as e:
            self.error_label.setText(str(e))
