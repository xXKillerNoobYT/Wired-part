"""Login dialog with PIN authentication and first-run admin setup."""

import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from wired_part.database.models import User
from wired_part.database.repository import Repository

# Path to the settings file where we persist last-login username
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_SETTINGS_FILE = _PROJECT_ROOT / "data" / "settings.json"


def _get_last_login_username() -> str:
    """Read the last-login username from settings.json."""
    try:
        if _SETTINGS_FILE.exists():
            data = json.loads(_SETTINGS_FILE.read_text(encoding="utf-8"))
            return data.get("last_login_username", "")
    except (json.JSONDecodeError, OSError):
        pass
    return ""


def _save_last_login_username(username: str):
    """Write the last-login username to settings.json."""
    data = {}
    try:
        if _SETTINGS_FILE.exists():
            data = json.loads(_SETTINGS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        pass
    data["last_login_username"] = username
    _SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _SETTINGS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


# ── Styles ────────────────────────────────────────────────────────

_USER_CARD_STYLE = """
    QFrame#userCard {
        background-color: #313244;
        border: 2px solid #45475a;
        border-radius: 8px;
        padding: 10px;
    }
    QFrame#userCard:hover {
        border-color: #89b4fa;
        background-color: #3b3d54;
    }
"""

_USER_CARD_SELECTED_STYLE = """
    QFrame#userCard {
        background-color: #3b3d54;
        border: 2px solid #89b4fa;
        border-radius: 8px;
        padding: 10px;
    }
"""

_PIN_PANEL_STYLE = """
    QFrame#pinPanel {
        background-color: #313244;
        border: 1px solid #45475a;
        border-radius: 8px;
        padding: 12px;
    }
"""


class _UserCard(QFrame):
    """Clickable card representing a single user in the login screen."""

    def __init__(self, user: User, hat_names: list[str],
                 is_last_login: bool = False, parent=None):
        super().__init__(parent)
        self.user = user
        self.setObjectName("userCard")
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(_USER_CARD_STYLE)
        self.setMinimumHeight(56)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)

        # Avatar circle with initials
        initials = "".join(
            w[0].upper() for w in user.display_name.split()[:2]
        ) or "?"
        avatar = QLabel(initials)
        avatar.setFixedSize(40, 40)
        avatar.setAlignment(Qt.AlignCenter)
        avatar.setStyleSheet(
            "background-color: #89b4fa; color: #1e1e2e; "
            "border-radius: 20px; font-size: 15px; font-weight: bold;"
        )
        layout.addWidget(avatar)

        # Name and details
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)

        name_row = QHBoxLayout()
        name_row.setSpacing(8)
        name_label = QLabel(user.display_name)
        name_label.setStyleSheet(
            "font-size: 14px; font-weight: bold; color: #cdd6f4;"
        )
        name_row.addWidget(name_label)

        if is_last_login:
            tag = QLabel("Last Login")
            tag.setStyleSheet(
                "background-color: #a6e3a1; color: #1e1e2e; "
                "font-size: 10px; font-weight: bold; padding: 1px 6px; "
                "border-radius: 4px;"
            )
            name_row.addWidget(tag)

        name_row.addStretch()
        info_layout.addLayout(name_row)

        hats_text = ", ".join(hat_names) if hat_names else user.role
        detail = QLabel(f"@{user.username}  ·  {hats_text}")
        detail.setStyleSheet("font-size: 11px; color: #a6adc8;")
        info_layout.addWidget(detail)

        layout.addLayout(info_layout, 1)

    def set_selected(self, selected: bool):
        """Toggle the visual selected state."""
        self.setStyleSheet(
            _USER_CARD_SELECTED_STYLE if selected else _USER_CARD_STYLE
        )


class LoginDialog(QDialog):
    """PIN-based login screen with a visual user list.

    Users are displayed as clickable cards. Clicking a card selects
    that user and reveals the PIN input. The last logged-in user
    is shown at the top with a "Last Login" badge.
    """

    def __init__(self, repo: Repository, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.authenticated_user = None
        self._selected_user: User | None = None
        self._cards: list[_UserCard] = []

        self.setWindowTitle("Wired-Part — Login")
        self.setMinimumSize(420, 480)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowContextHelpButtonHint
        )

        self._setup_ui()
        self._load_users()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # ── Title ───────────────────────────────────────────────
        title = QLabel("Wired-Part")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        layout.addWidget(title)

        subtitle = QLabel("Select your account to sign in")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("color: #6c7086; margin-bottom: 4px;")
        layout.addWidget(subtitle)

        # ── User list (scrollable) ──────────────────────────────
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.user_list_widget = QWidget()
        self.user_list_layout = QVBoxLayout(self.user_list_widget)
        self.user_list_layout.setContentsMargins(4, 4, 4, 4)
        self.user_list_layout.setSpacing(6)
        self.user_list_layout.addStretch()

        self.scroll.setWidget(self.user_list_widget)
        layout.addWidget(self.scroll, 1)

        # ── PIN panel (hidden until a user is selected) ─────────
        self.pin_panel = QFrame()
        self.pin_panel.setObjectName("pinPanel")
        self.pin_panel.setStyleSheet(_PIN_PANEL_STYLE)
        pin_layout = QVBoxLayout(self.pin_panel)
        pin_layout.setSpacing(8)

        self.pin_header = QLabel("Enter PIN")
        self.pin_header.setAlignment(Qt.AlignCenter)
        self.pin_header.setStyleSheet(
            "font-size: 13px; font-weight: bold; color: #cdd6f4;"
        )
        pin_layout.addWidget(self.pin_header)

        pin_row = QHBoxLayout()
        self.pin_input = QLineEdit()
        self.pin_input.setEchoMode(QLineEdit.Password)
        self.pin_input.setPlaceholderText("Enter PIN")
        self.pin_input.setMinimumHeight(36)
        self.pin_input.setMaxLength(6)
        self.pin_input.setAlignment(Qt.AlignCenter)
        self.pin_input.setStyleSheet(
            "font-size: 18px; letter-spacing: 8px; "
            "background-color: #1e1e2e; border: 1px solid #45475a; "
            "border-radius: 6px; color: #cdd6f4; padding: 4px;"
        )
        self.pin_input.returnPressed.connect(self._attempt_login)
        pin_row.addStretch()
        pin_row.addWidget(self.pin_input, 2)
        pin_row.addStretch()
        pin_layout.addLayout(pin_row)

        self.login_btn = QPushButton("Sign In")
        self.login_btn.setMinimumHeight(36)
        self.login_btn.setStyleSheet(
            "background-color: #89b4fa; color: #1e1e2e; "
            "font-weight: bold; border-radius: 6px; font-size: 13px;"
        )
        self.login_btn.clicked.connect(self._attempt_login)
        pin_layout.addWidget(self.login_btn)

        self.error_label = QLabel("")
        self.error_label.setAlignment(Qt.AlignCenter)
        self.error_label.setStyleSheet("color: #f38ba8; font-size: 12px;")
        pin_layout.addWidget(self.error_label)

        self.pin_panel.setVisible(False)
        layout.addWidget(self.pin_panel)

    def _load_users(self):
        """Build the user card list, with last-login user at the top."""
        # Clear existing cards
        for card in self._cards:
            card.setParent(None)
            card.deleteLater()
        self._cards.clear()

        users = self.repo.get_all_users(active_only=True)
        last_username = _get_last_login_username()

        # Sort: last-login user first, then alphabetical
        def sort_key(u: User):
            if u.username == last_username:
                return (0, u.display_name.lower())
            return (1, u.display_name.lower())

        users.sort(key=sort_key)

        # Remove the stretch before adding cards
        while self.user_list_layout.count():
            item = self.user_list_layout.takeAt(0)
            # Only delete spacer items, cards already cleaned above
            if item.widget() is None:
                del item

        for user in users:
            hat_names = self.repo.get_user_hat_names(user.id)
            is_last = user.username == last_username
            card = _UserCard(user, hat_names, is_last_login=is_last)
            card.mousePressEvent = (
                lambda event, u=user, c=card: self._on_user_clicked(u, c)
            )
            self.user_list_layout.addWidget(card)
            self._cards.append(card)

        self.user_list_layout.addStretch()

    def _on_user_clicked(self, user: User, card: _UserCard):
        """Select a user card and show the PIN panel."""
        self._selected_user = user

        # Update visual selection
        for c in self._cards:
            c.set_selected(c is card)

        # Show and focus PIN
        self.pin_header.setText(
            f"Enter PIN for {user.display_name}"
        )
        self.pin_input.clear()
        self.error_label.clear()
        self.pin_panel.setVisible(True)
        self.pin_input.setFocus()

    def _attempt_login(self):
        if not self._selected_user:
            self.error_label.setText("Select a user first")
            return

        pin = self.pin_input.text().strip()
        if not pin:
            self.error_label.setText("Please enter your PIN")
            return

        user = self.repo.authenticate_user(
            self._selected_user.username, pin
        )
        if user:
            _save_last_login_username(user.username)
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
        self.setMinimumSize(450, 400)
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
        self.create_btn.setStyleSheet(
            "background-color: #a6e3a1; color: #1e1e2e; "
            "font-weight: bold; border-radius: 6px; font-size: 13px;"
        )
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
            # Auto-assign Admin hat (id=1) to the first user
            admin_hat = self.repo.get_hat_by_id(1)
            if admin_hat:
                self.repo.assign_hat(user_id, admin_hat.id)
            _save_last_login_username(username)
            self.created_user = user
            self.accept()
        except Exception as e:
            self.error_label.setText(str(e))
